"""Audited G12 writes; no eligibility, decision, publication or scoring side effects."""
from datetime import date, timedelta
from ewaf.source_invalidation import source_writer
from ewaf.diagnostic_invalidation import diagnostic_writer
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.permissions import require_workspace_permissions
from members.models import Member
from programs.models import Program, ProgramApplication, ProgramLog, ProgramApprovalControl
from programs.terms import terms_lock
from .models import EvidencePolicyRevision, CriterionAssessment, EligibilityReadinessSnapshot
from .evidence_records import recording
from .evidence_rules import validate_policy_relationships, substantiate, relevance_findings
from .evidence import (VIEW, ALL_CRITERIA, approval_context, source_context, digest,
                       validate_policy, resolve_reviews, reviewed_value)


def persist(artifact):
    artifact.digest = digest(artifact.payload())
    log = ProgramLog.objects.create(program=artifact.program,
        application_id=getattr(artifact, 'application_id', None), actor=artifact.actor,
        actor_label=artifact.actor_label, action='g12_' + artifact._meta.model_name,
        notes='Private G12 evidence record retained; restricted review permission required.',
        changes={'artifact': {'before': None, 'after': artifact._meta.model_name},
                                       'digest': {'before': None, 'after': artifact.digest}})
    artifact.audit_entry = log
    with recording():
        artifact.save()
    return artifact


def reasoned(user, reason, confirmed):
    if confirmed is not True or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Explicit confirmation and an explanation of up to 2,000 characters are required.')
    return {'actor': user, 'actor_label': user.get_username(), 'reason': reason.strip()}


def locked_application(reference):
    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
    program = Program.objects.select_for_update().get(pk=program_id)
    application = ProgramApplication.objects.select_for_update().get(pk=reference)
    member = Member.objects.select_for_update().get(pk=application.member_id)
    application.program, application.member = program, member
    return application


@source_writer("program_id", action="g12_evidencepolicyrevision")
@terms_lock()
def record_policy(program_id, *, user, snapshot, authority_reference, expected_revision,
                  expected_context, reason, confirmed):
    require_workspace_permissions(user, *VIEW, 'ewaf.record_evidencepolicyrevision')
    actor = reasoned(user, reason, confirmed)
    validate_policy(snapshot)
    if not isinstance(authority_reference, str) or not authority_reference.strip() or len(authority_reference) > 500:
        raise ValidationError('Record the authority reference; this does not activate the policy.')
    program = Program.objects.select_for_update().get(pk=program_id)
    validate_policy_relationships(snapshot, program)
    latest = EvidencePolicyRevision.objects.filter(program=program).first()
    actual_context = {'program_version': program.version, 'approval': approval_context(program)}
    if expected_revision != (latest.revision if latest else 0) or expected_context != digest(actual_context):
        raise ValidationError('Policy or program authority changed. Reload before recording.')
    control = ProgramApprovalControl.objects.filter(program=program).first()
    return persist(EvidencePolicyRevision(program=program, revision=expected_revision + 1,
        snapshot=snapshot, authority_reference=authority_reference.strip(),
        terms_revision_id=control.current_revision_id if control else None,
        terms_digest=control.current_digest if control else '', **actor))


@source_writer("reference", action="g12_criterionassessment", application_scope=True)
@terms_lock()
def record_assessment(reference, *, user, criterion, policy_id, state, source_type,
                      value, expected_revision, expected_context, reason, confirmed,
                      supporting_review_ids=None, observation_start=None, observation_end=None,
                      disputed=False, rubric_findings=None, rubric_attested=False):
    permission = 'ewaf.declare_criterionassessment' if state == 'DECLARED' else 'ewaf.review_criterionassessment'
    require_workspace_permissions(user, *VIEW, permission)
    actor = reasoned(user, reason, confirmed)
    if criterion not in ALL_CRITERIA or state not in dict(CriterionAssessment.STATES) or type(disputed) is not bool:
        raise ValidationError('Select a supported criterion and evidence state.')
    if state == 'VERIFIED' and disputed:
        raise ValidationError('Disputed evidence cannot be recorded as verified.')
    application = locked_application(reference)
    # Final cases stay diagnostic-only until B2/B3 defines reassessment.
    if application.status not in ('PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED', 'NEEDS_INFORMATION', 'ELIGIBILITY_REVIEW', 'ELIGIBLE'):
        raise ValidationError('Historical or final applications require a separately authorized reassessment workflow.')
    policy = EvidencePolicyRevision.objects.filter(pk=policy_id, program=application.program).first()
    latest_policy = EvidencePolicyRevision.objects.filter(program=application.program).first()
    latest = CriterionAssessment.objects.filter(application=application, criterion=criterion).first()
    if not policy or policy != latest_policy or expected_revision != (latest.revision if latest else 0):
        raise ValidationError('Policy or criterion review changed. Reload before recording.')
    policy.clean()
    context = source_context(application)
    if expected_context != digest(context):
        raise ValidationError('SOURCE_CHANGED: sources or approval context changed. Reload before recording.')
    today = timezone.localdate()
    if criterion not in policy.snapshot['criteria']:
        raise ValidationError('This criterion is not defined by the current evidence policy.')
    rule = policy.snapshot['criteria'][criterion]
    reviews = resolve_reviews(application, supporting_review_ids or [], at=today)
    if source_type == 'successful_releases':
        if value is not None and str(value) != str(context['pa']['count']):
            raise ValidationError('PA must match the server-resolved successful release count.')
        value = context['pa']['count']
    value, value_type, original = reviewed_value(application, criterion, source_type, value, rule)
    mappings, relevance = [], None
    if state == 'VERIFIED':
        if value is None:
            raise ValidationError('Missing evidence cannot be verified; zero must be explicitly reviewed.')
        validate_policy_relationships(policy.snapshot, application.program)
        if criterion in ('SI', 'ES', 'ND', 'HI', 'HM'):
            mappings = substantiate(reviews, rule.get('evidence_mappings', {}).get(source_type))
        if criterion == 'PR':
            relevance = relevance_findings(application, policy, context, rubric_findings, rubric_attested, today)
        if criterion == 'PA' and rule.get('pa_scope') != 'all_retained_successful_releases':
            raise ValidationError('PA scope is unresolved or unsupported. Record a declaration or pending diagnostic review.')
    if any(item is not None and type(item) is not date for item in (observation_start, observation_end)):
        raise ValidationError('Observation dates must be validated dates.')
    if observation_start or observation_end:
        if not rule.get('observation_rule') or not rule.get('rule_authority'):
            raise ValidationError('Observation dates require a separately documented rule and authority.')
        if not observation_start or (observation_end and observation_end < observation_start) or observation_start > today or (observation_end and observation_end > today):
            raise ValidationError('Use a valid past/current observation date or period.')
    expires_on = None
    if rule.get('freshness_days'):
        if not observation_start:
            raise ValidationError('This recorded freshness rule requires an observation date.')
        expires_on = (observation_end or observation_start) + timedelta(days=rule['freshness_days'])
        if state == 'VERIFIED' and expires_on < today:
            raise ValidationError('Expired evidence cannot receive a current verified finding.')
    manifest = {'context': context, 'source_type': source_type, 'original_value': original,
                'supporting_reviews': reviews, 'policy_digest': policy.digest,
                'evidence_contract_version': 2, 'evidence_mappings': mappings, 'relevance': relevance}
    return persist(CriterionAssessment(program=application.program, application=application,
        criterion=criterion, revision=expected_revision + 1, previous=latest, policy=policy,
        state=state, value=value, value_type=value_type, unit=rule.get('unit', ''), source_type=source_type,
        observation_start=observation_start, observation_end=observation_end, expires_on=expires_on,
        disputed=disputed, source_manifest=manifest, source_digest=digest(manifest),
        supporting_reviews=reviews, **actor))


@diagnostic_writer('reference')
@terms_lock()
def record_readiness(reference, *, user, expected_context, expected_assessments, reason, confirmed):
    require_workspace_permissions(user, *VIEW, 'ewaf.record_eligibilityreadinesssnapshot')
    actor = reasoned(user, reason, confirmed)
    application = locked_application(reference)
    from .readiness import evaluate
    result = evaluate(application)
    actual = {row['criterion']: row['assessment'] for row in result['criteria']}
    if result['context_digest'] != expected_context or actual != expected_assessments:
        raise ValidationError('Readiness sources or criterion reviews changed. Reload before retaining a snapshot.')
    return persist(EligibilityReadinessSnapshot(program=application.program, application=application,
        source_manifest=result['source_manifest'], result=result, **actor))
