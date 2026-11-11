"""Shared source fence, available only to the verified disposable session.

Scope comes from the writer's database resolver, never from expected tokens.
This module supplies no current-result or operational consumption capability.
"""
from contextlib import contextmanager

from django.core.exceptions import PermissionDenied, ValidationError


@contextmanager
def source_fence(user, expected, resolve):
    from accounts.authority_services import enlisted
    from programs.models import Program
    from programs.terms import terms_lock
    from . import generation_services as generation
    from .generation_models import ProgramSourceState
    from .generation_records import _owned_transaction
    from .source_invalidation import _actor, _authority_identity

    generation.durable_services._boundary()
    with terms_lock(), _owned_transaction():
        authority = generation._authority()
        actor = _actor(user)
        identity = _authority_identity(actor)
        ids = sorted(set(resolve()))
        if not isinstance(expected, dict) or set(expected) != {str(pk) for pk in ids}:
            raise ValidationError('INCOMPLETE_SHARED_SOURCE_SCOPE')
        programs = [Program.objects.select_for_update().get(pk=pk) for pk in ids]
        states = []
        for program in programs:
            state = ProgramSourceState.objects.select_for_update().filter(program=program).first()
            generation._expect(state, authority, expected[str(program.pk)])
            states.append(state)
        yield actor, authority, states
        if not enlisted() or _authority_identity(_actor(actor)) != identity:
            raise PermissionDenied('Shared-source actor or disposable identity changed.')
        if generation._authority().generation != authority.generation or sorted(set(resolve())) != ids:
            raise ValidationError('SHARED_SOURCE_SCOPE_OR_AUTHORITY_CHANGED')


def finish(states, authority, expected, *, actor, kind, source_id, audits):
    from . import generation_services as generation
    from .event_invalidation import _finalize
    for state in states:
        generation._expect(state, authority, expected[str(state.program_id)])
    batch = generation._invalidate(states, kind='SOURCE_CHANGE', source_kind=kind,
        source_id=str(source_id), native_audits=[generation.native_reference(row) for row in audits],
        metadata=generation._metadata(actor, 'SHARED_SOURCE_CHANGED', 'Audited shared source mutation.'))
    _finalize(states, authority, expected, batch)
    return batch


def audit_delta(model, before):
    """Preserve old native history and enumerate the entire transaction's additions."""
    after = {str(row['id']): row for row in model.objects.order_by('pk').values()}
    if any(after.get(key) != value for key, value in before.items()):
        raise ValidationError('SHARED_NATIVE_HISTORY_CHANGED')
    return list(model.objects.filter(pk__in=set(after) - set(before)).order_by('pk'))


def audit_history(model):
    return {str(row['id']): row for row in model.objects.order_by('pk').values()}
