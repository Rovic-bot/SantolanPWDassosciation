"""Bounded linked-event writers in registered disposable sessions only."""
from contextvars import ContextVar
from functools import wraps
from inspect import signature

_uploads = ContextVar('generation_event_uploads', default=None)


def remember_event_upload(saved_file):
    journal = _uploads.get()
    if journal is not None:
        journal.append(saved_file)


def retain_event_images():
    return _uploads.get() is not None


def _finalize(states, authority, expected, batch):
    from django.core.exceptions import ValidationError
    from . import generation_services as generation
    if generation._authority().generation != authority.generation:
        raise ValidationError('EVENT_AUTHORITY_CHANGED')
    generation._validate_batch(batch)
    if (batch.scope_count != len(states) or
            batch.scope_digest != generation._scope([state.program_id for state in states])):
        raise ValidationError('EVENT_INVALIDATION_SCOPE')
    for state in states:
        state.refresh_from_db()
        generation._state(state)
        prior = expected[str(state.program_id)]
        if (state.generation != prior['source_generation'] + 1 or
                state.revision != prior['revision'] + 1 or state.last_invalidation.batch_id != batch.pk):
            raise ValidationError('EVENT_FINAL_STATE_MISMATCH')


def event_writer(*, publication=False):
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            from django.core.exceptions import PermissionDenied, ValidationError
            expected = kwargs.pop('source_expected', None)
            if not enlisted():
                if expected is not None:
                    raise PermissionDenied('Source tokens require a registered disposable session.')
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from django.core.files.storage import FileSystemStorage
            from announcements.services import remove_file
            from core.permissions import require_workspace_permissions
            from events.forms import EventForm
            from events.models import Event, EventLog
            from programs.models import Program
            from programs.terms import terms_lock
            from . import generation_services as generation
            from .generation_models import ProgramSourceState
            from .generation_records import _owned_transaction
            from .source_invalidation import _actor, _authority_identity

            generation.durable_services._boundary()
            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            journal = []
            context = _uploads.set(journal)
            try:
                with terms_lock(), _owned_transaction():
                    authority = generation._authority()
                    actor = _actor(arguments['user'])
                    identity = _authority_identity(actor)
                    arguments['user'] = actor
                    pk = arguments['pk']
                    old = Event.objects.get(pk=pk) if pk else Event(created_by=actor)
                    proposed_id = old.application_program_id
                    if not publication:
                        require_workspace_permissions(actor, 'events.view_event',
                            'events.change_event' if pk else 'events.add_event')
                        form = EventForm(instance=old, user=actor)
                        if arguments['data'].get('application_program'):
                            require_workspace_permissions(actor, 'programs.view_program')
                        field = form.fields.get('application_program')
                        if field is not None:
                            # Validate only the link before locking; full form/image validation
                            # remains in the original writer and is not run twice.
                            proposed = field.clean(arguments['data'].get('application_program'))
                            proposed_id = proposed.pk if proposed else None
                    ids = sorted({value for value in (old.application_program_id, proposed_id) if value is not None})
                    if not isinstance(expected, dict) or set(expected) != {str(value) for value in ids}:
                        raise ValidationError('INCOMPLETE_EVENT_SOURCE_SCOPE')
                    # Explicit per-row iteration makes all P-before-all S ordering observable.
                    programs = [Program.objects.select_for_update().get(pk=value) for value in ids]
                    states = []
                    for program in programs:
                        state = ProgramSourceState.objects.select_for_update().filter(program=program).first()
                        generation._expect(state, authority, expected[str(program.pk)])
                        states.append(state)
                    if pk:
                        current = Event.objects.select_for_update().get(pk=pk)
                        if current.application_program_id != old.application_program_id:
                            raise ValidationError('EVENT_SCOPE_CHANGED')
                        old = current
                    previous = {name: str(getattr(old, name)) for name in EventForm.Meta.fields}
                    before_version, before_status = old.version, old.status
                    program_rows = list(Program.objects.filter(pk__in=ids).order_by('pk').values())
                    history = {row['id']: row for row in EventLog.objects.order_by('pk').values()}
                    storage = Event._meta.get_field('image').storage
                    if storage.__class__ is not FileSystemStorage or storage._allow_overwrite:
                        raise ValidationError('NONOVERWRITING_LOCAL_STORAGE_REQUIRED')
                    result = function(*bound.args, **bound.kwargs)
                    if not enlisted() or _authority_identity(_actor(actor)) != identity:
                        raise PermissionDenied('Event actor or disposable session changed.')
                    if not isinstance(result, Event) or (pk and result.pk != old.pk):
                        raise ValidationError('EVENT_RESULT_SCOPE')
                    item = Event.objects.get(pk=result.pk)
                    if any(getattr(result, field.attname) != getattr(item, field.attname)
                           for field in Event._meta.concrete_fields):
                        raise ValidationError('EVENT_RESULT_CONTENT')
                    if (item.application_program_id != proposed_id or item.version != before_version + 1 or
                            item.updated_by_id != actor.pk or
                            (not pk and (item.created_by_id != actor.pk or item.status != 'draft'))):
                        raise ValidationError('EVENT_RESULT_VERSION_OR_LINK')
                    if item.image and not storage.exists(item.image.name):
                        raise ValidationError('EVENT_IMAGE_MISSING')
                    after_history = {row['id']: row for row in EventLog.objects.order_by('pk').values()}
                    if any(after_history.get(key) != row for key, row in history.items()):
                        raise ValidationError('EVENT_HISTORY_CHANGED')
                    logs = list(EventLog.objects.filter(pk__in=set(after_history) - set(history)).order_by('pk'))
                    if len(logs) != 1:
                        raise ValidationError('EVENT_NATIVE_AUDIT_SCOPE')
                    if publication:
                        action, notes = arguments['action'], arguments['notes'].strip()
                        changes = {'status': {'before': before_status, 'after': action}}
                        if item.status != action or any(str(getattr(item, name)) != value for name, value in previous.items()):
                            raise ValidationError('EVENT_PUBLICATION_CHANGED_CONTENT')
                    else:
                        action = 'updated' if pk else 'created'
                        notes = (str(arguments['data'].get('notes') or '').strip() or
                                 'Event updated from the event editor.') if pk else 'Event saved as a private draft.'
                        # Native audits retain the validated form's datetime spelling
                        # (e.g. Philippine offset); DB reload normalizes to UTC. Compare
                        # actual values above, then preserve the native representation.
                        changes = {name: {'before': value, 'after': str(getattr(result, name))}
                                   for name, value in previous.items() if value != str(getattr(result, name))}
                        if item.status != before_status:
                            raise ValidationError('EVENT_EDIT_CHANGED_PUBLICATION')
                    log = logs[0]
                    address = EventLog._meta.get_field('address').get_prep_value(arguments['address'] or None)
                    if (log.event_id, log.registration_id, log.actor_id, log.actor_label, log.action,
                            log.notes, log.changes, log.address) != (item.pk, None, actor.pk, actor.get_username(),
                            action, notes, changes, address):
                        raise ValidationError('EVENT_NATIVE_AUDIT_INVALID')
                    if program_rows != list(Program.objects.filter(pk__in=ids).order_by('pk').values()):
                        raise ValidationError('EVENT_CHANGED_PROGRAM')
                    current_authority = generation._authority()
                    if current_authority.generation != authority.generation:
                        raise ValidationError('EVENT_AUTHORITY_CHANGED')
                    for state in states:
                        generation._expect(state, current_authority, expected[str(state.program_id)])
                    if states:
                        batch = generation._invalidate(states, kind='SOURCE_CHANGE', source_kind='event',
                            source_id=str(item.pk), native_audits=[generation.native_reference(log)],
                            metadata=generation._metadata(actor, 'LINKED_EVENT_CHANGED', 'Linked event source mutation.'))
                        _finalize(states, authority, expected, batch)
                    # An unlinked event retains its native audit but has no program batch.
                    return result
            except Exception:
                for storage, name in journal:
                    remove_file(storage, name)
                raise
            finally:
                _uploads.reset(context)
        return wrapped
    return decorate
