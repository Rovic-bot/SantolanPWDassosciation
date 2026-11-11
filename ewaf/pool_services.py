"""Complete retained-program inventory and current score-free readiness.

Schema authorization was not identified for this increment. Consequently these
services do NOT resolve an approved evaluation cutoff, calculate applicant scores,
write requests/results, or supply an operational consumption token. There is no
test-enable flag. The future durable adapter must implement the separate proposal.

Double observations detect changed source contexts; they are not transactional
promotion or an ABA-proof generation protocol. No new source-writer locks/hooks
are installed. Historical G12-G17 artifacts and guards remain untouched.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import connection
from django.utils import timezone

from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from .evidence import digest
from .models import ScoringPolicyRevision
from .pool_contracts import ENGINE, MAX_APPLICATIONS, BARRIERS, scoring_findings, require_context_digest, unavailable
from .scoring_inputs import READINESS_VIEW, evaluate_application, policy_context, validate_readiness_payload


def _reader(user):
    # Check before program/evidence reads and discard Django's cached permissions.
    require_workspace_permissions(user, *READINESS_VIEW)
    try:
        current = get_user_model().objects.get(pk=user.pk)
    except ObjectDoesNotExist:
        raise PermissionDenied from None
    require_workspace_permissions(current, *READINESS_VIEW)
    return current


def _transaction_boundary():
    # An outer REPEATABLE READ snapshot could hide a committed writer from both
    # observations. This read-only service deliberately owns no outer transaction.
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ValidationError('POOL_OBSERVATION_REQUIRES_AUTOCOMMIT',
                              code='POOL_OBSERVATION_REQUIRES_AUTOCOMMIT')


def _observe(program_id, user):
    program = Program.objects.get(pk=program_id)
    context = policy_context(program)
    policy = ScoringPolicyRevision.objects.filter(program=program).first()
    findings = scoring_findings(policy.proposal if policy else None)
    applications = ProgramApplication.objects.filter(program=program).order_by('pk')
    count = applications.count()
    date = str(timezone.localdate())
    zone = timezone.get_current_timezone_name()
    base = {'program_id': str(program.pk), 'program_version': program.version,
            'policy_context_digest': digest(context), 'policy_id': policy.pk if policy else None,
            'evaluation_date': date, 'evaluation_timezone': zone,
            'retained_application_count': count, 'manifest': [], 'items': [],
            'inventory_complete': False, 'policy_findings': findings,
            'inventory_reasons': []}
    if count > MAX_APPLICATIONS:
        base['inventory_reasons'] = ['POOL_RESOURCE_LIMIT']
        return base
    # Fetch one extra to detect a pool growing after COUNT. Never evaluate a page.
    rows = list(applications.select_related('program', 'member', 'member__application',
                                           'current_photo')[:MAX_APPLICATIONS + 1])
    if len(rows) > MAX_APPLICATIONS:
        base['inventory_reasons'] = ['POOL_RESOURCE_LIMIT', 'POOL_CONTEXT_CHANGED']
        return base
    if len(rows) != count:
        base['inventory_reasons'] = ['POOL_CONTEXT_CHANGED']
        return base
    for application in rows:
        if application.program_id != program.pk:
            raise ValidationError('POOL_ASSOCIATION_INVALID', code='POOL_ASSOCIATION_INVALID')
        # Retain ELIGIBLE markers even when their evidence/provenance is invalid.
        entry = {'application_id': str(application.pk), 'application_version': application.version,
                 'status': application.status, 'submitted_at': application.submitted_at.isoformat(),
                 'eligible_status': application.status == ProgramApplication.Status.ELIGIBLE}
        try:
            result = evaluate_application(application, user=user)
            validate_readiness_payload(result)
        except (ValidationError, ObjectDoesNotExist, OSError):
            # No exception messages, document contents or input values in output.
            entry.update(source_context_digest=None, readiness_digest=None)
            detail = {'application_id': entry['application_id'], 'readiness': None,
                      'reasons': ['SOURCE_REVIEW_UNAVAILABLE']}
        else:
            # Evaluation instants vary; date/timezone and all source/assessment
            # identities and findings participate in the digest instead.
            result = {key: value for key, value in result.items() if key != 'evaluated_at'}
            entry.update(source_context_digest=result['source_context_digest'],
                         readiness_digest=digest(result))
            detail = {'application_id': entry['application_id'], 'readiness': result, 'reasons': []}
        base['manifest'].append(entry)
        base['items'].append(detail)
    base['inventory_complete'] = True
    return base


def inspect_program_pool(program_id, *, user):
    """Inspect every retained application, never a caller-selected subset.

    All retained records are an accounting inventory, NOT an approved evaluation
    scope. Actual admission/cutoff remains unknown. This private response contains
    record identifiers and must not be published or logged wholesale.
    """
    user = _reader(user)
    _transaction_boundary()
    first = _observe(program_id, user)
    user = _reader(user)
    second = _observe(program_id, user)
    _reader(user)
    stable = (first == second and second['evaluation_date'] == str(timezone.localdate())
              and second['evaluation_timezone'] == timezone.get_current_timezone_name())
    state = second
    reasons = set(BARRIERS) | set(state['inventory_reasons'])
    if not stable:
        reasons.add('POOL_CONTEXT_CHANGED')
    if not state['retained_application_count']:
        reasons.add('EMPTY_POOL')
    inventory_complete = stable and state['inventory_complete']
    eligible = [entry['application_id'] for entry in state['manifest'] if entry['eligible_status']]
    details = {entry['application_id']: entry for entry in state['items']}
    eligibility_ready, evidence_ready, weights_ready = [], [], []
    for identity in eligible:
        readiness = details[identity]['readiness']
        if readiness:
            if readiness['eligibility_ready']:
                eligibility_ready.append(identity)
            if readiness['evidence_complete']:
                evidence_ready.append(identity)
            if readiness['weight_evidence_complete']:
                weights_ready.append(identity)
    if eligible and len(eligibility_ready) != len(eligible):
        reasons.add('ELIGIBLE_POOL_REVIEW_INCOMPLETE')
    if eligible and len(evidence_ready) != len(eligible):
        reasons.add('ELIGIBLE_POOL_EVIDENCE_INCOMPLETE')
    if eligible and len(weights_ready) != len(eligible):
        reasons.add('POOL_WEIGHT_EVIDENCE_INCOMPLETE')
    if any(entry['readiness'] is None for entry in state['items']):
        reasons.add('SOURCE_REVIEW_UNAVAILABLE')
    if state['manifest'] and len(eligible) != len(state['manifest']):
        reasons.add('NONCANDIDATE_ADMISSION_POLICY_PENDING')
    reasons.update(entry['code'] for entry in state['policy_findings'])
    report = {'schema_version': 1, 'engine': ENGINE, 'mode': 'POOL_READINESS_ONLY',
              'program_id': state['program_id'], 'inspection_scope': 'ALL_RETAINED_APPLICATIONS',
              'evaluation_scope': None, 'evaluation_cutoff': None,
              'effective_authorization': False, 'operational_ready': False,
              'calculation_complete': False, 'persisted': False,
              'inventory_complete': inventory_complete, 'observations_match': stable,
              'context_digest': digest(state) if inventory_complete else None,
              'evaluation_date': state['evaluation_date'], 'evaluation_timezone': state['evaluation_timezone'],
              'retained_application_count': state['retained_application_count'],
              'eligible_status_ids': eligible, 'eligibility_ready_ids': eligibility_ready,
              'evidence_ready_ids': evidence_ready, 'weight_evidence_ready_ids': weights_ready,
              'policy_id': state['policy_id'], 'policy_context_digest': state['policy_context_digest'],
              'policy_findings': state['policy_findings'], 'manifest': state['manifest'],
              'items': state['items'], 'reasons': sorted(reasons)}
    # A torn observation is not a report on a stable pool. Expose no subset as
    # ready and no token that a later service could mistake for a usable capture.
    if not inventory_complete:
        for key in ('eligible_status_ids', 'eligibility_ready_ids', 'evidence_ready_ids',
                    'weight_evidence_ready_ids', 'manifest', 'items'):
            report[key] = []
    return report


def recheck_program_pool(program_id, *, user, expected_context_digest):
    """Fresh diagnostic comparison only, never validate a stored snapshot as authority."""
    user = _reader(user)
    require_context_digest(expected_context_digest)
    current = inspect_program_pool(program_id, user=user)
    if current['context_digest'] != expected_context_digest:
        raise ValidationError('POOL_CONTEXT_CHANGED', code='POOL_CONTEXT_CHANGED')
    return current


def request_recalculation(program_id, *, user, reason, expected_context_digest, request_key):
    """Reserved contract; no requests exist until durable schema is authorized."""
    require_workspace_permissions(user, *READINESS_VIEW)
    unavailable()


def process_recalculation(request_id, *, user):
    require_workspace_permissions(user, *READINESS_VIEW)
    unavailable()


def current_pool_result(program_id, *, user):
    require_workspace_permissions(user, *READINESS_VIEW)
    unavailable()
