"""Isolated development orchestration. Operational consumption always denied.

Successful graph transaction: Terms -> Program -> all Applications (PK) ->
distinct Members (PK). Requests/attempts commit separately before calculation.
Failure outcomes commit only after the failed graph transaction has rolled back.
No caller-selected applicant list, no operational approval inference.
"""
import re
from datetime import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.utils import timezone
from core.permissions import require_workspace_permissions
from assistance.models import EligibilityStatus
from members.models import Member
from programs.models import Program, ProgramApplication, ProgramLog
from programs.terms import terms_lock
from .durable_models import DurableRequest, DurableAttempt, DurableRun, DurableResult, DurableTrace, DurableOutcome
from .durable_records import recording, AUDIT_NOTE
from .evidence import canonical, digest, source_context
from .evidence_services import reasoned
from .models import ScoringPolicyRevision, CriterionAssessment
from .normalization import CRITERIA, number
from .pool_contracts import MAX_APPLICATIONS
from .readiness import evaluate
from .scoring_inputs import READINESS_VIEW, policy_context, weight_evidence
from .scoring_policy import proposal_reasons
from .weighted_scoring import calculate_values
from . import source_freshness

ENGINE = 'durable-pool-development-1'
PERMISSION = 'ewaf.process_durablerequest'


def _authorize(user):
    require_workspace_permissions(user, *READINESS_VIEW, PERMISSION)
    # Do not trust Django's per-instance permission cache after revocation.
    user = get_user_model().objects.get(pk=user.pk)
    require_workspace_permissions(user, *READINESS_VIEW, PERMISSION)
    from scripts.durable_test_runner import require_disposable
    require_disposable()
    return user


def _boundary():
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ValidationError('Use a top-level durable service transaction.')


def _contract(value):
    from .four_policy import PROFILE
    if isinstance(value, dict) and value.get('profile') == PROFILE:
        return _contract({key: item for key, item in value.items() if key != 'profile'})
    required = {'purpose', 'version', 'scope', 'cutoff', 'pending', 'comparison', 'repeat_rule'}
    if not isinstance(value, dict) or set(value) != required or value != canonical(value):
        raise ValidationError('EVALUATION_POLICY_INCOMPLETE')
    if (value['purpose'] != 'FICTIONAL_DISPOSABLE_TEST' or value['version'] != 1 or
            value['scope'] != 'submitted_at_or_before_cutoff' or value['pending'] != 'block' or
            value['comparison'] != 'descending_exact_ties' or value['repeat_rule'] != 'explicit_test_request'):
        raise ValidationError('UNSUPPORTED_TEST_POLICY')
    try:
        cutoff = datetime.fromisoformat(value['cutoff'])
        if timezone.is_naive(cutoff):
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError('EVALUATION_CUTOFF_REQUIRED')
    return cutoff


def _locks(program_id):
    program = Program.objects.select_for_update().get(pk=program_id)
    if ProgramApplication.objects.filter(program=program).count() > MAX_APPLICATIONS:
        raise ValidationError('WHOLE_POOL_UNSUPPORTED')
    applications = list(ProgramApplication.objects.select_for_update().filter(program=program).order_by('pk'))
    members = {row.pk: row for row in Member.objects.select_for_update().filter(
        pk__in={row.member_id for row in applications}).order_by('pk')}
    for row in applications:
        row.program, row.member = program, members[row.member_id]
    list(EligibilityStatus.objects.select_for_update().order_by('pk'))
    return program, applications


def _capture_legacy(program, applications, contract, user):
    cutoff = _contract(contract)
    policy = ScoringPolicyRevision.objects.filter(program=program).first()
    if not policy:
        raise ValidationError('SCORING_POLICY_MISSING')
    from .four_policy import PROFILE
    if policy.profile == PROFILE:
        raise ValidationError('FOUR_REQUEST_PROFILE_REQUIRED')
    findings = proposal_reasons(policy.proposal)
    if findings:
        raise ValidationError(sorted({entry['code'] for entry in findings}))
    weight_evidence(policy, user=user)
    snapshot = {'engine': ENGINE, 'contract': contract, 'program': str(program.pk),
        'policy': {'id': policy.pk, 'digest': policy.digest, 'payload': policy.payload()},
        'configuration': policy.configuration.payload(), 'validation': policy.validation.payload(),
        'evidence_policy': policy.evidence_policy.payload(), 'context': policy_context(program),
        'evaluation_date': str(timezone.localdate()), 'timezone': timezone.get_current_timezone_name(),
        'manifest': [], 'eligible': {}}
    for application in applications:
        source = source_context(application)
        ready = evaluate(application, context=source)
        admitted = application.submitted_at <= cutoff
        entry = {'application': str(application.pk), 'in_scope': admitted, 'status': application.status,
                 'source_digest': digest(source), 'eligibility_ready': ready['eligibility_readiness'],
                 'evidence_complete': ready['criterion_completeness'], 'readiness_reasons': ready['reasons']}
        snapshot['manifest'].append(entry)
        if not admitted:
            continue
        if application.status not in ('ELIGIBLE', 'INELIGIBLE'):
            raise ValidationError('ELIGIBILITY_UNRESOLVED')
        if application.status == 'INELIGIBLE':
            case = source['case']
            if (not case or case['eligibility'] != 'ineligible' or not case['active'] or
                    not case['log_matches'] or case['member_version'] != source['member_version'] or
                    case['program_version'] != source['program_version'] or case['decision'] != 'pending'):
                raise ValidationError('INELIGIBLE_OUTCOME_STALE_OR_UNVERIFIED')
            continue
        if not ready['eligibility_readiness'] or not ready['criterion_completeness']:
            raise ValidationError('ELIGIBLE_POOL_EVIDENCE_INCOMPLETE')
        assessments, inputs = {}, {}
        for code in CRITERIA:
            row = CriterionAssessment.objects.filter(application=application, criterion=code).first()
            row.clean()
            definition = policy.proposal['criteria'][code]
            if row.policy_id != policy.evidence_policy_id or any(
                    getattr(row, key) != definition.get(key) for key in ('source_type', 'value_type', 'unit')):
                raise ValidationError('ASSESSMENT_POLICY_MISMATCH')
            assessments[code] = {'id': row.pk, 'digest': row.digest, 'payload': row.payload()}
            inputs[code] = {'source_type': row.source_type, 'unit': row.unit, 'value': row.value}
        snapshot['eligible'][str(application.pk)] = {'source': source, 'assessments': assessments, 'inputs': inputs}
    if not snapshot['eligible']:
        raise ValidationError('ELIGIBLE_POOL_EMPTY')
    return policy, canonical(snapshot)


def _capture(program, applications, contract, user):
    """Versioned extension; legacy snapshots and their digest inputs stay intact."""
    from . import four_policy, four_pool
    if isinstance(contract, dict) and contract.get('profile') == four_policy.PROFILE:
        return four_pool.capture(program, applications, contract, user)
    before = source_freshness.observe(program, applications, user)
    policy, snapshot = _capture_legacy(program, applications, contract, user)
    after = source_freshness.observe(program, applications, user)
    if before != after:
        raise ValidationError('SOURCE_OBSERVATION_CHANGED')
    snapshot['engine'] = source_freshness.ENGINE
    snapshot['freshness'] = after
    return policy, snapshot


def inspect_development_context(program_id, *, user, contract):
    user = _authorize(user)
    _boundary()
    with terms_lock():
        program, applications = _locks(program_id)
        policy, snapshot = _capture(program, applications, contract, user)
        _authorize(user)
        return {'context_digest': digest(snapshot), 'policy_id': policy.pk,
                'eligible_count': len(snapshot['eligible']), 'retained_count': len(applications),
                'operational_ready': False}


def _persist(row):
    row.digest = digest(row.payload())
    row.audit_entry = ProgramLog.objects.create(program=row.program, actor=row.actor, actor_label=row.actor_label,
        action='durable_' + row._meta.model_name, notes=AUDIT_NOTE,
        changes={'digest': {'before': None, 'after': row.digest}})
    with recording():
        row.save()
    return row


def request_development_calculation(program_id, *, user, request_key, expected_context, contract, reason, previous_id=None):
    user = _authorize(user)
    _boundary()
    actor = reasoned(user, reason, True)
    if not isinstance(request_key, str) or not re.fullmatch('[a-z0-9-]{1,64}', request_key):
        raise ValidationError('INVALID_REQUEST_KEY')
    from .pool_contracts import require_context_digest
    require_context_digest(expected_context)
    _contract(contract)
    content = digest({'actor': user.pk, 'reason': actor['reason'], 'context': expected_context,
                      'contract': contract, 'previous': previous_id})
    with terms_lock():
        program, applications = _locks(program_id)
        existing = DurableRequest.objects.filter(program=program, request_key=request_key).first()
        if existing:
            _deny_integrated_request(existing.pk)
            existing.clean()
            if existing.content_digest != content:
                raise ValidationError('REQUEST_CONTENT_CONFLICT')
            # Idempotency must not turn an outdated request into an accepted one.
            _, current = _capture(program, applications, contract, user)
            if digest(current) != existing.expected_context:
                raise ValidationError('CONTEXT_CHANGED')
            _authorize(user)
            return existing
        previous = DurableRun.objects.filter(pk=previous_id, program=program).first() if previous_id else None
        if previous_id and (not previous or not DurableOutcome.objects.filter(run=previous, status='COMPLETED').exists()):
            raise ValidationError('INVALID_PREDECESSOR')
        if previous and DurableRequest.objects.filter(previous=previous).exists():
            raise ValidationError('PREDECESSOR_ALREADY_REPLACEMENT_REQUESTED')
        policy, snapshot = _capture(program, applications, contract, user)
        if digest(snapshot) != expected_context:
            raise ValidationError('CONTEXT_CHANGED')
        _authorize(user)
        return _persist(DurableRequest(program=program, request_key=request_key, expected_context=expected_context,
            content_digest=content, policy=policy, contract=contract, previous=previous, **actor))


def _request(request_id, program_id, user):
    # Caller program must match before any source data is resolved.
    request = DurableRequest.objects.get(pk=request_id, program_id=program_id)
    request.clean()
    if request.actor_id != user.pk:
        raise PermissionDenied('Test requests are scoped to the recorded actor.')
    return request


def _deny_integrated_request(request_id):
    # Only called after _authorize has verified the fresh disposable identity.
    # Even a suspended generation session cannot fall back to the old processor.
    # Old-schema disposable replay remains possible without querying absent tables.
    if 'ewaf_requestsourcebinding' in connection.introspection.table_names():
        from .generation_models import RequestSourceBinding
        from .generation_protocol import COVERAGE
        if RequestSourceBinding.objects.filter(request_id=request_id, coverage_contract=COVERAGE).exists():
            raise ValidationError('USE_GENERATION_DEVELOPMENT_PROTOCOL')


def _outcome(attempt, status, code, user, run=None):
    return _persist(DurableOutcome(program=attempt.program, attempt=attempt, status=status, code=code, run=run,
        **reasoned(user, 'Internal development processing outcome.', True)))


def process_development_request(request_id, *, program_id, user):
    user = _authorize(user)
    _boundary()
    _deny_integrated_request(request_id)
    # Transaction A records intent before doing expensive numerical work.
    with terms_lock():
        Program.objects.select_for_update().get(pk=program_id)
        request = _request(request_id, program_id, user)
        completed = DurableRun.objects.filter(request=request, completion__status='COMPLETED').first()
        if completed:
            _assert_fresh(completed, user)
            return completed
        if request.attempts.filter(outcome__isnull=True).exists():
            raise ValidationError('ATTEMPT_IN_PROGRESS_OR_INTERRUPTED')
        attempt = _persist(DurableAttempt(program=request.program, request=request,
            ordinal=request.attempts.count() + 1, **reasoned(user, request.reason, True)))
    try:
        # Transaction B contains the entire historical result graph and success outcome.
        with terms_lock():
            user = _authorize(user)
            program, applications = _locks(program_id)
            request = _request(request_id, program_id, user)
            if DurableOutcome.objects.filter(attempt=attempt).exists():
                raise ValidationError('ATTEMPT_ALREADY_CLOSED')
            policy, snapshot = _capture(program, applications, request.contract, user)
            if digest(snapshot) != request.expected_context or policy.pk != request.policy_id:
                raise ValidationError('CONTEXT_CHANGED')
            validate_snapshot(snapshot)
            calculations = _calculate(snapshot)
            # Only cooperating writers share these locks. Repeated observations
            # do not provide atomic current-result promotion (Gate 2).
            fresh_program, fresh_applications = _locks(program_id)
            _, final = _capture(fresh_program, fresh_applications, request.contract, user)
            if snapshot != final:
                raise ValidationError('CONTEXT_CHANGED')
            _authorize(user)
            actor = reasoned(user, request.reason, True)
            run = _persist(DurableRun(program=program, request=request, attempt=attempt, previous=request.previous,
                snapshot=snapshot, context_digest=digest(snapshot), **actor))
            scores = [number(c['score_0_1'], calculated=True) for c in calculations.values()]
            for application_id, calculation in calculations.items():
                score = number(calculation['score_0_1'], calculated=True)
                result = _persist(DurableResult(program=program, run=run, application_id=application_id,
                    calculation=calculation, comparison={'higher': sum(s > score for s in scores),
                        'equal': sum(s == score for s in scores), 'business_rank': None}, **actor))
                accepted = snapshot['eligible'][application_id]
                for trace in calculation['traces']:
                    code = trace['criterion']
                    _persist(DurableTrace(program=program, result=result, criterion=code,
                        assessment_id=accepted['assessments'][code]['id'], snapshot={
                            'assessment': accepted['assessments'][code], 'input': accepted['inputs'][code],
                            'definition': policy.proposal['criteria'][code], 'calculation': trace}, **actor))
            # Also cover changes during graph persistence, not only calculation.
            fresh_program, fresh_applications = _locks(program_id)
            _, final = _capture(fresh_program, fresh_applications, request.contract, user)
            if snapshot != final:
                raise ValidationError('CONTEXT_CHANGED')
            _authorize(user)
            _outcome(attempt, 'COMPLETED', 'HISTORICAL_TEST_ONLY', user, run)
            return run
    except Exception:
        # Transaction B has exited/rolled back. Never write into a broken transaction.
        with terms_lock():
            Program.objects.select_for_update().get(pk=program_id)
            if not DurableOutcome.objects.filter(attempt=attempt).exists():
                _outcome(attempt, 'FAILED', 'PROCESSING_FAILED', user)
        raise


def _calculate(snapshot):
    from . import four_policy, four_pool
    if snapshot.get('engine') == four_policy.POOL_ENGINE:
        return four_pool.calculate(snapshot)
    policy = snapshot['policy']['payload']['proposal']['criteria']
    result = {}
    for application_id, accepted in snapshot['eligible'].items():
        calculation = calculate_values(criteria=list(CRITERIA), inputs=accepted['inputs'], definitions=policy,
            judgments=snapshot['configuration']['judgments'], validation=snapshot['validation']['result'])
        if not calculation['complete']:
            raise ValidationError('NUMERICAL_CALCULATION_INCOMPLETE')
        result[application_id] = calculation
    return result


def validate_graph(run):
    from . import four_policy
    criteria = four_policy.CRITERIA if run.snapshot.get('engine') == four_policy.POOL_ENGINE else CRITERIA
    if digest(run.snapshot) != run.context_digest:
        raise ValidationError('RUN_SNAPSHOT_MISMATCH')
    validate_snapshot(run.snapshot)
    expected = _calculate(run.snapshot)
    manifest = run.snapshot['manifest']
    if (len({entry['application'] for entry in manifest}) != len(manifest) or
            {entry['application'] for entry in manifest if entry['in_scope'] and entry['status'] == 'ELIGIBLE'} != set(expected)):
        raise ValidationError('COMPLETE_POOL_MANIFEST_REQUIRED')
    rows = list(run.results.all())
    if {str(row.application_id) for row in rows} != set(expected) or len(rows) != len(expected):
        raise ValidationError('COMPLETE_POOL_RESULTS_REQUIRED')
    scores = [number(c['score_0_1'], calculated=True) for c in expected.values()]
    for row in rows:
        row.clean()
        key = str(row.application_id)
        score = number(expected[key]['score_0_1'], calculated=True)
        if row.calculation != expected[key] or row.comparison != {
                'higher': sum(s > score for s in scores), 'equal': sum(s == score for s in scores), 'business_rank': None}:
            raise ValidationError('EXACT_REPLAY_MISMATCH')
        traces = list(row.traces.all())
        if len(traces) != len(criteria) or {trace.criterion for trace in traces} != set(criteria):
            raise ValidationError('COMPLETE_CRITERION_TRACES_REQUIRED')
        accepted = run.snapshot['eligible'][key]
        if run.snapshot.get('engine') == four_policy.POOL_ENGINE:
            gate = accepted['program_relevance_eligibility']['assessment']
            assessment = CriterionAssessment.objects.get(pk=gate['id'], application_id=row.application_id, criterion='PR')
            assessment.clean()
            if gate != {'id': assessment.pk, 'digest': assessment.digest, 'payload': assessment.payload()}:
                raise ValidationError('FOUR_ELIGIBILITY_REPLAY_MISMATCH')
        for trace in traces:
            trace.clean()
            code = trace.criterion
            if trace.snapshot != {'assessment': accepted['assessments'][code], 'input': accepted['inputs'][code],
                    'definition': run.snapshot['policy']['payload']['proposal']['criteria'][code],
                    'calculation': next(t for t in expected[key]['traces'] if t['criterion'] == code)}:
                raise ValidationError('TRACE_REPLAY_MISMATCH')


def validate_snapshot(snapshot):
    """Validate inventory/trace inputs before replay; no numerical reinterpretation."""
    from . import four_policy, four_pool
    if snapshot.get('engine') == four_policy.POOL_ENGINE:
        four_pool.validate(snapshot)
        return
    if snapshot.get('engine') not in (ENGINE, source_freshness.ENGINE):
        raise ValidationError('UNSUPPORTED_RUN_VERSION')
    if snapshot['engine'] == source_freshness.ENGINE:
        observation = snapshot.get('freshness', {})
        if observation.get('version') != source_freshness.VERSION:
            raise ValidationError('UNSUPPORTED_FRESHNESS_VERSION')
        if observation.get('inventory') != [e['application'] for e in snapshot['manifest']]:
            raise ValidationError('COMPLETE_POOL_MANIFEST_REQUIRED')
    eligible = snapshot.get('eligible')
    if not isinstance(eligible, dict) or not eligible:
        raise ValidationError('COMPLETE_POOL_RESULTS_REQUIRED')
    for entry in snapshot['manifest']:
        if entry['in_scope'] and entry['status'] not in ('ELIGIBLE', 'INELIGIBLE'):
            raise ValidationError('COMPLETE_POOL_MANIFEST_REQUIRED')
        if entry['in_scope'] and entry['status'] == 'ELIGIBLE' and not (
                entry['eligibility_ready'] and entry['evidence_complete']):
            raise ValidationError('COMPLETE_POOL_MANIFEST_REQUIRED')
    for accepted in eligible.values():
        if set(accepted.get('inputs', {})) != set(CRITERIA) or set(accepted.get('assessments', {})) != set(CRITERIA):
            raise ValidationError('COMPLETE_CRITERION_TRACES_REQUIRED')


def _assert_history(run):
    run.request.clean()
    run.attempt.clean()
    run.clean()
    validate_graph(run)
    outcome = DurableOutcome.objects.filter(run=run, status='COMPLETED').first()
    if not outcome:
        raise ValidationError('RUN_INCOMPLETE')
    outcome.clean()


def _assert_fresh(run, user):
    _assert_history(run)
    if run.snapshot.get('engine') != source_freshness.ENGINE:
        raise ValidationError('FRESHNESS_REVALIDATION_REQUIRED')
    program, applications = _locks(run.program_id)
    _, current = _capture(program, applications, run.request.contract, user)
    if digest(current) != run.context_digest:
        raise ValidationError('RESULT_STALE')
    if DurableRequest.objects.filter(program=program, previous=run).exists():
        raise ValidationError('RESULT_REPLACEMENT_REQUESTED')
    _authorize(user)


def inspect_development_result(run_id, *, program_id, user):
    user = _authorize(user)
    _boundary()
    with terms_lock():
        Program.objects.select_for_update().get(pk=program_id)
        run = DurableRun.objects.get(pk=run_id, program_id=program_id)
        _deny_integrated_request(run.request_id)
        _request(run.request_id, program_id, user)
        _assert_fresh(run, user)
        return {'run_id': run.pk, 'historically_complete': True, 'sources_match_now': True,
                'freshness_basis': 'repeated_source_observations', 'atomic_freshness': False,
                'current_promotion': False, 'operational_ready': False}


def inspect_development_history(run_id, *, program_id, user):
    """Authorized immutable replay remains available even when sources are stale."""
    user = _authorize(user)
    _boundary()
    with terms_lock():
        Program.objects.select_for_update().get(pk=program_id)
        run = DurableRun.objects.get(pk=run_id, program_id=program_id)
        _request(run.request_id, program_id, user)
        _assert_history(run)
        return {'run_id': run.pk, 'historically_complete': True, 'sources_match_now': None,
                'freshness_basis': 'not_evaluated', 'atomic_freshness': False,
                'current_promotion': False, 'operational_ready': False}


def close_interrupted_attempt(request_id, *, program_id, user, reason):
    user = _authorize(user)
    _boundary()
    _deny_integrated_request(request_id)
    reasoned(user, reason, True)
    with terms_lock():
        Program.objects.select_for_update().get(pk=program_id)
        request = _request(request_id, program_id, user)
        attempt = request.attempts.filter(outcome__isnull=True).first()
        if not attempt:
            raise ValidationError('NO_UNFINISHED_ATTEMPT')
        return _persist(DurableOutcome(program=request.program, attempt=attempt, status='INTERRUPTED',
            code='EXPLICIT_RECOVERY', **reasoned(user, reason, True)))


def require_operational_result(*args, **kwargs):
    raise ValidationError('OPERATIONAL_DURABLE_PROCESSING_UNAVAILABLE')
