"""Whole Admin form transaction for the four existing reference-data writers.

No new controls, permissions, bulk actions, or application-mode table queries.
Existing metadata forms have no optimistic version token; the server captures
their source token under T/H and retains the native Django audit atomically.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import PermissionDenied, ValidationError

ALLOWED = frozenset(('documents.documenttype', 'documents.membershipdocumentrequirement',
                     'members.disabilitytype', 'membership.membershipsettings'))
_writer = ContextVar('development_reference_writer', default=None)


def require_reference_writer():
    from accounts.authority_services import enlisted
    if enlisted():
        from django.db import connection
        from .generation_records import require_owner
        require_owner()
        if _writer.get() != (connection.connection, id(connection.atomic_blocks[0])):
            raise ValidationError('REFERENCE_MUTATION_REQUIRES_FENCED_ADMIN')


@contextmanager
def _reference_writes():
    from django.db import connection
    token = _writer.set((connection.connection, id(connection.atomic_blocks[0])))
    try:
        yield
    finally:
        _writer.reset(token)


@contextmanager
def reference_request(request, model):
    from accounts.authority_services import enlisted
    if request.method != 'POST':
        yield
        return
    if not enlisted():
        from programs.terms import terms_lock as operational_terms_lock
        with operational_terms_lock():
            yield
        return
    from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
    from django.contrib.contenttypes.models import ContentType
    from programs.models import Program
    from programs.terms import terms_lock
    from . import generation_services as generation
    from .generation_models import ProgramSourceState
    from .generation_records import _owned_transaction
    from .source_invalidation import _actor, _authority_identity
    from .shared_invalidation import finish, audit_history, audit_delta

    if model._meta.label_lower not in ALLOWED:
        raise ValidationError('REFERENCE_WRITER_NOT_INTEGRATED')
    generation.durable_services._boundary()
    with terms_lock(), _owned_transaction():
        authority = generation._authority()
        actor = _actor(request.user)
        identity = _authority_identity(actor)
        request.user = actor
        # Preserve ModelAdmin's current per-model permission checks; never trust
        # its request's previously populated permission caches.
        ids = list(Program.objects.order_by('pk').values_list('pk', flat=True))
        programs = [Program.objects.select_for_update().get(pk=pk) for pk in ids]
        states = [generation._state(ProgramSourceState.objects.select_for_update().filter(program=p).first())
                  for p in programs]
        expected = {str(s.program_id): generation._token(s, authority) for s in states}
        list(model.objects.select_for_update().order_by('pk'))
        before = {str(row['id']): row for row in model.objects.order_by('pk').values()}
        history = audit_history(LogEntry)
        with _reference_writes():
            yield
        if not enlisted() or _authority_identity(_actor(actor)) != identity:
            raise PermissionDenied('Reference actor or disposable identity changed.')
        after = {str(row['id']): row for row in model.objects.order_by('pk').values()}
        logs = audit_delta(LogEntry, history)
        changed = [key for key, row in after.items() if before.get(key) != row]
        if set(before) - set(after):
            raise ValidationError('REFERENCE_DELETION_NOT_SUPPORTED')
        if not changed:
            # Django logs a no-change form; keep that accepted native behavior,
            # but do not fabricate source invalidation for an unchanged source.
            if len(logs) > 1 or any(log.action_flag != CHANGE or log.change_message != '[]' for log in logs):
                raise ValidationError('REFERENCE_NO_CHANGE_AUDIT_INVALID')
            return
        if len(changed) != 1 or len(logs) != 1:
            raise ValidationError('REFERENCE_NATIVE_AUDIT_SCOPE')
        key, log = changed[0], logs[0]
        content_type = ContentType.objects.get_for_model(model)
        instance = model.objects.get(pk=key)
        if (log.user_id != actor.pk or log.content_type_id != content_type.pk or log.object_id != key or
                log.object_repr != str(instance)[:200] or
                log.action_flag != (CHANGE if key in before else ADDITION) or not log.change_message):
            raise ValidationError('REFERENCE_NATIVE_AUDIT_INVALID')
        if ids != list(Program.objects.order_by('pk').values_list('pk', flat=True)):
            raise ValidationError('REFERENCE_SOURCE_SCOPE_CHANGED')
        finish(states, authority, expected, actor=actor, kind='reference', source_id=key, audits=logs)


class ReferenceTransactions:
    def changeform_view(self, request, *args, **kwargs):
        with reference_request(request, self.model):
            return super().changeform_view(request, *args, **kwargs)

    def changelist_view(self, request, *args, **kwargs):
        from accounts.authority_services import enlisted
        if request.method == 'POST' and enlisted():
            raise PermissionDenied('Reference bulk actions are not supported in this disposable protocol.')
        return super().changelist_view(request, *args, **kwargs)
