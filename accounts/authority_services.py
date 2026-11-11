"""Gate 2C authority writers, enlisted only in verified disposable sessions.

No route, setting, schema probe or caller boolean enables enlistment. Raw ORM,
management commands and privileged SQL are outside this integration contract.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from types import SimpleNamespace

from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max

from audit.models import SecurityEvent
from ewaf import generation_services as generation
from ewaf.generation_records import _owned_transaction, require_owner
from ewaf.generation_models import AuthorityInvalidation
from programs.terms import terms_lock
from scripts import durable_test_runner as disposable

_session = None
_registration_lock = Lock()
_used_bootstraps = set()
_request_owner = ContextVar('authority_request_owner', default=None)


@contextmanager
def _disposable_authority_session(*, user):
    """Private test bootstrap; never called by application startup or a request."""
    global _session
    disposable.require_disposable()
    with generation._fence(user):
        identity = disposable.identity()[:4]
        bootstrap = AuthorityInvalidation.objects.get(kind='INITIALIZE').pk
    with _registration_lock:
        if _session is not None:
            raise ValidationError('AUTHORITY_SESSION_ALREADY_REGISTERED')
        key = (*identity, bootstrap)
        if key in _used_bootstraps:
            # Unfenced writes while suspended cannot be retrospectively certified.
            # Reconciliation is not implemented here. Require a new test fixture.
            raise ValidationError('AUTHORITY_SESSION_REINITIALIZATION_REQUIRED')
        _used_bootstraps.add(key)
        _session = identity
    try:
        yield
    finally:
        with _registration_lock:
            _session = None


def enlisted():
    if _session is None:
        return False
    disposable.require_disposable()
    if disposable.identity()[:4] != _session:
        raise PermissionDenied('Authority session database identity changed.')
    return True


def _actor(user, *, own_password=False):
    actor = User.objects.filter(pk=getattr(user, 'pk', None)).first()
    if not actor or not actor.is_active or not actor.is_staff or (not own_password and not actor.is_superuser):
        raise PermissionDenied('Current authority required.')
    return actor


def _lock_records():
    # Coarse global fence: small disposable authority catalog, never per-program.
    # No user/group row is acquired before Terms and AuthorityGeneration.
    for model in (User, Group, Permission, User.groups.through,
                  User.user_permissions.through, Group.permissions.through):
        list(model.objects.select_for_update().order_by('pk').values_list('pk', flat=True))


def _snapshot(model):
    # Password hashes are transient comparison values only. Never digest or audit
    # this snapshot, log it, return it to a caller, or include it in exceptions.
    fields = [f.attname for f in model._meta.concrete_fields if f.name != 'last_login']
    result = {row['id']: row for row in model.objects.order_by('pk').values(*fields)}
    relations = ('groups', 'user_permissions') if model is User else ('permissions',)
    for obj in model.objects.order_by('pk'):
        for name in relations:
            result[obj.pk][name] = tuple(getattr(obj, name).order_by('pk').values_list('pk', flat=True))
    return result


def _finish(state, actor, model, before, audit_start, *, own_password=False, credential=False):
    after = _snapshot(model)
    changed = sorted(pk for pk in before.keys() | after.keys() if before.get(pk) != after.get(pk))
    audit_model = SecurityEvent if own_password else LogEntry
    audit_query = audit_model.objects.filter(pk__gt=audit_start)
    if own_password:
        # Concurrent login failures have no User FK lock and are maintenance,
        # not part of this password operation's mandatory native audit set.
        audit_query = audit_query.filter(user=actor, action=SecurityEvent.Action.PASSWORD_CHANGED)
    audits = list(audit_query.order_by('pk'))
    if own_password:
        valid = (len(audits) == len(changed) and all(
            row.user_id == actor.pk and row.action == SecurityEvent.Action.PASSWORD_CHANGED for row in audits))
        by_subject = {actor.pk: audits}
    else:
        content_type = ContentType.objects.get_for_model(model)
        valid = all(row.user_id == actor.pk and row.content_type_id == content_type.pk for row in audits)
        by_subject = {}
        for row in audits:
            by_subject.setdefault(row.object_id, []).append(row)
        for pk in changed:
            rows = by_subject.get(str(pk), [])
            flag = ADDITION if pk not in before else DELETION if pk not in after else CHANGE
            valid = valid and len(rows) == 1 and rows[0].action_flag == flag
        # Django logs an unchanged valid change form. It is not an invalidation.
        for key, rows in by_subject.items():
            if key not in {str(pk) for pk in changed}:
                valid = valid and len(rows) == 1 and rows[0].action_flag == CHANGE and any(
                    str(pk) == key and before[pk] == after.get(pk) for pk in before)
    if not valid:
        raise ValidationError('AUTHORITY_NATIVE_AUDIT_MISMATCH')
    for pk in changed:
        refs = by_subject[actor.pk] if own_password else by_subject[str(pk)]
        event = generation._persist(AuthorityInvalidation(
            before_generation=state.generation, after_generation=generation._next(state.generation),
            kind='CREDENTIAL_CHANGE' if credential else 'USER_CHANGE' if model is User else 'GROUP_CHANGE',
            subject_kind='user' if model is User else 'group', subject_id=str(pk),
            native_audits=[generation.native_reference(row) for row in refs],
            **generation._metadata(actor, 'AUTHORITY_INTEGRATION',
                'Explicit credential change.' if credential else 'Explicit account or role mutation.')))
        generation._cas_authority(state, event)
        state = generation._authority()


@contextmanager
def _mutation(request, model, *, own_password=False, credential=False):
    generation.durable_services._boundary()
    with terms_lock(), _owned_transaction():
        state = generation._authority()
        _lock_records()
        actor = _actor(request.user, own_password=own_password)
        request.user = actor  # Forms/permissions use current state, without caches.
        before = _snapshot(model)
        audit_model = SecurityEvent if own_password else LogEntry
        start = audit_model.objects.aggregate(value=Max('pk'))['value'] or 0
        token = _request_owner.set(request)
        try:
            yield
            if not enlisted():
                raise PermissionDenied('Authority session ended during mutation.')
            _finish(state, actor, model, before, start, own_password=own_password, credential=credential)
        finally:
            _request_owner.reset(token)


@contextmanager
def protect_request(request, model, *, own_password=False, credential=False):
    """Wrap OUTSIDE inherited add/change/delete/action/password transactions."""
    if request.method != 'POST':
        yield
    elif not enlisted():
        with terms_lock():
            yield
    elif _request_owner.get() is request:
        require_owner()  # UserAdmin.add_view delegates to changeform_view.
        yield
    else:
        with _mutation(request, model, own_password=own_password, credential=credential):
            yield


def mutate_relation(*, user, model, pk, relation, operation, related_ids=()):
    """Internal, disposable-only forward/reverse M2M adapter. No HTTP endpoint.

    Accept actual model classes, IDs and one of the fixed supported relations.
    Native CHANGE logs and global invalidations cover each changed root record.
    """
    if not enlisted():
        raise PermissionDenied('Registered disposable authority session required.')
    mapping = {(User, 'groups'): (User, Group), (User, 'user_permissions'): (User, Permission),
               (Group, 'permissions'): (Group, Permission), (Group, 'user_set'): (User, User),
               (Permission, 'user_set'): (User, User), (Permission, 'group_set'): (Group, Group)}
    if (model, relation) not in mapping or operation not in ('add', 'remove', 'set', 'clear'):
        raise ValidationError('AUTHORITY_RELATION_NOT_SUPPORTED')
    root, related_model = mapping[(model, relation)]
    ids = tuple(related_ids)
    if len(set(ids)) != len(ids) or (operation == 'clear' and ids):
        raise ValidationError('AUTHORITY_RELATION_IDS_INVALID')
    request = SimpleNamespace(user=user)
    with _mutation(request, root):
        target = model.objects.get(pk=pk)
        objects = list(related_model.objects.filter(pk__in=ids).order_by('pk'))
        if len(objects) != len(ids):
            raise ValidationError('AUTHORITY_RELATION_TARGET_MISSING')
        before = _snapshot(root)
        manager = getattr(target, relation)
        if operation == 'set':
            manager.set(objects)
        elif operation == 'clear':
            manager.clear()
        else:
            getattr(manager, operation)(*objects)
        after = _snapshot(root)
        for subject in sorted(before):
            if before[subject] != after[subject]:
                LogEntry.objects.create(user=request.user, content_type=ContentType.objects.get_for_model(root),
                    object_id=str(subject), object_repr=str(root.objects.get(pk=subject))[:200],
                    action_flag=CHANGE, change_message='Explicit authority relationship change.')
