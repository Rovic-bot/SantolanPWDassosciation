"""Reviewed registered values and verified releases for the shared vault contract."""
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date
from .evidence import canonical, digest, source_context, resolve_reviews
from .household_criteria import CRITERIA, SOURCES
from .household_math import calculate
from .vault_models import RegisteredInputReview
from .evidence_services import persist, reasoned
from .readiness import ineligible_exclusion_errors


def sources(application, configuration, context):
    member = application.member
    releases = context['pa']['successful']
    if configuration.policy['pa_scope'] == 'this_program':
        from programs.models import ProgramApplication
        ids = {str(pk) for pk in ProgramApplication.objects.filter(program=application.program).values_list('pk', flat=True)}
        releases = [row for row in releases if row['application_id'] in ids]
    if configuration.policy['pa_period'] == 'date_range':
        releases = [row for row in releases if configuration.policy['pa_start'] <= row['released_on'] <= configuration.policy['pa_end']]
    values = {'HI': str(member.household_monthly_income) if member.household_monthly_income is not None else None,
        'SI': member.registration_profile.get('four_ps_member'), 'ES': member.employment_status or None,
        'PA': len(releases), 'HM': member.household_members}
    inputs = {code: {'source_type': SOURCES[code], 'unit': configuration.policy['criteria'][code]['unit'],
                     'value': values[code]} for code in CRITERIA}
    return canonical({'context': context, 'configuration': configuration.digest, 'inputs': inputs,
                      'release_ids': [row['id'] for row in releases]})


def validate_inputs(source, configuration):
    for code, item in source['inputs'].items():
        if item['value'] is None or item['value'] == '':
            raise ValidationError(f'{code}: accepted member-registration information is missing. Request a reviewed record update.')
    calculate(inputs=source['inputs'], definitions=configuration.policy['criteria'],
              judgments=configuration.judgments, validation=configuration.validation)


def verified_documents(application, configuration, choices):
    if not isinstance(choices, dict) or set(choices) != set(CRITERIA) - {'PA'}:
        raise ValidationError('Select verified supporting evidence for the four registered criteria.')
    result = {}
    for code, identifiers in choices.items():
        rows = resolve_reviews(application, identifiers, at=timezone.localdate())
        allowed = configuration.policy['criteria'][code]['evidence_document_types']
        if not rows or any(row['document_type'] not in allowed for row in rows):
            raise ValidationError(f'{code}: use current, verified documents of the types approved in the vault.')
        result[code] = rows
    return result


def eligibility_errors(application, context):
    from .readiness import evaluate
    ready = evaluate(application, context=context)
    errors = [item['code'] for item in ready['reasons']['eligibility']]
    errors += [item['code'] for item in ready['reasons']['governance'] if item['code'] != 'CRITERION_POLICY_UNAPPROVED']
    if context.get('current_information') and not context['current_information'].get('resolved'):
        errors.append('CURRENT_INFORMATION_REVIEW_REQUIRED')
    return errors


def review_token(application, configuration):
    latest = RegisteredInputReview.objects.filter(application=application).first()
    return digest({'source': sources(application, configuration, source_context(application)),
                   'review': latest.digest if latest else None})


def record_review(reference, *, user, expected, supporting_review_ids, observation_start, observation_end, reason, confirmed):
    from programs.models import ProgramApplication
    from .operational_services import fence, latest_configuration
    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
    with fence(program_id, user, 'ewaf.review_criterionassessment') as (current, program, applications):
        application = next(item for item in applications if item.pk == reference or str(item.pk) == str(reference))
        configuration = latest_configuration(program)
        if not configuration.vault_revision_id:
            raise ValidationError('Use this program\'s retained evidence review workflow.')
        context = source_context(application)
        errors = eligibility_errors(application, context)
        if errors:
            raise ValidationError(errors)
        if expected != review_token(application, configuration):
            raise ValidationError('Member information, evidence or assistance records changed. Reload and review again.')
        start, end = (parse_date(configuration.policy[key]) for key in ('assessment_start', 'assessment_end'))
        if not (start <= observation_start <= observation_end <= end and observation_end <= timezone.localdate()):
            raise ValidationError('The reviewed information must fall within the vault assessment period and cutoff.')
        source = sources(application, configuration, context)
        validate_inputs(source, configuration)
        reviews = verified_documents(application, configuration, supporting_review_ids)
        return persist(RegisteredInputReview(program=program, application=application, configuration=configuration,
            source=source, supporting_reviews=reviews, observation_start=observation_start, observation_end=observation_end,
            **reasoned(current, reason, confirmed)))


def accepted_review(application, configuration, source):
    row = RegisteredInputReview.objects.filter(application=application).first()
    if not row:
        raise ValidationError('Verify the registered EWAF inputs and supporting evidence before calculation.')
    row.clean()
    if row.configuration_id != configuration.pk or row.source != source:
        raise ValidationError('Registered EWAF inputs or their accepted sources changed. Review them again.')
    current = verified_documents(application, configuration,
        {code: [review['id'] for review in rows] for code, rows in row.supporting_reviews.items()})
    if row.supporting_reviews != current:
        raise ValidationError('The registered-input supporting evidence has changed.')
    validate_inputs(source, configuration)
    return row


def inventory(program, applications, configuration):
    rows, accepted, problems = [], {}, []
    for application in applications:
        context = source_context(application)
        errors = eligibility_errors(application, context)
        review = None
        if application.status == 'INELIGIBLE':
            errors = ineligible_exclusion_errors(context)
        elif not errors:
            try:
                source = sources(application, configuration, context)
                review = accepted_review(application, configuration, source)
            except ValidationError as error:
                errors.extend(error.messages)
        if application.status != 'INELIGIBLE' and application.submitted_at > program.registration_closes_at:
            errors.append('APPLICATION_SUBMITTED_AFTER_APPROVED_CLOSE')
        rows.append({'application': str(application.pk), 'reference': application.public_reference,
            'status': application.status, 'errors': sorted(set(errors)), 'source': context,
            'membership': not errors, 'evidence': bool(review), 'pr': bool(review)})
        if errors:
            problems.extend(str(application.pk) + ': ' + message for message in sorted(set(errors)))
        elif application.status == 'ELIGIBLE' and review:
            accepted[str(application.pk)] = {'inputs': source['inputs'],
                'assessments': {'registered_review': {'id': review.pk, 'digest': review.digest, 'payload': review.payload()}},
                'pr': {'eligibility_review': context['case'], 'contributes_to_score': False}}
    return rows, accepted, problems
