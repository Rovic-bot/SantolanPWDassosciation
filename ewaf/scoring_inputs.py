"""Permission-checked provenance adapters. Applicant output is never numerical."""
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from .configuration_services import VIEW as CONFIG_VIEW, configuration_context
from .evidence import VIEW as EVIDENCE_VIEW, digest, source_context
from .models import ScoringPolicyRevision, CriterionAssessment
from .normalization import CRITERIA, NumericIssue
from .weighted_scoring import replay_weights
from .scoring_policy import BARRIERS, proposal_reasons

VIEW = (*CONFIG_VIEW, 'ewaf.view_scoringpolicyrevision')
READINESS_VIEW = tuple(dict.fromkeys((*VIEW, *EVIDENCE_VIEW, 'ewaf.view_calculationdiagnosticrun',
                                    'ewaf.view_calculationdiagnosticitem', 'ewaf.view_calculationcriteriontrace')))


def policy_context(program):
    latest = ScoringPolicyRevision.objects.filter(program=program).first()
    return {'configuration': configuration_context(program), 'policy': latest.pk if latest else None,
            'policy_digest': latest.digest if latest else ''}


def evidence_token(application, context=None):
    context = context if context is not None else source_context(application)
    rows = [CriterionAssessment.objects.filter(application=application, criterion=code).first() for code in CRITERIA]
    return digest({'source': digest(context), 'policies': policy_context(application.program),
                   'assessments': [[row.pk, row.digest] if row else None for row in rows],
                   'date': str(timezone.localdate()), 'timezone': timezone.get_current_timezone_name()})


def weight_evidence(policy, *, user):
    """Exact artifacts, audit associations and full replay; no client calculations."""
    require_workspace_permissions(user, *VIEW)
    if not policy.configuration_id or not policy.validation_id or not policy.evidence_policy_id:
        raise ValidationError('WEIGHT_SOURCE_INVALID', code='WEIGHT_SOURCE_INVALID')
    program = Program.objects.get(pk=policy.program_id)
    latest = ScoringPolicyRevision.objects.filter(program=program).first()
    if not latest or latest.pk != policy.pk or policy.source_context != configuration_context(program):
        raise ValidationError('SCORING_POLICY_STALE', code='SCORING_POLICY_STALE')
    policy.clean()
    policy.evidence_policy.clean()
    policy.configuration.clean()
    policy.validation.clean()
    from . import four_policy
    if policy.profile == four_policy.PROFILE:
        # Mathematical evidence only; readiness below still has all barriers.
        result = four_policy.ahp(policy.configuration.judgments)
        if result != policy.validation.result or result['reference_consistency'] != 'PASSED':
            raise ValidationError('FOUR_WEIGHT_REPLAY_INVALID')
        return result['weights']
    try:
        return replay_weights(policy.configuration.judgments, policy.validation.result)
    except NumericIssue as error:
        raise ValidationError(str(error), code=str(error)) from error


def applicant_readiness(application_id, *, user, program_id=None):
    require_workspace_permissions(user, *READINESS_VIEW)
    application = ProgramApplication.objects.select_related('program', 'member').get(pk=application_id)
    if program_id is not None and str(application.program_id) != str(program_id):
        raise ValidationError('Application does not belong to the requested program.')
    return evaluate_application(application, user=user)


def evaluate_application(application, *, user):
    require_workspace_permissions(user, *READINESS_VIEW)
    from .readiness import evaluate
    context = source_context(application)
    g12 = evaluate(application, context=context)
    policy = ScoringPolicyRevision.objects.filter(program=application.program).first()
    reasons = [entry for group in g12['reasons'].values() for entry in group]
    mathematical = False
    if not policy:
        reasons.append({'code': 'SCORING_POLICY_MISSING', 'source': None})
    else:
        if policy.source_context != configuration_context(application.program):
            reasons.append({'code': 'SCORING_POLICY_STALE', 'source': policy.pk})
        reasons.extend(proposal_reasons(policy.proposal))
        try:
            weight_evidence(policy, user=user)
            mathematical = True
        except ValidationError:
            reasons.append({'code': 'WEIGHT_SOURCE_INVALID', 'source': policy.pk})
        for entry in g12['criteria']:
            if entry['criterion'] not in policy.proposal['criteria']:
                # PR remains in G12 eligibility evidence, never a four-input score.
                continue
            if entry['assessment']:
                row = CriterionAssessment.objects.get(pk=entry['assessment'], application=application)
                definition = policy.proposal['criteria'][entry['criterion']]
                if (row.policy_id != policy.evidence_policy_id or row.policy.digest != policy.evidence_policy_digest or
                        definition.get('source_type') != row.source_type or definition.get('unit') != row.unit or
                        definition.get('value_type') != row.value_type):
                    reasons.append({'code': 'MEASURE_OR_UNIT_MISMATCH', 'source': row.pk})
                if row.value_type in ('category', 'text') and (not isinstance(row.value, str) or row.value not in (definition.get('encoding') or {})):
                    reasons.append({'code': 'ENCODING_UNAVAILABLE', 'source': row.pk})
    for code in BARRIERS:
        if not any(entry['code'] == code for entry in reasons):
            reasons.append({'code': code, 'source': None})
    result = {'schema_version': 1, 'mode': 'READINESS_ONLY',
              'eligibility_ready': g12['eligibility_readiness'], 'evidence_complete': g12['criterion_completeness'],
              'weight_evidence_complete': mathematical, 'effective_authorization': False, 'operational_ready': False,
              'mathematical_readiness': 'UNAVAILABLE_FOR_APPLICANTS',
              'criteria': g12['criteria'], 'reasons': reasons, 'context_digest': evidence_token(application, context),
              'source_context_digest': digest(context), 'policy_id': policy.pk if policy else None,
              'evaluation_date': str(timezone.localdate()), 'evaluation_timezone': timezone.get_current_timezone_name(),
              'evaluated_at': timezone.now().isoformat()}
    validate_readiness_payload(result)
    return result


def validate_readiness_payload(result):
    fields = {'schema_version', 'mode', 'eligibility_ready', 'evidence_complete', 'weight_evidence_complete',
              'effective_authorization', 'operational_ready', 'criteria', 'reasons', 'context_digest',
              'source_context_digest', 'policy_id', 'evaluation_date', 'evaluation_timezone', 'evaluated_at'}
    fields.add('mathematical_readiness')
    if not isinstance(result, dict) or set(result) != fields or result['schema_version'] != 1 or result['mode'] != 'READINESS_ONLY':
        raise ValidationError('Applicant diagnostics permit only the readiness schema, never numerical scores.')
    if result['effective_authorization'] is not False or result['operational_ready'] is not False:
        raise ValidationError('Operational authorization is unavailable.')
    if (result['mathematical_readiness'] != 'UNAVAILABLE_FOR_APPLICANTS' or
            any(type(result[key]) is not bool for key in ('eligibility_ready', 'evidence_complete', 'weight_evidence_complete'))):
        raise ValidationError('Applicant mathematical output is unavailable.')
    if (not isinstance(result['criteria'], list) or len(result['criteria']) != 5 or
            [entry.get('criterion') for entry in result['criteria']] != list(CRITERIA)):
        raise ValidationError('Exactly five ordered readiness findings are required.')
    for entry in result['criteria']:
        if (set(entry) != {'criterion', 'assessment', 'state', 'current'} or type(entry['current']) is not bool or
                type(entry['assessment']) not in (int, type(None)) or entry['state'] not in ('MISSING', 'DECLARED', 'NEEDS_REVIEW', 'VERIFIED', 'REJECTED')):
            raise ValidationError('Unexpected criterion readiness payload.')
    for entry in result['reasons']:
        if set(entry) != {'code', 'source'} or not isinstance(entry['code'], str) or type(entry['source']) not in (str, int, type(None)):
            raise ValidationError('Unexpected diagnostic reason payload.')
    if not set(BARRIERS) <= {entry['code'] for entry in result['reasons']}:
        raise ValidationError('Governance barriers must remain explicit.')
