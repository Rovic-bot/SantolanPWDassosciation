"""Disposable-only Gate 2B foundations, with no source writers or promotion API.

These counters certify only calls to these helpers. They do not certify source
freshness: writer enlistment, expiry orchestration and atomic promotion are later
gates. Sidecar helpers are private, non-promotable foundation test primitives.
"""
from contextlib import contextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils import timezone

from programs.models import Program
from programs.terms import terms_lock
from . import durable_services
from .evidence import canonical, digest
from .generation_records import (MAX_GENERATION, PROTOCOL, COVERAGE, ENGINE_PROFILE,
    _owned_transaction, require_owner, bounded, identifier, canonical_payload)
from .generation_models import (AuthorityGeneration, AuthorityInvalidation, ProgramSourceState,
    SourceMutationBatch, SourceInvalidation, RequestSourceBinding, RunSourceBinding, DevelopmentPromotion)

NATIVE_MODELS = frozenset(('membership.membershipevent', 'members.memberevent',
    'programs.programlog', 'assistance.assistancelog', 'events.eventlog',
    'admin.logentry', 'audit.securityevent',
    'programs.photoverification', 'programs.programdocumentrevision', 'documents.documentverification'))


def _next(value):
    bounded(value)
    if value == MAX_GENERATION:
        raise ValidationError('GENERATION_EXHAUSTED')
    return value + 1


def _metadata(user, reason_code, reason):
    identifier(reason_code)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('GENERATION_REASON_REQUIRED')
    return {'actor': user, 'actor_label': user.get_username(), 'system_code': '',
            'reason_code': reason_code, 'reason': reason}


def native_reference(row):
    """Minimal allowlisted identity/content hash; never copy native private text."""
    require_owner()
    label = row._meta.label_lower
    if label not in NATIVE_MODELS or not row.pk:
        raise ValidationError('NATIVE_AUDIT_NOT_ALLOWED')
    row = row.__class__.objects.get(pk=row.pk)
    action = getattr(row, 'action', getattr(row, 'action_flag', None))
    return {'model': label, 'pk': str(row.pk), 'action': str(action),
            'digest': _native_digest(row)}


def _native_digest(row):
    label = row._meta.label_lower
    fields = {f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields}
    version = 'g18-native-audit-1'
    if label in ('programs.photoverification', 'programs.programdocumentrevision', 'documents.documentverification'):
        # New evidence-audit types only; every previously supported hash retains
        # its exact version/fields. Never read file bytes into the audit payload.
        version = 'g18-native-evidence-audit-1'
        if label == 'programs.programdocumentrevision':
            fields['file'] = row.file.name
    return digest({'version': version, 'model': label, 'fields': fields})


def _native_audits(refs, *, required=False):
    if not isinstance(refs, list) or (required and not refs):
        raise ValidationError('NATIVE_AUDIT_REQUIRED')
    seen = set()
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) != {'model', 'pk', 'action', 'digest'} or
                ref['model'] not in NATIVE_MODELS or not isinstance(ref['pk'], str)):
            raise ValidationError('NATIVE_AUDIT_INVALID')
        key = (ref['model'], ref['pk'])
        if key in seen:
            raise ValidationError('DUPLICATE_NATIVE_AUDIT')
        seen.add(key)
        model = apps.get_model(ref['model'])
        try:
            row = model.objects.get(pk=ref['pk'])
        except (model.DoesNotExist, ValueError, TypeError):
            raise ValidationError('NATIVE_AUDIT_MISSING')
        # Validate without the write-context guard so immutable history can replay.
        action = getattr(row, 'action', getattr(row, 'action_flag', None))
        expected = {'model': ref['model'], 'pk': str(row.pk), 'action': str(action),
            'digest': _native_digest(row)}
        if ref != expected:
            raise ValidationError('NATIVE_AUDIT_CHANGED')


def _scope(program_ids):
    return digest({'version': 'g18-source-scope-1', 'programs': sorted(str(pk) for pk in program_ids)})


def _unused_audits(row, field):
    for ref in getattr(row, field):
        if row.__class__.objects.exclude(pk=row.pk).filter(**{
                field + '__contains': [{'model': ref['model'], 'pk': ref['pk']}]}).exists():
            raise ValidationError('NATIVE_AUDIT_ALREADY_ACCOUNTED')


def _submission(request, binding):
    return digest(canonical_payload({'version': 'g18-submission-1', 'request_content': request.content_digest,
        'key': request.request_key, 'actor': request.actor_id, 'reason': request.reason,
        'contract': request.contract, 'previous': request.previous_id,
        'source': binding.source_generation, 'authority': binding.authority_generation,
        'revision': binding.expected_state_revision, 'pointer': binding.expected_current_binding_id,
        'protocol': binding.protocol, 'coverage': binding.coverage_contract,
        'engine': binding.engine_profile, 'context': binding.context_digest,
        'valid_until': binding.valid_until, 'timezone': binding.evaluation_timezone}))


def _graph(run):
    from .durable_models import DurableResult, DurableTrace, DurableOutcome
    durable_services._assert_history(run)
    return digest({'version': 'g18-complete-graph-1', 'run': [run.pk, run.digest],
        'results': list(DurableResult.objects.filter(run=run).order_by('pk').values_list('pk', 'digest')),
        'traces': list(DurableTrace.objects.filter(result__run=run).order_by('pk').values_list('pk', 'digest')),
        'completion': list(DurableOutcome.objects.filter(run=run, status='COMPLETED').values_list('pk', 'digest'))})


def _validate_record(row):
    """Cross-record rules are service/ORM checks, not SQL CHECK constraints."""
    if getattr(row, 'system_code', '') == 'VERIFIED_MEMBER_SUBMISSION':
        if (not isinstance(row, SourceMutationBatch) or row.kind != 'SOURCE_CHANGE' or
                row.source_kind != 'application' or row.reason_code != 'APPLICATION_SUBMITTED' or
                row.actor_id is not None or row.actor_label != 'Verified member application submission'):
            raise ValidationError('SUBMISSION_SYSTEM_SCOPE_INVALID')
        _native_audits(row.source_audits, required=True)
        if len(row.source_audits) != 1 or row.source_audits[0]['model'] != 'programs.programlog':
            raise ValidationError('SUBMISSION_SYSTEM_AUDIT_INVALID')
        log = apps.get_model('programs.ProgramLog').objects.get(pk=row.source_audits[0]['pk'])
        if (log.action != 'submitted' or log.actor_id is not None or log.actor_label != '' or
                log.application_id is None or str(log.application_id) != row.source_id or
                log.application.program_id != log.program_id or row.scope_count != 1 or
                row.scope_digest != _scope([log.program_id])):
            raise ValidationError('SUBMISSION_SYSTEM_AUDIT_INVALID')
    if isinstance(row, AuthorityInvalidation):
        identifier(row.subject_id)
        expected = {'INITIALIZE': 'installation', 'USER_CHANGE': 'user', 'GROUP_CHANGE': 'group',
                    'CREDENTIAL_CHANGE': 'user', 'CATALOG_RECONCILE': 'catalog'}
        if expected.get(row.kind) != row.subject_kind:
            raise ValidationError('AUTHORITY_SUBJECT_MISMATCH')
        if row.kind == 'INITIALIZE' and (row.before_generation != 0 or row.subject_id != 'installation'):
            raise ValidationError('AUTHORITY_INITIALIZATION_INVALID')
        if row.kind != 'INITIALIZE' and row.before_generation == 0:
            raise ValidationError('AUTHORITY_INITIALIZATION_REQUIRED')
        _native_audits(row.native_audits, required=row.kind != 'INITIALIZE')
        _unused_audits(row, 'native_audits')
    elif isinstance(row, SourceMutationBatch):
        identifier(row.source_kind)
        identifier(row.source_id)
        _native_audits(row.source_audits, required=row.kind == 'SOURCE_CHANGE')
        _unused_audits(row, 'source_audits')
    elif isinstance(row, SourceInvalidation):
        row.batch.clean()
        if (row.before_generation == 0) != (row.batch.kind == 'INITIALIZE'):
            raise ValidationError('SOURCE_INITIALIZATION_INVALID')
        if row.cleared_binding_id and row.cleared_binding.run.program_id != row.program_id:
            raise ValidationError('CROSS_PROGRAM_CLEARED_BINDING')
    elif isinstance(row, RequestSourceBinding):
        request = row.request
        request.clean()
        snapshot = row.accepted_snapshot
        from .four_policy import POOL_ENGINE, BINDING_PROFILE
        four = isinstance(snapshot, dict) and snapshot.get('engine') == POOL_ENGINE
        from .generation_protocol import COVERAGE as INTEGRATED_COVERAGE
        if (row.protocol != PROTOCOL or row.coverage_contract not in (COVERAGE, INTEGRATED_COVERAGE) or
                row.engine_profile != (BINDING_PROFILE if four else ENGINE_PROFILE)):
            raise ValidationError('UNSUPPORTED_FOUNDATION_CONTRACT')
        if not isinstance(snapshot, dict) or snapshot.get('engine') not in ('durable-pool-development-2', POOL_ENGINE):
            raise ValidationError('GATE1_SNAPSHOT_REQUIRED')
        if four and row.coverage_contract != INTEGRATED_COVERAGE:
            raise ValidationError('FOUR_INTEGRATED_COVERAGE_REQUIRED')
        durable_services.validate_snapshot(snapshot)
        if (str(request.program_id) != snapshot['program'] or snapshot['policy']['id'] != request.policy_id or
                snapshot['contract'] != request.contract or
                row.context_digest != request.expected_context or row.context_digest != digest(snapshot) or
                row.inventory_digest != digest({'version': 'g18-inventory-1', 'manifest': snapshot['manifest']}) or
                row.submission_digest != _submission(request, row)):
            raise ValidationError('REQUEST_BINDING_MISMATCH')
        if row.expected_current_binding_id and row.expected_current_binding.run.program_id != request.program_id:
            raise ValidationError('CROSS_PROGRAM_EXPECTED_BINDING')
        try:
            ZoneInfo(row.evaluation_timezone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValidationError('EVALUATION_TIMEZONE_INVALID')
        if row.evaluation_timezone != snapshot['timezone']:
            raise ValidationError('EVALUATION_TIMEZONE_MISMATCH')
    elif isinstance(row, RunSourceBinding):
        binding, run = row.request_binding, row.run
        binding.clean()
        if (run.request_id != binding.request_id or run.snapshot != binding.accepted_snapshot or
                run.context_digest != binding.context_digest or row.graph_digest != _graph(run) or
                row.retained_count != len(run.snapshot['manifest']) or row.eligible_count != len(run.snapshot['eligible'])):
            raise ValidationError('RUN_BINDING_MISMATCH')
    elif isinstance(row, DevelopmentPromotion):
        from .generation_protocol import validate_promotion
        validate_promotion(row)


def _engine_profile(snapshot):
    from .four_policy import POOL_ENGINE, BINDING_PROFILE
    return BINDING_PROFILE if snapshot.get('engine') == POOL_ENGINE else ENGINE_PROFILE


def _persist(row):
    require_owner()
    row.digest = digest(row.payload())
    row.save()
    return row


def _authority():
    state = AuthorityGeneration.objects.select_for_update().filter(pk=1).first()
    if state is None or state.generation == 0:
        raise ValidationError('AUTHORITY_NOT_INITIALIZED')
    state.full_clean()
    state.last_event.full_clean()
    if state.last_event.after_generation != state.generation:
        raise ValidationError('AUTHORITY_TAIL_MISMATCH')
    return state


def _validate_batch(batch):
    batch.full_clean()
    rows = list(SourceInvalidation.objects.filter(batch=batch).order_by('program_id'))
    if len(rows) != batch.scope_count or _scope([r.program_id for r in rows]) != batch.scope_digest:
        raise ValidationError('INCOMPLETE_INVALIDATION_SCOPE')
    for row in rows:
        row.full_clean()


def _state(state):
    if state is None or state.generation == 0:
        raise ValidationError('SOURCE_STATE_NOT_INITIALIZED')
    state.full_clean()
    tail = state.last_invalidation
    tail.full_clean()
    _validate_batch(tail.batch)
    if tail.program_id != state.program_id or tail.after_generation != state.generation:
        raise ValidationError('SOURCE_STATE_TAIL_MISMATCH')
    if state.current_binding_id is None:
        if tail.after_revision != state.revision:
            raise ValidationError('SOURCE_STATE_TAIL_MISMATCH')
    else:
        promotion = DevelopmentPromotion.objects.filter(new_binding_id=state.current_binding_id, program_id=state.program_id).first()
        if (not promotion or promotion.source_generation != state.generation or
                promotion.before_revision != tail.after_revision or promotion.after_revision != state.revision):
            raise ValidationError('SOURCE_STATE_TAIL_MISMATCH')
        promotion.full_clean()
    return state


@contextmanager
def _fence(user, program_ids=(), *, bootstrap=False):
    durable_services._boundary()
    user = durable_services._authorize(user)
    ids = list(program_ids)
    if len(set(map(str, ids))) != len(ids):
        raise ValidationError('DUPLICATE_PROGRAM_SCOPE')
    with terms_lock(), _owned_transaction():
        authority = None if bootstrap else _authority()
        user = durable_services._authorize(user)
        programs = list(Program.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        if len(programs) != len(ids):
            raise ValidationError('PROGRAM_SCOPE_MISSING')
        states = {s.program_id: s for s in ProgramSourceState.objects.select_for_update().filter(
            program_id__in=[p.pk for p in programs]).order_by('program_id')}
        yield user, authority, programs, states
        durable_services._authorize(user)


def initialize_authority(*, user, reason):
    with _fence(user, bootstrap=True) as (actor, _, _, _):
        metadata = _metadata(actor, 'FOUNDATION_BOOTSTRAP', reason)
        if AuthorityGeneration.objects.filter(pk=1).exists():
            return _authority()
        if AuthorityInvalidation.objects.exists():
            raise ValidationError('ORPHAN_AUTHORITY_HISTORY')
        state = AuthorityGeneration.objects.create(id=1)
        event = _persist(AuthorityInvalidation(before_generation=0, after_generation=1,
            kind='INITIALIZE', subject_kind='installation', subject_id='installation', **metadata))
        _cas_authority(state, event)
        return _authority()


def _cas_authority(state, event):
    require_owner()
    event.full_clean()
    if event.before_generation != state.generation or event.after_generation != _next(state.generation):
        raise ValidationError('AUTHORITY_SEQUENCE_CONFLICT')
    changed = AuthorityGeneration.objects.filter(pk=1, generation=state.generation,
        last_event_id=state.last_event_id).update(generation=event.after_generation, last_event=event)
    if changed != 1:
        raise ValidationError('STALE_AUTHORITY_CAS')


def advance_authority(*, user, expected_generation, kind, subject_kind, subject_id, native_audits,
                      reason_code, reason):
    bounded(expected_generation, positive=True)
    if kind == 'INITIALIZE':
        raise ValidationError('USE_AUTHORITY_INITIALIZATION')
    with _fence(user) as (actor, state, _, _):
        if state.generation != expected_generation:
            raise ValidationError('STALE_AUTHORITY_GENERATION')
        event = _persist(AuthorityInvalidation(before_generation=state.generation,
            after_generation=_next(state.generation), kind=kind, subject_kind=subject_kind,
            subject_id=subject_id, native_audits=native_audits, **_metadata(actor, reason_code, reason)))
        _cas_authority(state, event)
        return _authority()


def _token(state, authority):
    return {'source_generation': state.generation, 'authority_generation': authority.generation,
            'revision': state.revision, 'current_binding': state.current_binding_id}


def _expect(state, authority, expected):
    _state(state)
    if not isinstance(expected, dict) or set(expected) != set(_token(state, authority)):
        raise ValidationError('EXPECTED_GENERATION_TOKEN_REQUIRED')
    for field in ('source_generation', 'authority_generation', 'revision'):
        bounded(expected[field], positive=True)
    if canonical(expected) != canonical(_token(state, authority)):
        raise ValidationError('STALE_GENERATION_TOKEN')


def inspect_foundation(program_id, *, user):
    with _fence(user, [program_id]) as (_, authority, programs, states):
        state = _state(states.get(programs[0].pk))
        return {**_token(state, authority), 'coverage_contract': COVERAGE,
                'operational_ready': False, 'current_promotion': False}


def _cas_source(state, event):
    require_owner()
    event.full_clean()
    if (event.program_id != state.program_id or event.before_generation != state.generation or
            event.before_revision != state.revision or event.cleared_binding_id != state.current_binding_id):
        raise ValidationError('SOURCE_SEQUENCE_CONFLICT')
    changed = ProgramSourceState.objects.filter(program_id=state.program_id,
        generation=state.generation, revision=state.revision, current_binding_id=state.current_binding_id,
        last_invalidation_id=state.last_invalidation_id).update(generation=event.after_generation,
            revision=event.after_revision, last_invalidation=event, current_binding=None)
    if changed != 1:
        raise ValidationError('STALE_SOURCE_CAS')


def _invalidate(states, *, metadata, kind, source_kind, source_id, native_audits):
    require_owner()
    batch = _persist(SourceMutationBatch(kind=kind, source_kind=source_kind, source_id=source_id,
        source_audits=native_audits, scope_count=len(states),
        scope_digest=_scope([s.program_id for s in states]), **metadata))
    for state in states:
        event = _persist(SourceInvalidation(batch=batch, program_id=state.program_id,
            before_generation=state.generation, after_generation=_next(state.generation),
            before_revision=state.revision, after_revision=_next(state.revision),
            cleared_binding_id=state.current_binding_id))
        _cas_source(state, event)
    _validate_batch(batch)
    for state in states:
        state.refresh_from_db()
        _state(state)
    return batch


def initialize_programs(program_ids, *, user, expected_authority_generation, reason):
    bounded(expected_authority_generation, positive=True)
    program_ids = list(program_ids)
    if not program_ids:
        raise ValidationError('PROGRAM_INITIALIZATION_SCOPE_REQUIRED')
    with _fence(user, program_ids) as (actor, authority, programs, states):
        if authority.generation != expected_authority_generation:
            raise ValidationError('STALE_AUTHORITY_GENERATION')
        metadata = _metadata(actor, 'FOUNDATION_BOOTSTRAP', reason)
        pending = []
        for program in programs:
            if program.pk in states:
                _state(states[program.pk])
            else:
                if SourceInvalidation.objects.filter(program=program).exists():
                    raise ValidationError('ORPHAN_SOURCE_HISTORY')
                pending.append(ProgramSourceState.objects.create(program=program))
        if pending:
            _invalidate(pending, metadata=metadata, kind='INITIALIZE', source_kind='foundation',
                        source_id='disposable-bootstrap', native_audits=[])
        return [ProgramSourceState.objects.get(program=p) for p in programs]


def advance_sources(expected, *, user, kind, source_kind, source_id, native_audits, reason_code, reason):
    """Internal foundation transition, NOT a wrapper around any source writer.

    Caller-supplied scope is checked for internal completeness only. Deriving the
    complete affected business scope is explicitly deferred to writer integrations.
    """
    if not isinstance(expected, dict) or kind not in ('SOURCE_CHANGE', 'EXPIRY', 'REPLACEMENT'):
        raise ValidationError('SOURCE_TRANSITION_CONTEXT_REQUIRED')
    normalized = {str(pk): token for pk, token in expected.items()}
    if len(normalized) != len(expected):
        raise ValidationError('DUPLICATE_PROGRAM_SCOPE')
    expected = normalized
    with _fence(user, list(expected)) as (actor, authority, programs, states):
        for program in programs:
            _expect(states.get(program.pk), authority, expected[str(program.pk)])
        return _invalidate([states[p.pk] for p in programs], metadata=_metadata(actor, reason_code, reason),
            kind=kind, source_kind=source_kind, source_id=source_id, native_audits=native_audits)


def _bind_request(request, snapshot, *, state, authority, expected, valid_until, coverage_contract=COVERAGE):
    """Private non-promotable sidecar primitive, not request acceptance workflow."""
    require_owner()
    _expect(state, authority, expected)
    if (state.program_id != request.program_id or timezone.is_naive(valid_until) or
            valid_until <= timezone.now()):
        raise ValidationError('REQUEST_BINDING_CONTEXT_INVALID')
    row = RequestSourceBinding(request=request, source_generation=state.generation,
        authority_generation=authority.generation, expected_state_revision=state.revision,
        expected_current_binding_id=state.current_binding_id, protocol=PROTOCOL,
        coverage_contract=coverage_contract, engine_profile=_engine_profile(snapshot), accepted_snapshot=snapshot,
        context_digest=digest(snapshot), inventory_digest=digest({'version': 'g18-inventory-1', 'manifest': snapshot['manifest']}),
        valid_until=valid_until, evaluation_timezone=snapshot['timezone'])
    row.submission_digest = _submission(request, row)
    old = RequestSourceBinding.objects.filter(pk=request.pk).first()
    if old:
        old.full_clean()
        if old.submission_digest != row.submission_digest or old.valid_until <= timezone.now():
            raise ValidationError('CONFLICTING_REQUEST_BINDING')
        return old
    return _persist(row)


def _bind_run(run, *, state, authority):
    require_owner()
    binding = RequestSourceBinding.objects.get(request_id=run.request_id)
    _expect(state, authority, {'source_generation': binding.source_generation,
        'authority_generation': binding.authority_generation, 'revision': binding.expected_state_revision,
        'current_binding': binding.expected_current_binding_id})
    if state.program_id != run.program_id or binding.valid_until <= timezone.now():
        raise ValidationError('STALE_RUN_BINDING')
    old = RunSourceBinding.objects.filter(pk=run.pk).first()
    if old:
        old.full_clean()
        return old
    return _persist(RunSourceBinding(run=run, request_binding=binding, graph_digest=_graph(run),
        retained_count=len(run.snapshot['manifest']), eligible_count=len(run.snapshot['eligible'])))
