"""Accepted findings backed by the existing verified-document and release services."""
import calendar
from datetime import date, timedelta
from fractions import Fraction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ewaf.evidence import source_context, resolve_reviews, canonical, digest
from ewaf.evidence_services import persist, reasoned
from ewaf.vault_sources import eligibility_errors
from ewaf.readiness import ineligible_exclusion_errors
from .engine import ES
from .math import number, CalculationError
from .live_models import DatasetInputReview as Review
from . import si as si_rule
from ewaf import dataset_methods as methods
from . import member_record_evidence, automatic_inputs


def shift_months(day, count):
    year, month = divmod(day.year * 12 + day.month - 1 - count, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def periods(configuration):
    end = timezone.localdate(configuration.assessment_cutoff)
    if automatic_inputs.enabled(configuration.policy):
        return {'income_basis': 'Current approved member record at generation',
                'observed_on': timezone.localdate().isoformat(),
                'history_start': shift_months(end, configuration.policy['pa_months']).isoformat(),
                'history_end': end.isoformat()}
    close = parse_datetime(configuration.source['terms']['program']['registration_closes_at'])
    month = timezone.localdate(close).replace(day=1)
    return {'income_start': shift_months(month, configuration.policy['income_months']).isoformat(),
            'income_end': (month - timedelta(days=1)).isoformat(), 'observed_on': end.isoformat(),
            'history_start': shift_months(end, configuration.policy['pa_months']).isoformat(), 'history_end': end.isoformat()}


def context(application):
    source = source_context(application)
    source['dataset_program_applications'] = sorted(str(pk) for pk in application.program.applications.values_list('pk', flat=True))
    return source


def derive_inputs(findings, configuration, source):
    expected_keys = {'income_monthly', 'si_domains', 'employment', 'household_members', 'history_complete',
                     'income_start', 'income_end', 'observed_on', 'history_start', 'history_end', 'assessment_finding'}
    if methods.is_ses(configuration.policy):
        expected_keys.remove('si_domains')
        expected_keys.update(('income_consistency', 'income_resolution'))
        if methods.is_composite(configuration.policy):
            expected_keys.update(('household_four_ps', 'four_ps_household_confirmed', 'four_ps_household_review'))
    elif si_rule.document_rule(configuration.policy):
        expected_keys.remove('si_domains')
        expected_keys.add('si_documents')
    if not isinstance(findings, dict) or set(findings) != expected_keys:
        raise ValidationError('Record all reviewer findings and assessment periods; a note alone cannot establish accepted inputs.')
    if any(findings[key] != value for key, value in periods(configuration).items()):
        raise ValidationError('The findings must use this bound policy period and immutable assessment cutoff.')
    if not isinstance(findings['assessment_finding'], str) or not findings['assessment_finding'].strip():
        raise ValidationError('Record the evidence-supported assessment finding.')
    try:
        amounts = findings['income_monthly']
        if not isinstance(amounts, list) or len(amounts) != configuration.policy['income_months']:
            raise ValueError
        incomes = [number(value) for value in amounts]
        if any(value < 0 for value in incomes):
            raise ValueError
        if methods.is_ses(configuration.policy):
            if findings['income_consistency'] not in ('consistent', 'resolved'):
                raise ValidationError('Review the income dates and evidence discrepancies before accepting SES; unresolved is not zero.')
            if (not isinstance(findings['income_resolution'], str)
                    or len(findings['income_resolution']) > 4000
                    or findings['income_consistency'] == 'resolved' and not findings['income_resolution'].strip()):
                raise ValidationError('Record how the income discrepancy was resolved and why this income was accepted.')
            if methods.is_composite(configuration.policy):
                if type(findings['household_four_ps']) is not bool:
                    raise ValidationError('Household 4Ps participation is unresolved. Record Verified Yes or Verified No under the approved evidence procedure.')
                if (findings['four_ps_household_confirmed'] is not True
                        or not isinstance(findings['four_ps_household_review'], str)
                        or not findings['four_ps_household_review'].strip()
                        or len(findings['four_ps_household_review']) > 4000):
                    raise ValidationError('Confirm the applicant-household relationship and record the evidence-supported 4Ps review under the approved procedure.')
        elif si_rule.document_rule(configuration.policy):
            si = si_rule.score(findings['si_documents'])
        else:
            domains = findings['si_domains']
            if set(domains) != {'food', 'housing', 'care'} or any(value not in ('none', 'occasional', 'recurrent', 'critical') for value in domains.values()):
                raise ValueError
            si = (4 if 'critical' in domains.values() or list(domains.values()).count('recurrent') >= 2 else
                  3 if 'recurrent' in domains.values() else 2 if 'occasional' in domains.values() else 1)
        employment = findings['employment']
        from ewaf.employment_scoring import SCORES
        # Retained reviews must still validate; new runs enforce their frozen encoding.
        if employment not in (ES | SCORES):
            raise ValidationError('Unlisted employment remains unresolved; no mapping to unemployed is assumed.')
        household = findings['household_members']
        if type(household) is not int or not 1 <= household <= 2147483647 or findings['history_complete'] is not True:
            raise ValueError
    except (ValueError, TypeError, KeyError, CalculationError):
        label = 'Accepted SES income, employment, household count and verified history coverage' if methods.is_ses(configuration.policy) else 'Accepted income, SI findings, household count and verified history coverage'
        raise ValidationError(label + ' are required; unknown is not zero.') from None
    releases = [row for row in source['pa']['successful']
        if findings['history_start'] <= row['released_on'] <= findings['history_end']
        and parse_datetime(row['recorded_at']) <= configuration.assessment_cutoff]
    if configuration.policy['pa_scope'] == 'this_program':
        releases = [row for row in releases if row['application_id'] in source['dataset_program_applications']]
    result = {'ES': {'value': employment, 'source_type': 'accepted_employment_category', 'unit': 'category'},
            'PA': {'value': str(len(releases)), 'source_type': 'successful_releases', 'unit': 'records',
                   'release_ids': [row['id'] for row in releases]},
            'HM': {'value': str(household), 'source_type': 'accepted_household_assessment', 'unit': 'persons'}}
    if methods.is_ses(configuration.policy):
        result['SES'] = {'value': str(sum(incomes) / len(incomes)), 'source_type': 'accepted_household_income', 'unit': 'PHP/month'}
        if methods.is_composite(configuration.policy):
            result['SES'].update(source_type='accepted_household_income_and_4ps',
                household_four_ps=int(findings['household_four_ps']),
                four_ps_observed_on=findings['observed_on'])
    else:
        result.update(HI={'value': str(sum(incomes) / len(incomes)), 'source_type': 'accepted_income_assessment', 'unit': 'PHP/month'},
                      SI={'value': str(si), 'source_type': 'accepted_si_rubric', 'unit': 'level'})
    return result


def supporting(application, configuration, selections):
    if member_record_evidence.enabled(configuration.policy):
        if selections != {}:
            raise ValidationError('This policy uses member records; do not submit separate ranking documents.')
        return member_record_evidence.supporting(context(application), configuration)
    codes = methods.criteria(configuration.policy)
    if not isinstance(selections, dict) or set(selections) != set(codes):
        raise ValidationError('Select current verified evidence for every criterion, including PA history coverage.')
    today = timezone.localdate()
    result = {}
    from documents.models import DocumentVerification
    for code in codes:
        reviews = resolve_reviews(application, selections[code], at=today)
        allowed = configuration.policy[f'evidence_{code}']
        if not reviews or any(row['document_type'] not in allowed for row in reviews):
            raise ValidationError(f'{code}: supporting evidence must use the types authorized by this policy.')
        if DocumentVerification.objects.filter(pk__in=selections[code], reviewed_at__lt=
                timezone.now() - timedelta(days=configuration.policy['evidence_max_age_days'])).exists():
            raise ValidationError(f'{code}: supporting review is stale under this policy.')
        result[code] = reviews
    return result


def review_token(application, configuration):
    latest = Review.objects.filter(application=application).first()
    return digest({'configuration': configuration.digest, 'source': context(application),
                   'latest': latest.digest if latest else None})


def record(reference, *, user, expected, findings, selections, state, reason, confirmed):
    from programs.models import ProgramApplication
    from ewaf.operational_services import fence, latest_configuration
    from .live_services import require_binding
    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
    with fence(program_id, user, 'ewaf.review_criterionassessment') as (current, program, applications):
        application = next(item for item in applications if str(item.pk) == str(reference))
        configuration = latest_configuration(program)
        if not configuration.dataset_policy_id:
            raise ValidationError('Use this program\'s original evidence workflow.')
        require_binding(configuration)
        if automatic_inputs.enabled(configuration.policy):
            raise ValidationError('This program uses member records automatically; update the member directory to correct its inputs.')
        if state not in ('ACCEPTED', 'NEEDS_REVIEW', 'DISPUTED'):
            raise ValidationError('Choose an explicit review outcome.')
        if expected != review_token(application, configuration):
            raise ValidationError('Applicant evidence or policy changed. Reload before reviewing.')
        if application.status != 'ELIGIBLE':
            raise ValidationError('Complete the existing eligibility review before accepting dataset inputs.')
        source = context(application)
        errors = eligibility_errors(application, source)
        if errors:
            raise ValidationError(errors)
        inputs, reviews = {}, {}
        if state == 'ACCEPTED':
            if timezone.now() < configuration.assessment_cutoff:
                raise ValidationError('The assessment cutoff has not occurred; do not accept future observations.')
            reviews = supporting(application, configuration, selections)
            inputs = derive_inputs(findings, configuration, source)
        previous = Review.objects.filter(application=application).first()
        row = persist(Review(program=program, application=application, configuration=configuration,
            revision=previous.revision + 1 if previous else 1, previous=previous, state=state,
            findings=canonical(findings), inputs=inputs, supporting_reviews=reviews, source=source,
            **reasoned(current, reason, confirmed)))
        if source != context(application):
            raise ValidationError('Source evidence changed during review; the acceptance was rolled back.')
        return row


def accepted(application, configuration, source):
    row = Review.objects.filter(application=application).first()
    if not row or row.state != 'ACCEPTED' or row.configuration_id != configuration.pk:
        if member_record_evidence.enabled(configuration.policy):
            raise ValidationError('Open Review ranking inputs and accept the member-record findings. No separate ranking document is required.')
        if methods.is_composite(configuration.policy):
            raise ValidationError('Accept all four composite-SES inputs, including explicit reviewed household 4Ps Yes/No and relationship evidence, under the exact bound policy first.')
        raise ValidationError('Accept all four SES dataset inputs under the exact bound policy first.' if methods.is_ses(configuration.policy)
                              else 'Accept all five dataset inputs under the exact bound policy first.')
    row.clean()
    if row.source != source:
        from ewaf.ranking_freshness import eligibility_recheck
        if not eligibility_recheck(row.source, source):
            raise ValidationError('Accepted inputs are stale; reassess changed declarations, evidence or assistance history.')
    if member_record_evidence.enabled(configuration.policy):
        # An audited Eligible confirmation does not replace unchanged findings.
        # The current source passed the exact comparison or recheck above.
        if row.supporting_reviews != member_record_evidence.supporting(row.source, configuration):
            raise ValidationError('Member-record provenance changed; review the ranking inputs again.')
        if row.recorded_at < timezone.now() - timedelta(days=configuration.policy['evidence_max_age_days']):
            raise ValidationError('The ranking-input review is outdated; review the current member records again.')
        return row
    selections = {code: [review['id'] for review in rows] for code, rows in row.supporting_reviews.items()}
    if supporting(application, configuration, selections) != row.supporting_reviews:
        raise ValidationError('Supporting evidence changed; accepted inputs need renewed review.')
    return row


def inventory(program, applications, configuration):
    from . import rolling_pool
    open_ranking = rolling_pool.enabled(configuration.policy) and timezone.now() < program.registration_closes_at
    rows, eligible, problems = [], {}, []
    previous = None
    if methods.is_composite(configuration.policy):
        from ewaf.operational_models import OperationalRun
        previous = OperationalRun.objects.filter(program=program, configuration=configuration).first()
        if previous:
            previous.clean()
    for application in applications:
        current_source = source = context(application)
        if automatic_inputs.enabled(configuration.policy):
            source['member_record_inputs'] = automatic_inputs.member_values(application.member)
        receipts, errors = [], []
        if previous:
            from .fulfillment import project
            try:
                source, receipts = project(application, configuration, source, previous)
            except ValidationError as error:
                errors.extend(error.messages)
        errors.extend(eligibility_errors(application, source))
        review, automatic = None, None
        if source['status'] == 'INELIGIBLE':
            errors = ineligible_exclusion_errors(source)
        elif source['status'] != 'ELIGIBLE':
            errors.append('APPLICATION_REVIEW_UNRESOLVED')
        elif not errors:
            try:
                if automatic_inputs.enabled(configuration.policy):
                    automatic = automatic_inputs.entry(source, configuration)
                else:
                    review = accepted(application, configuration, source)
            except ValidationError as error:
                errors.extend(error.messages)
        if source['status'] != 'INELIGIBLE' and application.submitted_at > program.registration_closes_at:
            errors.append('APPLICATION_SUBMITTED_AFTER_APPROVED_CLOSE')
        rows.append({'application': str(application.pk), 'reference': application.public_reference,
            'status': application.status, 'source': source, 'errors': sorted(set(errors)),
            'membership': not errors, 'evidence': bool(review or automatic), 'pr': bool(review or automatic),
            **({'current_source': current_source, 'post_cutoff_receipts': receipts} if receipts else {})})
        if errors and not (open_ranking and source['status'] not in ('ELIGIBLE', 'COMPLETED')):
            problems.extend(f'{application.pk}: {message}' for message in errors)
        elif automatic:
            eligible[str(application.pk)] = automatic
        elif review:
            eligible[str(application.pk)] = {'inputs': review.inputs,
                'assessments': {'dataset_review': {'id': review.pk, 'digest': review.digest, 'payload': review.payload()}},
                'pr': {'eligibility_review': source['case'], 'contributes_to_score': False}}
    return rows, eligible, problems
