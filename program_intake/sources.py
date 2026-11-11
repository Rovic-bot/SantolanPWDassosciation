"""Program evidence and onsite sources, recorded through immutable EWAF artifacts."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from core.permissions import require_workspace_permissions
from documents.services import file_digest
from programs.terms import terms_lock
from programs.models import ProgramApplication, ProgramRequirement
from ewaf.evidence import VIEW, canonical, digest, source_context
from ewaf.evidence_services import persist, reasoned, locked_application
from ewaf.models import CriterionAssessment
from ewaf.operational_models import OperationalConfiguration
from ewaf.operational_services import latest_configuration
from ewaf.source_invalidation import source_writer
from .models import SocioeconomicReview

CONTRACT = 'verified_program_intake_v1'


def uses_sources(configuration):
    return bool(configuration and configuration.policy.get('source_contract') == CONTRACT)


def configured(program):
    if not getattr(settings, 'PROGRAM_INTAKE_ENABLED', False):
        return None
    return OperationalConfiguration.objects.filter(program=program).first()


def required_criteria(application):
    row = configured(application.program)
    return ('SI', 'ES', 'PA', 'ND') if uses_sources(row) and not row.policy.get('eligibility') else ('SI', 'ES', 'PA', 'ND', 'PR')


def policy_findings(proposal):
    if proposal.get('source_contract') != CONTRACT:
        return []
    errors = []
    expected = {'SI': 'socioeconomic_assessment', 'ES': 'employment_status',
                'PA': 'successful_releases', 'ND': 'dependent_count'}
    for code, source in expected.items():
        if proposal.get('criteria', {}).get(code, {}).get('source_type') != source:
            errors.append(code + ': this source contract requires ' + source)
    if type(proposal.get('si_requirement')) is not int:
        errors.append('SI: select the configured socioeconomic document requirement')
    if not isinstance(proposal.get('eligibility'), dict) or set(proposal.get('eligibility', {})) - {
            'functional_need', 'consent', 'accessible_alternative'}:
        errors.append('PR: explicitly record only applicable additional eligibility requirements')
    return errors


def validate_configuration(program, proposed, evidence):
    if proposed.get('source_contract') != CONTRACT:
        return
    errors = policy_findings(proposed)
    requirement = ProgramRequirement.objects.filter(pk=proposed.get('si_requirement'), program=program,
        is_active=True, is_required=True, kind='document').first()
    if not requirement:
        errors.append('SI: a required active program document must be configured before applications open')
    # An explicit optional-eligibility policy cannot silently discard an existing rubric.
    rubric = evidence.snapshot['criteria']['PR'].get('rubric_definition') or {}
    required = {item['id'] for item in rubric.get('items', [])}
    retained = {rule.get('item') for rule in proposed.get('eligibility', {}).values()}
    if required != retained:
        errors.append('PR: retain every genuinely required authorized rubric item')
    for code, kind in (('SI', 'decimal'), ('ES', 'category'), ('PA', 'integer'), ('ND', 'integer')):
        if proposed['criteria'][code].get('value_type') != kind:
            errors.append(code + ': incompatible measurement type')
    if errors:
        raise ValidationError(errors)


def measurement(configuration):
    return {'source_contract': CONTRACT, 'requirement': configuration.policy['si_requirement'],
        'definition': configuration.policy['criteria']['SI'],
        'evidence_policy': configuration.evidence_policy_id,
        'evidence_digest': configuration.evidence_policy.digest}


def si_document(application, configuration):
    requirement = configuration.policy['si_requirement']
    expected = next((r for r in application.requirements_snapshot if r['id'] == requirement), None)
    document = application.documents.filter(requirement_id=requirement).first()
    if not expected or not expected['is_required'] or expected['kind'] != 'document' or not document:
        raise ValidationError('SI: the required program socioeconomic document is missing.')
    return document


def si_source(application, configuration, document):
    value = file_digest(document)
    if not value:
        raise ValidationError('SI: the protected document is unavailable.')
    return canonical({'member': application.member_id, 'member_version': application.member.version,
        'program': str(application.program_id), 'program_version': application.program.version,
        'application': str(application.pk), 'document': str(document.pk), 'document_digest': value,
        'measurement': measurement(configuration)})


def source_extension(application):
    if not getattr(settings, 'PROGRAM_INTAKE_ENABLED', False):
        return {}
    row = SocioeconomicReview.objects.filter(application=application).first()
    return {'program_si_review': {'id': row.pk, 'digest': row.digest}} if row else {}


def review_token(application, configuration):
    row = SocioeconomicReview.objects.filter(application=application).first()
    document = si_document(application, configuration)
    return digest({'context': source_context(application), 'source': si_source(application, configuration, document),
        'previous': row.digest if row else None, 'configuration': configuration.digest})


def validate_value(value, rule):
    if value is None or value == '':
        raise ValidationError('The verified source value is missing; missing is not zero.')
    original = value
    if rule['value_type'] == 'category':
        if value not in rule.get('encoding', {}):
            raise ValidationError('The recorded category has no authorized encoding. Review the source or policy.')
        value = rule['encoding'][value]
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not Decimal(str(rule['bounds']['lower'])) <= number <= Decimal(str(rule['bounds']['upper'])):
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('The source measurement is invalid or outside the authorized normalization bounds.') from None
    if rule['value_type'] == 'integer' and (isinstance(original, bool) or number != number.to_integral_value()):
        raise ValidationError('A verified whole-number source is required.')
    return original


def current_si(application, configuration):
    row = SocioeconomicReview.objects.filter(application=application).first()
    if not row or row.state != 'VERIFIED':
        raise ValidationError('SI: verify the submitted socioeconomic evidence before calculation.')
    row.clean()
    if row.expires_on and row.expires_on < timezone.localdate():
        raise ValidationError('SI: the verified evidence has expired.')
    document = si_document(application, configuration)
    if row.source != si_source(application, configuration, document):
        raise ValidationError('SI: the document, member record or authorized measurement changed; review again.')
    validate_value(row.value, configuration.policy['criteria']['SI'])
    return row


def actual_sources(application, configuration, context):
    member = application.member
    si = current_si(application, configuration)
    receipts = context['pa']['successful']
    if configuration.policy['pa_scope'] == 'this_program':
        ids = {str(pk) for pk in ProgramApplication.objects.filter(program=application.program).values_list('pk', flat=True)}
        receipts = [r for r in receipts if r['application_id'] in ids]
    if configuration.policy['pa_period'] == 'date_range':
        receipts = [r for r in receipts if configuration.policy['pa_start'] <= r['released_on'] <= configuration.policy['pa_end']]
    return {
        'SI': {'value': si.value, 'lineage': {'review': si.pk, 'digest': si.digest, 'payload': si.payload()}},
        'ES': {'value': member.employment_status, 'lineage': {'member': member.pk, 'version': member.version,
            'field': 'employment_status', 'value': member.employment_status}},
        'PA': {'value': len(receipts), 'lineage': {'receipts': receipts, 'scope': configuration.policy['pa_scope'],
            'period': configuration.policy['pa_period'], 'start': configuration.policy.get('pa_start'), 'end': configuration.policy.get('pa_end')}},
        'ND': {'value': member.dependents, 'lineage': {'member': member.pk, 'version': member.version,
            'field': 'dependents', 'value': member.dependents}},
    }, si


@source_writer('reference', action='g12_socioeconomicreview', application_scope=True)
@terms_lock()
def review_si(reference, *, user, expected, state, value, observation_start, observation_end, reason, confirmed):
    require_workspace_permissions(user, *VIEW, 'programs.view_programdocument', 'program_intake.review_socioeconomic')
    fields = reasoned(user, reason, confirmed)
    application = locked_application(reference)
    configuration = latest_configuration(application.program)
    if not uses_sources(configuration):
        raise ValidationError('Authorize the program’s source configuration before reviewing SI.')
    if state not in ('VERIFIED', 'DISPUTED', 'REJECTED') or expected != review_token(application, configuration):
        raise ValidationError('Sources or review changed. Reload before saving.')
    if not observation_start or not observation_end or not observation_start <= observation_end <= timezone.localdate():
        raise ValidationError('Use the evidence’s valid past/current observation period.')
    rule = configuration.evidence_policy.snapshot['criteria']['SI']
    if not rule.get('observation_rule') or not rule.get('rule_authority'):
        raise ValidationError('SI: an authorized observation-period definition is required.')
    expires = observation_end + timedelta(days=rule['freshness_days']) if rule.get('freshness_days') else None
    if state == 'VERIFIED':
        validate_value(value, configuration.policy['criteria']['SI'])
        if expires and expires < timezone.localdate():
            raise ValidationError('Expired evidence cannot be verified.')
    document = si_document(application, configuration)
    previous = SocioeconomicReview.objects.filter(application=application).first()
    return persist(SocioeconomicReview(program=application.program, application=application, document=document,
        configuration=configuration, previous=previous, revision=previous.revision + 1 if previous else 1,
        state=state, value=str(value) if value not in (None, '') else None, observation_start=observation_start,
        observation_end=observation_end, expires_on=expires, source=si_source(application, configuration, document), **fields))


@source_writer('reference', action='g12_criterionassessment', application_scope=True)
@terms_lock()
def collect_sources(reference, *, user, expected, reason, confirmed):
    require_workspace_permissions(user, *VIEW, 'ewaf.review_criterionassessment', 'program_intake.review_socioeconomic')
    fields = reasoned(user, reason, confirmed)
    application = locked_application(reference)
    configuration = latest_configuration(application.program)
    if not uses_sources(configuration):
        raise ValidationError('This program requires its retained evidence review workflow.')
    if application.status not in ('PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW', 'NEEDS_INFORMATION', 'ELIGIBLE'):
        raise ValidationError('Complete identity review or return the application for authorized reassessment first.')
    context = source_context(application)
    if expected != digest(context):
        raise ValidationError('Sources changed. Reload before verifying the onsite values.')
    values, si = actual_sources(application, configuration, context)
    result = []
    for code in ('SI', 'ES', 'PA', 'ND'):
        rule = configuration.policy['criteria'][code]
        value = validate_value(values[code]['value'], rule)
        manifest = canonical({'evidence_contract_version': 3, 'context': context,
            'policy_digest': configuration.evidence_policy.digest, 'source_type': rule['source_type'],
            'original_value': value, 'lineage': values[code]['lineage'],
            'measurement_digest': digest(rule)})
        previous = CriterionAssessment.objects.filter(application=application, criterion=code).first()
        # Repeated confirmation of unchanged evidence does not manufacture history.
        if previous and previous.state == 'VERIFIED' and previous.source_manifest == manifest and previous.value == value:
            result.append(previous)
            continue
        result.append(persist(CriterionAssessment(program=application.program, application=application,
            criterion=code, revision=previous.revision + 1 if previous else 1, previous=previous,
            policy=configuration.evidence_policy, state='VERIFIED', value=value, value_type=rule['value_type'],
            unit=rule['unit'], source_type=rule['source_type'], observation_start=si.observation_start if code == 'SI' else timezone.localdate(),
            observation_end=si.observation_end if code == 'SI' else timezone.localdate(),
            expires_on=si.expires_on if code == 'SI' else None, disputed=False,
            source_manifest=manifest, source_digest=digest(manifest), supporting_reviews=[], **fields)))
    return result


def validate_assessment(row, application, context):
    configuration = latest_configuration(application.program)
    if not uses_sources(configuration) or row.criterion not in ('SI', 'ES', 'PA', 'ND'):
        raise ValidationError('Unrecognized source evidence contract.')
    values, si = actual_sources(application, configuration, context)
    rule = configuration.policy['criteria'][row.criterion]
    expected = values[row.criterion]
    validate_value(expected['value'], rule)
    if (row.value != expected['value'] or row.source_manifest.get('lineage') != canonical(expected['lineage'])
            or row.source_manifest.get('measurement_digest') != digest(rule)
            or row.policy_id != configuration.evidence_policy_id):
        raise ValidationError('Verified source or measurement changed; refresh the source assessment.')


def program_gate(application, configuration):
    from ewaf.four_pool import eligibility
    if uses_sources(configuration) and not configuration.policy['eligibility']:
        from programs.services import require_disability
        require_disability(application.program, application.member)
        return {'disabilities': application.member.disability_ids,
            'qualifications': list(application.program.eligible_disability_types.values_list('pk', flat=True)),
            'additional_requirements': {}, 'contributes_to_score': False}
    pr = CriterionAssessment.objects.filter(application=application, criterion='PR').first()
    if not pr or pr.policy_id != configuration.evidence_policy_id:
        raise ValidationError('PR: current verified functional-need assessment required')
    pr.clean()
    return eligibility(pr, configuration.policy['eligibility'])


def has_additional_eligibility(application):
    configuration = configured(application.program)
    if uses_sources(configuration):
        # Validate current authorization before dispensing with extra review.
        configuration = latest_configuration(application.program)
        return bool(configuration.policy['eligibility'])
    return True
