"""Atomic proposal and readiness records. No synthetic calculator web service."""
from ewaf.source_invalidation import source_writer
from ewaf.diagnostic_invalidation import diagnostic_writer
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramLog
from programs.terms import terms_lock
from .models import (EvidencePolicyRevision, ConfigurationRevision, ConfigurationValidation,
                     ScoringPolicyRevision, CalculationDiagnosticRun, CalculationDiagnosticItem, CalculationCriterionTrace,
                     CriterionAssessment)
from .evidence import digest
from .evidence_services import reasoned, locked_application
from .configuration_services import configuration_context, predecessor
from .normalization import CRITERIA, ENGINE, PROFILE
from .scoring_policy import proposal
from .scoring_inputs import VIEW, READINESS_VIEW, policy_context, evaluate_application
from .scoring_records import artifact_digest, recording, AUDIT_NOTE


def persist(row):
    row.digest = artifact_digest(row.payload())
    row.audit_entry = ProgramLog.objects.create(program=row.program, application_id=row.audit_application_id,
        actor=row.actor, actor_label=row.actor_label, action='g15_' + row._meta.model_name, notes=AUDIT_NOTE,
        changes={'artifact': {'before': None, 'after': row._meta.model_name}, 'digest': {'before': None, 'after': row.digest}})
    with recording():
        row.save()
    return row


@source_writer("program_id", action="g15_scoringpolicyrevision")
@terms_lock()
def record_scoring_policy(program_id, *, user, proposed, configuration_id, validation_id,
                          evidence_policy_id, expected_context, reason, confirmed):
    require_workspace_permissions(user, *VIEW, 'ewaf.record_scoringpolicyrevision')
    actor = reasoned(user, reason, confirmed)
    snapshot = proposal(proposed)
    program = Program.objects.select_for_update().get(pk=program_id)
    context = policy_context(program)
    if digest(context) != expected_context:
        raise ValidationError('SCORING_CONTEXT_CHANGED: reload current configuration and policy.')
    current = context['configuration']
    latest_validation = current['histories'].get('validations')
    for supplied, expected in ((configuration_id, current['configuration']),
            (validation_id, latest_validation['id'] if latest_validation else None), (evidence_policy_id, current['source']['policy'])):
        if type(supplied) not in (int, type(None)) or supplied != expected:
            raise ValidationError('Use the exact current program artifacts.')
    configuration = ConfigurationRevision.objects.filter(pk=configuration_id, program=program).first()
    validation = ConfigurationValidation.objects.filter(pk=validation_id, program=program).first()
    evidence_policy = EvidencePolicyRevision.objects.filter(pk=evidence_policy_id, program=program).first()
    for row in (configuration, validation, evidence_policy):
        if row:
            row.clean()
    if configuration and configuration.source_context != current['source']:
        raise ValidationError('CONFIGURATION_STALE: record a current configuration draft first.')
    approval = current['source']['approval']
    return persist(ScoringPolicyRevision(program=program, **predecessor(ScoringPolicyRevision, program=program),
        criteria_order=list(CRITERIA), proposal=snapshot, engine=ENGINE, profile=PROFILE,
        configuration=configuration, configuration_digest=configuration.digest if configuration else '',
        validation=validation, validation_digest=validation.digest if validation else '',
        evidence_policy=evidence_policy, evidence_policy_digest=evidence_policy.digest if evidence_policy else '',
        terms_revision_id=approval['terms_revision'], terms_revision_digest=approval['terms_digest'],
        source_context=current, **actor))


@diagnostic_writer('application_id')
@terms_lock()
def record_applicant_diagnostic(application_id, *, user, program_id, expected_context, reason, confirmed):
    require_workspace_permissions(user, *READINESS_VIEW, 'ewaf.record_calculationdiagnosticrun')
    actor = reasoned(user, reason, confirmed)
    application = locked_application(application_id)
    if str(application.program_id) != str(program_id):
        raise ValidationError('Application/program ownership mismatch.')
    result = evaluate_application(application, user=user)
    if result['context_digest'] != expected_context:
        raise ValidationError('SCORING_CONTEXT_CHANGED: current evidence, policy or review changed.')
    policy = ScoringPolicyRevision.objects.filter(pk=result['policy_id'], program=application.program).first()
    if not policy:
        raise ValidationError('Record a pending scoring-policy proposal before retaining readiness.')
    policy.clean()
    traces = []
    for detail in result['criteria']:
        row = CriterionAssessment.objects.select_for_update().filter(pk=detail['assessment'], application=application).first()
        traces.append({'criterion': detail['criterion'], 'assessment_id': row.pk if row else None,
                       'assessment_digest': row.digest if row else '', 'source_digest': row.source_digest if row else '',
                       'evidence_policy_id': row.policy_id if row else None, 'evidence_policy_digest': row.policy.digest if row else '',
                       'value_type': row.value_type if row else '', 'unit': row.unit if row else '', 'current': detail['current']})
    key = str(application.pk)
    manifest = {entry['criterion']: digest(entry) for entry in traces}
    run = persist(CalculationDiagnosticRun(program=application.program, **predecessor(CalculationDiagnosticRun, program=application.program),
        policy=policy, policy_digest=policy.digest, configuration=policy.configuration, configuration_digest=policy.configuration_digest,
        validation=policy.validation, validation_digest=policy.validation_digest, mode='READINESS_ONLY', engine=ENGINE, profile=PROFILE,
        evaluation_date=timezone.localdate(), evaluation_timezone=timezone.get_current_timezone_name(), result=result,
        context_digest=result['context_digest'], item_manifest={key: digest({'result': result, 'traces': manifest})}, **actor))
    item = persist(CalculationDiagnosticItem(program=application.program, revision=1, run=run, application=application,
        item_key=key, result=result, trace_manifest=manifest, **actor))
    for entry in traces:
        persist(CalculationCriterionTrace(program=application.program, revision=1, item=item, **entry, **actor))
    validate_run(run)
    # Date and source recheck catches midnight/expiry and unsupported storage changes.
    final = evaluate_application(application, user=user)
    if final['context_digest'] != result['context_digest'] or final['criteria'] != result['criteria'] or final['reasons'] != result['reasons']:
        raise ValidationError('SCORING_CONTEXT_CHANGED during diagnostic capture.')
    return run


def validate_run(run):
    """Validate a complete retained graph; replay is historical, not current acceptance."""
    run.clean()
    items = list(run.items.all())
    if len(items) != 1 or set(run.item_manifest) != {items[0].item_key}:
        raise ValidationError('Incomplete diagnostic item set.')
    for item in items:
        item.clean()
        traces = list(item.traces.all())
        if len(traces) != 5 or {row.criterion for row in traces} != set(CRITERIA):
            raise ValidationError('Incomplete criterion trace set.')
        manifest = {}
        for row in traces:
            row.clean()
            fields = ('criterion', 'assessment_id', 'assessment_digest', 'source_digest', 'evidence_policy_id',
                      'evidence_policy_digest', 'value_type', 'unit', 'current')
            manifest[row.criterion] = digest({name: getattr(row, name) for name in fields})
        if manifest != item.trace_manifest or run.item_manifest[item.item_key] != digest({'result': item.result, 'traces': manifest}):
            raise ValidationError('Diagnostic graph manifest mismatch.')
    return run
