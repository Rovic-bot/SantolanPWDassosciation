"""Private complete-pool development protocol for a verified disposable session.

Never called by selection, release, publication or an ordinary application route.
The supported-writer guarantee excludes external SQL/ORM, processes and files.
"""
from contextlib import contextmanager
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from programs.models import Program
from programs.terms import terms_lock
from . import durable_services as durable, generation_services as generation
from .durable_models import DurableRequest, DurableAttempt, DurableRun, DurableResult, DurableTrace, DurableOutcome
from .evidence import digest
from .evidence_services import reasoned
from .generation_models import ProgramSourceState, RequestSourceBinding, RunSourceBinding, DevelopmentPromotion
from .generation_records import _owned_transaction
from .generation_protocol import COVERAGE, promotion_recording
from .generation_inputs import lock_sources, deadline
from .normalization import number


class _ReadExpiry(Exception):
    """Only raised by read-only branches before any business mutation."""
    def __init__(self, observed_at):
        self.observed_at = observed_at


@contextmanager
def _fence(program_id, user):
    from accounts.authority_services import enlisted
    if not enlisted():
        raise PermissionDenied('A registered disposable generation session is required.')
    durable._boundary()
    expired = False
    with terms_lock(), _owned_transaction():
        authority = generation._authority()
        actor = durable._authorize(user)
        program = Program.objects.select_for_update().get(pk=program_id)
        state = generation._state(ProgramSourceState.objects.select_for_update().filter(program=program).first())
        applications = lock_sources(program)
        try:
            yield actor, authority, program, state, applications
        except _ReadExpiry as error:
            expired = _expire(state, actor, observed_at=error.observed_at)
            if not expired:
                raise ValidationError('EXPIRY_STATE_MISMATCH')
        if not enlisted():
            raise PermissionDenied('Disposable generation session ended.')
        durable._authorize(actor)
        if generation._authority().generation != authority.generation:
            raise ValidationError('AUTHORITY_CHANGED')
    if expired:
        raise ValidationError('DEVELOPMENT_RESULT_EXPIRED')


def _capture(program, applications, contract, actor):
    policy, snapshot = durable._capture(program, applications, contract, actor)
    durable.validate_snapshot(snapshot)
    return policy, snapshot


def _binding(request):
    binding = RequestSourceBinding.objects.filter(request=request).first()
    if not binding or binding.coverage_contract != COVERAGE:
        raise ValidationError('INTEGRATED_REQUEST_BINDING_REQUIRED')
    binding.full_clean()
    return binding


def _expected(binding):
    return {'source_generation': binding.source_generation, 'authority_generation': binding.authority_generation,
            'revision': binding.expected_state_revision, 'current_binding': binding.expected_current_binding_id}


def _current(actor, authority, program, state, applications, *, sticky=False):
    if state.current_binding_id is None:
        raise ValidationError('NO_CURRENT_DEVELOPMENT_RESULT')
    binding = RunSourceBinding.objects.get(pk=state.current_binding_id)
    request_binding = _binding(binding.run.request)
    durable._request(binding.run.request_id, program.pk, actor)
    if request_binding.source_generation != state.generation or request_binding.authority_generation != authority.generation:
        raise ValidationError('STALE_DEVELOPMENT_GENERATION')
    def clock_check():
        observed = timezone.now()
        if observed >= request_binding.valid_until:
            if sticky:
                raise _ReadExpiry(observed)
            raise ValidationError('DEVELOPMENT_RESULT_EXPIRED')
    clock_check()
    binding.full_clean()
    _, snapshot = _capture(program, applications, binding.run.request.contract, actor)
    if snapshot != request_binding.accepted_snapshot:
        raise ValidationError('DEVELOPMENT_SOURCE_CHANGED')
    if DurableRequest.objects.filter(previous=binding.run).exists():
        raise ValidationError('DEVELOPMENT_REPLACEMENT_REQUESTED')
    clock_check()
    return binding


def _expire(state, actor, *, observed_at=None):
    if state.current_binding_id is None:
        return False
    binding = state.current_binding.request_binding
    if (observed_at or timezone.now()) < binding.valid_until:
        return False
    generation._invalidate([state], kind='EXPIRY', source_kind='development_result',
        source_id=str(state.current_binding_id), native_audits=[], metadata=generation._metadata(
            actor, 'DEVELOPMENT_EXPIRY', 'Development result reached its protected-use deadline.'))
    return True


def inspect_context(program_id, *, user, contract):
    with _fence(program_id, user) as (actor, authority, program, state, applications):
        observed = timezone.now()
        if state.current_binding_id and observed >= state.current_binding.request_binding.valid_until:
            raise _ReadExpiry(observed)
        _, snapshot = _capture(program, applications, contract, actor)
        return {'expected': generation._token(state, authority), 'context_digest': digest(snapshot),
            'retained_count': len(snapshot['manifest']), 'eligible_count': len(snapshot['eligible']),
            'valid_until': deadline(program, snapshot, timezone.now()).isoformat(),
            'coverage_contract': COVERAGE, 'operational_ready': False}


def accept_request(program_id, *, user, request_key, expected, expected_context, contract, reason, previous_id=None):
    if not isinstance(request_key, str) or not re.fullmatch('[a-z0-9-]{1,64}', request_key):
        raise ValidationError('INVALID_REQUEST_KEY')
    with _fence(program_id, user) as (actor, authority, program, state, applications):
        actor_fields = reasoned(actor, reason, True)
        content = digest({'actor': actor.pk, 'reason': actor_fields['reason'], 'context': expected_context,
                          'contract': contract, 'previous': previous_id})
        existing = DurableRequest.objects.filter(program=program, request_key=request_key).first()
        if existing:
            existing.clean()
            binding = _binding(existing)
            submitted = _expected(binding)
            if existing.previous_id:
                transition = state.last_invalidation
                # Locate the original replacement, even after later invalidations.
                from .generation_models import SourceInvalidation
                transition = SourceInvalidation.objects.filter(program=program,
                    after_generation=binding.source_generation, batch__kind='REPLACEMENT',
                    batch__source_id=request_key).first()
                if not transition:
                    raise ValidationError('REPLACEMENT_PROVENANCE_MISSING')
                submitted = {**submitted, 'source_generation': transition.before_generation,
                    'revision': transition.before_revision, 'current_binding': transition.cleared_binding_id}
            if existing.content_digest != content or expected != submitted:
                raise ValidationError('REQUEST_CONTENT_CONFLICT')
            completed = RunSourceBinding.objects.filter(request_binding=binding).first()
            if completed:
                if _current(actor, authority, program, state, applications, sticky=True).pk != completed.pk:
                    raise ValidationError('STALE_REQUEST_RETRY')
            else:
                _revalidate(binding, actor, authority, program, state, applications)
            return existing
        generation._expect(state, authority, expected)
        previous = None
        if previous_id is not None:
            previous_binding = RunSourceBinding.objects.filter(run_id=previous_id, run__program=program).first()
            latest = RunSourceBinding.objects.filter(run__program=program).order_by('-run_id').first()
            if (not previous_binding or latest.pk != previous_binding.pk or
                    state.current_binding_id not in (None, previous_binding.pk)):
                raise ValidationError('CURRENT_PREDECESSOR_REQUIRED')
            previous_binding.full_clean()
            _binding(previous_binding.run.request)
            durable._request(previous_binding.run.request_id, program.pk, actor)
            previous = previous_binding.run
            if DurableRequest.objects.filter(previous=previous).exists():
                raise ValidationError('PREDECESSOR_ALREADY_REPLACEMENT_REQUESTED')
        elif state.current_binding_id is not None:
            raise ValidationError('EXPLICIT_REPLACEMENT_REQUIRED')
        policy, snapshot = _capture(program, applications, contract, actor)
        if digest(snapshot) != expected_context:
            raise ValidationError('CONTEXT_CHANGED')
        if previous:
            generation._invalidate([state], kind='REPLACEMENT', source_kind='development_request',
                source_id=request_key, native_audits=[], metadata=generation._metadata(actor,
                    'DEVELOPMENT_REPLACEMENT', 'Explicit replacement request; old result remains historical.'))
        request = durable._persist(DurableRequest(program=program, request_key=request_key,
            expected_context=expected_context, content_digest=content, contract=contract, policy=policy,
            previous=previous, **actor_fields))
        generation._bind_request(request, snapshot, state=state, authority=authority,
            expected=generation._token(state, authority), valid_until=deadline(program, snapshot, timezone.now()),
            coverage_contract=COVERAGE)
        return request


def _revalidate(binding, actor, authority, program, state, applications):
    generation._expect(state, authority, _expected(binding))
    if timezone.now() >= binding.valid_until:
        raise ValidationError('DEVELOPMENT_REQUEST_EXPIRED')
    policy, snapshot = _capture(program, applications, binding.request.contract, actor)
    if snapshot != binding.accepted_snapshot or policy.pk != binding.request.policy_id:
        raise ValidationError('CONTEXT_CHANGED')
    return policy, snapshot


def _persist_graph(request, attempt, snapshot, calculations, policy, actor):
    fields = reasoned(actor, request.reason, True)
    run = durable._persist(DurableRun(program=request.program, request=request, attempt=attempt,
        previous=request.previous, snapshot=snapshot, context_digest=digest(snapshot), **fields))
    scores = [number(c['score_0_1'], calculated=True) for c in calculations.values()]
    for application_id, calculation in calculations.items():
        score = number(calculation['score_0_1'], calculated=True)
        result = durable._persist(DurableResult(program=request.program, run=run, application_id=application_id,
            calculation=calculation, comparison={'higher': sum(s > score for s in scores),
                'equal': sum(s == score for s in scores), 'business_rank': None}, **fields))
        accepted = snapshot['eligible'][application_id]
        for trace in calculation['traces']:
            code = trace['criterion']
            durable._persist(DurableTrace(program=request.program, result=result, criterion=code,
                assessment_id=accepted['assessments'][code]['id'], snapshot={
                    'assessment': accepted['assessments'][code], 'input': accepted['inputs'][code],
                    'definition': policy.proposal['criteria'][code], 'calculation': trace}, **fields))
    durable._outcome(attempt, 'COMPLETED', 'HISTORICAL_TEST_ONLY', actor, run)
    durable._assert_history(run)
    return run


def _promote(state, authority, run, actor):
    binding = generation._bind_run(run, state=state, authority=authority)
    checked = timezone.now()
    if checked >= binding.request_binding.valid_until:
        raise ValidationError('DEVELOPMENT_REQUEST_EXPIRED')
    revision = generation._next(state.revision)
    with promotion_recording():
        audit = generation._persist(DevelopmentPromotion(program=run.program, previous_binding_id=state.current_binding_id,
            new_binding=binding, source_generation=state.generation, authority_generation=authority.generation,
            before_revision=state.revision, after_revision=revision, checked_at=checked,
            actor=actor, actor_label=actor.get_username(), reason_code='COMPLETE_DEVELOPMENT_GRAPH',
            reason='Complete fictional calculation accepted for private development inspection only.'))
    changed = ProgramSourceState.objects.filter(program_id=state.program_id, generation=state.generation,
        revision=state.revision, current_binding_id=state.current_binding_id,
        last_invalidation_id=state.last_invalidation_id).update(revision=revision, current_binding=binding)
    if changed != 1:
        raise ValidationError('STALE_PROMOTION_CAS')
    state.refresh_from_db()
    generation._state(state)
    audit.full_clean()
    return binding


def process_request(request_id, *, program_id, user):
    with _fence(program_id, user) as (actor, authority, program, state, applications):
        request = durable._request(request_id, program_id, actor)
        binding = _binding(request)
        if RunSourceBinding.objects.filter(request_binding=binding).exists():
            current = _current(actor, authority, program, state, applications, sticky=True)
            if current.run.request_id != request.pk:
                raise ValidationError('STALE_REQUEST_RETRY')
            return current.run
        _revalidate(binding, actor, authority, program, state, applications)
        if request.attempts.filter(outcome__isnull=True).exists():
            raise ValidationError('ATTEMPT_IN_PROGRESS_OR_INTERRUPTED')
        attempt = durable._persist(DurableAttempt(program=program, request=request,
            ordinal=request.attempts.count() + 1, **reasoned(actor, request.reason, True)))
    try:
        calculations = durable._calculate(binding.accepted_snapshot)
        with _fence(program_id, user) as (actor, authority, program, state, applications):
            request = durable._request(request_id, program_id, actor)
            binding = _binding(request)
            if DurableOutcome.objects.filter(attempt=attempt).exists():
                raise ValidationError('ATTEMPT_ALREADY_CLOSED')
            policy, snapshot = _revalidate(binding, actor, authority, program, state, applications)
            run = _persist_graph(request, attempt, snapshot, calculations, policy, actor)
            _revalidate(binding, actor, authority, program, state, applications)
            _promote(state, authority, run, actor)
            _current(actor, authority, program, state, applications)
            return run
    except Exception:
        # Preserve failure history after graph rollback. Revoked users cannot use
        # this path to write; an authorized recovery remains available instead.
        try:
            with _fence(program_id, user) as (actor, _, _, _, _):
                if not DurableOutcome.objects.filter(attempt=attempt).exists():
                    durable._outcome(attempt, 'FAILED', 'PROCESSING_FAILED', actor)
        except PermissionDenied:
            pass
        raise


def inspect_current(program_id, *, user):
    expired = False
    with _fence(program_id, user) as (actor, authority, program, state, applications):
        expired = _expire(state, actor)
        if not expired:
            binding = _current(actor, authority, program, state, applications, sticky=True)
            result = {'run_id': binding.run_id, 'retained_count': binding.retained_count,
                'eligible_count': binding.eligible_count, 'coverage_contract': COVERAGE,
                'source_generation': state.generation, 'authority_generation': authority.generation,
                'revision': state.revision, 'valid_until': binding.request_binding.valid_until.isoformat(),
                'atomic_freshness': True, 'freshness_basis': 'integrated_writers_at_protected_use',
                'current_promotion': True, 'operational_ready': False}
    if expired:
        # Outside the transaction: retain the sticky audited expiry invalidation.
        raise ValidationError('DEVELOPMENT_RESULT_EXPIRED')
    return result


def close_interrupted(request_id, *, program_id, user, reason):
    with _fence(program_id, user) as (actor, _, _, _, _):
        request = durable._request(request_id, program_id, actor)
        _binding(request)
        attempt = request.attempts.filter(outcome__isnull=True).first()
        if not attempt:
            raise ValidationError('NO_UNFINISHED_ATTEMPT')
        return durable._persist(DurableOutcome(program=request.program, attempt=attempt, status='INTERRUPTED',
            code='EXPLICIT_RECOVERY', **reasoned(actor, reason, True)))
