"""G14 preparatory writes. No operational authorization or applicant mutations."""
from ewaf.source_invalidation import source_writer
from django.core.exceptions import ValidationError
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramLog
from programs.terms import terms_lock
from .models import (EvidencePolicyRevision, ConfigurationRevision, ConfigurationValidation,
                     ConfigurationReview, ConfigurationAuthorizationEvidence)
from .evidence import approval_context, digest
from .configuration_records import recording, artifact_digest, AUDIT_NOTE
from .ahp_validation import CRITERIA, METHOD, PROFILE, ENGINE, safe_payload, validate_ahp

VIEW = ('programs.view_program', 'programs.view_programtermsrevision', 'ewaf.view_evidencepolicyrevision',
        'ewaf.view_configurationrevision', 'ewaf.view_configurationvalidation',
        'ewaf.view_configurationreview', 'ewaf.view_configurationauthorizationevidence')


def source_context(program):
    policy = EvidencePolicyRevision.objects.filter(program=program).first()
    return {'program': str(program.pk), 'program_version': program.version,
            'approval': approval_context(program), 'policy': policy.pk if policy else None,
            'policy_digest': policy.digest if policy else ''}


def configuration_context(program):
    """Pure database reads. No mutex/control creation on GET."""
    current = ConfigurationRevision.objects.filter(program=program).first()
    context = {'source': source_context(program), 'configuration': current.pk if current else None,
               'configuration_digest': current.digest if current else '', 'histories': {}}
    if current:
        for name in ('validations', 'reviews', 'authority_evidence'):
            latest = getattr(current, name).first()
            context['histories'][name] = {'id': latest.pk, 'digest': latest.digest} if latest else None
    return context


def prepare(program_id, user, permission, expected_context, reason, confirmed):
    require_workspace_permissions(user, *VIEW, permission)
    if confirmed is not True or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Explicit confirmation and a reason of up to 2,000 characters are required.')
    program = Program.objects.select_for_update().get(pk=program_id)
    context = configuration_context(program)
    if expected_context != digest(context):
        raise ValidationError('CONFIGURATION_CONTEXT_CHANGED: reload the program and configuration history.')
    return program, context, {'actor': user, 'actor_label': user.get_username(), 'reason': reason.strip()}


def persist(row):
    row.digest = artifact_digest(row.payload())
    row.audit_entry = ProgramLog.objects.create(program=row.program, actor=row.actor, actor_label=row.actor_label,
        action='g14_' + row._meta.model_name, notes=AUDIT_NOTE,
        changes={'artifact': {'before': None, 'after': row._meta.model_name}, 'digest': {'before': None, 'after': row.digest}})
    with recording():
        row.save()
    return row


def predecessor(model, **scope):
    latest = model.objects.filter(**scope).first()
    return {'previous': latest, 'revision': latest.revision + 1 if latest else 1}


@source_writer("program_id", action="g14_configurationrevision")
@terms_lock()
def record_configuration(program_id, *, user, judgments, policy_id, expected_context, reason, confirmed):
    program, context, actor = prepare(program_id, user, 'ewaf.record_configurationrevision', expected_context, reason, confirmed)
    source = context['source']
    if policy_id != source['policy'] or type(policy_id) not in (int, type(None)):
        raise ValidationError('Select the current evidence-policy revision of this program.')
    policy = EvidencePolicyRevision.objects.filter(pk=policy_id, program=program).first() if policy_id else None
    if policy:
        policy.clean()
    judgments = safe_payload(judgments)
    report = validate_ahp(judgments)
    return persist(ConfigurationRevision(program=program, **predecessor(ConfigurationRevision, program=program),
        criteria_order=list(CRITERIA), judgments=judgments, canonical_judgments=report['canonical_input'],
        method=METHOD, profile=PROFILE, policy=policy, policy_digest=source['policy_digest'],
        terms_revision_id=source['approval']['terms_revision'], terms_digest=source['approval']['terms_digest'],
        source_context=source, **actor))


def current_configuration(program, context, configuration_id):
    row = ConfigurationRevision.objects.select_for_update().filter(pk=configuration_id, program=program).first()
    if not row or row.pk != context['configuration'] or row.source_context != context['source']:
        raise ValidationError('CONFIGURATION_STALE: record a new draft against current policy and terms.')
    row.clean()
    if row.policy:
        row.policy.clean()
    return row


@source_writer("program_id", action="g14_configurationvalidation")
@terms_lock()
def record_validation(program_id, *, user, configuration_id, expected_context, reason, confirmed):
    program, context, actor = prepare(program_id, user, 'ewaf.record_configurationvalidation', expected_context, reason, confirmed)
    configuration = current_configuration(program, context, configuration_id)
    return persist(ConfigurationValidation(program=program, configuration=configuration,
        configuration_digest=configuration.digest, engine=ENGINE, profile=PROFILE,
        result=validate_ahp(configuration.judgments),
        **predecessor(ConfigurationValidation, configuration=configuration), **actor))


def reviewed_references(program, context, configuration_id, validation_id):
    configuration = current_configuration(program, context, configuration_id)
    validation = ConfigurationValidation.objects.select_for_update().filter(pk=validation_id, configuration=configuration, program=program).first()
    latest = configuration.validations.first()
    if not validation or validation != latest:
        raise ValidationError('Select the latest validation of this exact configuration.')
    validation.clean()
    return {'configuration': configuration, 'configuration_digest': configuration.digest,
            'validation': validation, 'validation_digest': validation.digest}


@source_writer("program_id", action="g14_configurationreview")
@terms_lock()
def record_review(program_id, *, user, configuration_id, validation_id, finding, correction_requests,
                  expected_context, reason, confirmed):
    program, context, actor = prepare(program_id, user, 'ewaf.record_configurationreview', expected_context, reason, confirmed)
    if not isinstance(finding, str) or not isinstance(correction_requests, str):
        raise ValidationError('Review findings and correction requests must be text.')
    references = reviewed_references(program, context, configuration_id, validation_id)
    return persist(ConfigurationReview(program=program, finding=finding, correction_requests=correction_requests,
        **references, **predecessor(ConfigurationReview, configuration=references['configuration']), **actor))


@source_writer("program_id", action="g14_configurationauthorizationevidence")
@terms_lock()
def record_authority_evidence(program_id, *, user, configuration_id, validation_id, authority_reference,
                              stated_scope, attested, expected_context, reason, confirmed):
    program, context, actor = prepare(program_id, user, 'ewaf.record_configurationauthorizationevidence', expected_context, reason, confirmed)
    if attested is not True or not isinstance(authority_reference, str) or not isinstance(stated_scope, str):
        raise ValidationError('Documentary reference, scope and explicit attestation are required.')
    references = reviewed_references(program, context, configuration_id, validation_id)
    return persist(ConfigurationAuthorizationEvidence(program=program, authority_reference=authority_reference,
        stated_scope=stated_scope, attested=attested, **references,
        **predecessor(ConfigurationAuthorizationEvidence, configuration=references['configuration']), **actor))


def require_configuration_authorization(*args, **kwargs):
    raise ValidationError('CONFIGURATION_AUTHORIZATION_UNAVAILABLE', code='CONFIGURATION_AUTHORIZATION_UNAVAILABLE')
