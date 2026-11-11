import unicodedata
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from accounts.backends import reserve_windows
from announcements.services import remove_file
from core.permissions import require_workspace_permissions
from members.models import Member
from .forms import EventForm, OpenAttendanceForm
from .models import Event, EventAttendance, EventAttendanceLog, EventLog, EventRegistration, VerificationWindow
from programs.terms import terms_lock, guard_event
from .observances import REFERENCE_CATALOGUE, calendar_months
from ewaf.event_invalidation import event_writer, remember_event_upload, retain_event_images
from .participation import require_participation_details, guard_participation


def public_observance_calendar():
    from django.urls import reverse
    from .models import AnnualObservance
    if not observance_storage_ready():
        return calendar_months()
    months = calendar_months()
    for item in AnnualObservance.objects.public():
        card = calendar_months((item,))[item.month - 1]['observances'][0]
        card.update(image_url=reverse('events:observance_image', args=[item.pk]) if item.image else '',
                    image_alt=item.image_alt, target_audience=item.target_audience,
                    who_may_participate=item.who_may_participate,
                    detail_url=reverse('events:observance_public_detail', args=[item.pk]))
        months[item.month - 1]['observances'].append(card)
    return months


def observance_reference_calendar(*, user):
    require_workspace_permissions(user, 'events.view_annualobservance')
    return calendar_months(REFERENCE_CATALOGUE)

VERIFICATION_FAILED = 'Unable to verify membership. Please visit/contact the Barangay Santolan PWD Association Help Desk.'


def normalize_name(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())


def normalize_phone(value):
    value = value.strip()
    if any(char not in '0123456789+()- .\t\r\n' for char in value) or '+' in value[1:]:
        return None
    digits = ''.join(char for char in value if char in '0123456789')
    if len(digits) == 12 and digits.startswith('63'):
        digits = '0' + digits[2:]
    return digits or None


def reserve_verification(control_number, address):
    limits = {
        salted_hmac('events.verify.member', control_number.strip().upper(), algorithm='sha256').hexdigest(): settings.EVENT_VERIFICATION_MEMBER_LIMIT,
        salted_hmac('events.verify.address', address, algorithm='sha256').hexdigest(): settings.EVENT_VERIFICATION_ADDRESS_LIMIT,
    }
    try:
        return reserve_windows(limits, settings.EVENT_VERIFICATION_WINDOW_SECONDS, VerificationWindow)
    except (OperationalError, VerificationWindow.DoesNotExist):
        return False


def record_log(event, action, notes, *, user=None, changes=None, registration=None, address=None):
    return EventLog.objects.create(event=event, registration=registration, actor=user,
        actor_label=user.get_username() if user else '', action=action, notes=notes,
        changes=changes or {}, address=address or None)


def occupied_slots(event):
    return event.registrations.exclude(status='cancelled').count()


def check_version(item, version):
    if item.version != version:
        raise ValidationError('This record changed. Reload the page before continuing.')


def check_notes(notes):
    if not notes.strip() or len(notes) > 2000:
        raise ValidationError('Provide a reason of up to 2,000 characters.')


@event_writer()
@terms_lock()
def save_event(*, user, data, files=None, pk=None, address=None):
    require_workspace_permissions(user, 'events.view_event', 'events.change_event' if pk else 'events.add_event')
    saved_file = None
    try:
        with transaction.atomic():
            item = Event.objects.select_for_update().get(pk=pk) if pk else Event(created_by=user)
            if item.status in ('published', 'cancelled'):
                require_workspace_permissions(user, 'events.publish_event')
            previous = {name: str(getattr(item, name)) for name in EventForm.Meta.fields}
            old_image = item.image.name
            old_program_id = item.application_program_id
            old_terms = Event.objects.get(pk=pk) if pk else None
            expected_version = item.version
            form = EventForm(data, files, instance=item, user=user)
            if data.get("application_program"):
                require_workspace_permissions(user, "programs.view_program")
            if not form.is_valid():
                raise ValidationError([str(message) for errors in form.errors.values() for message in errors])
            if expected_version != form.cleaned_data['version']:
                raise ValidationError('This event changed. Reload the page before continuing.')
            guard_event(old_terms, item)
            guard_participation(old_terms, item)
            if old_program_id and old_program_id != item.application_program_id:
                from programs.models import ProgramApplication
                if ProgramApplication.objects.filter(program_id=old_program_id).exists():
                    raise ValidationError('Preserve the event application context once applications exist.')
            if pk and item.capacity is not None and item.capacity < occupied_slots(item):
                raise ValidationError('Capacity cannot be below the number of occupied slots.')
            item = form.save(commit=False)
            if item.image and not item.image._committed:
                item.image.save(item.image.name, item.image.file, save=False)
                saved_file = (item.image.storage, item.image.name)
                remember_event_upload(saved_file)
            item.updated_by = user
            item.version += 1
            item.save()
            changes = {name: {'before': previous[name], 'after': str(getattr(item, name))}
                       for name in previous if previous[name] != str(getattr(item, name))}
            record_log(item, 'updated' if pk else 'created', form.cleaned_data.get('notes', 'Event saved as a private draft.'),
                       user=user, changes=changes, address=address)
            if old_image and old_image != item.image.name and not retain_event_images():
                transaction.on_commit(lambda: remove_file(item.image.storage, old_image))
            return item
    except Exception:
        if saved_file:
            remove_file(*saved_file)
        raise


@event_writer(publication=True)
@terms_lock()
@transaction.atomic
def change_publication(pk, *, user, version, action, notes, address=None):
    require_workspace_permissions(user, 'events.view_event', 'events.publish_event')
    item = Event.objects.select_for_update().get(pk=pk)
    check_version(item, version)
    check_notes(notes)
    if action not in Event.Status.values or action == item.status:
        raise ValidationError('Select a different, valid event status.')
    if action == 'cancelled' and item.published_at is None:
        raise ValidationError('Archive an unpublished draft instead of cancelling it.')
    before = item.status
    item.status = action
    if action == 'published':
        require_participation_details(item, scheduled=True)
        item.published_at = timezone.now()
        item.full_clean()
        if item.image and not item.image.storage.exists(item.image.name):
            raise ValidationError('Replace or remove the missing image before publishing.')
    item.version += 1
    item.updated_by = user
    item.save()
    record_log(item, action, notes.strip(), user=user, changes={'status': {'before': before, 'after': action}}, address=address)
    return item


def publish_event(pk, *, user, version, address=None):
    # Supply the automatic audit text before entering the guarded event writer,
    # so its audit verification sees the same reason as the recorded action.
    return change_publication(pk, user=user, version=version, action='published',
        notes='Published from the event review.', address=address)


@transaction.atomic
def register_member(pk, *, version, control_number, full_name, birthdate, contact_number):
    raise ValidationError('Use the linked member-only Program Application for this event.')


@transaction.atomic
def change_registration(pk, *, user, version, status, notes, address=None):
    require_workspace_permissions(user, 'events.view_event', 'events.view_eventregistration', 'events.change_eventregistration')
    event_id = EventRegistration.objects.values_list('event_id', flat=True).get(pk=pk)
    event = Event.objects.select_for_update().get(pk=event_id)
    registration = EventRegistration.objects.select_for_update().get(pk=pk)
    check_version(registration, version)
    check_notes(notes)
    if status not in EventRegistration.Status.values or status == registration.status:
        raise ValidationError('Choose a different, valid registration status.')
    if status != 'cancelled' and event.status in ('draft', 'cancelled'):
        raise ValidationError('Publish this event before changing participation or attendance.')
    if status in ('attended', 'absent') and timezone.now() < event.starts_at:
        raise ValidationError('Record attendance only after the event starts.')
    if registration.status == 'cancelled' and status != 'cancelled':
        member = Member.objects.select_for_update().get(pk=registration.member_id)
        if not member.is_active or member.archived_at:
            raise ValidationError('Only an active member can have a cancelled registration restored.')
        if event.status != 'published':
            raise ValidationError('Restore registrations only on a published event.')
        if event.capacity is not None and occupied_slots(event) >= event.capacity:
            raise ValidationError('No slot is available to restore this registration.')
    before = registration.status
    registration.status = status
    registration.version += 1
    registration.save()
    record_log(event, 'registration_updated', notes.strip(), user=user, registration=registration,
               changes={'status': {'before': before, 'after': status}}, address=address)
    return registration


def record_attendance_log(item, *, user, action, notes, changes, address=None):
    return EventAttendanceLog.objects.create(attendance=item, actor=user, actor_label=user.get_username(),
        action=action, notes=notes, changes=changes, address=address or None)


@transaction.atomic
def save_attendance(event_id, *, user, data, reference=None, address=None):
    require_workspace_permissions(user, 'events.view_event', 'events.view_eventattendance',
        'events.change_eventattendance' if reference else 'events.add_eventattendance')
    if data.get('member'):
        require_workspace_permissions(user, 'members.view_member')
    event = Event.objects.select_for_update().get(pk=event_id)
    form = OpenAttendanceForm(data, user=user)
    if not form.is_valid():
        raise ValidationError([str(message) for errors in form.errors.values() for message in errors])
    cleaned = form.cleaned_data
    if not reference:
        member = cleaned.get('member')
        if not member or not event.application_program_id:
            raise ValidationError('New organizational attendance requires a selected Verified Member from this event’s Program Application. Historical attendance remains available for correction.')
        from programs.models import ProgramApplication
        from programs.workflow import require_verified_photo
        application = ProgramApplication.objects.filter(program_id=event.application_program_id, member=member,
            status__in=['SELECTED', 'COMPLETED']).first()
        if not application or not member.is_active or member.archived_at:
            raise ValidationError('Only current selected participants can be recorded for this organizational event.')
        require_verified_photo(application, member)
    if reference:
        item = EventAttendance.objects.select_for_update().get(pk=reference, event=event)
        if 'member' in cleaned and (cleaned['member'].pk if cleaned['member'] else None) != item.member_id:
            raise ValidationError('Preserve the historical member association. Do not convert old attendance into a new application.')
        if cleaned['submission_key'] != item.pk:
            raise ValidationError('Reload this attendance record before continuing.')
        check_version(item, cleaned['version'])
    else:
        if cleaned['version'] != 0:
            raise ValidationError('Reload the new attendance form before continuing.')
        item = EventAttendance(reference=cleaned['submission_key'], event=event)
    previous = {name: str(getattr(item, name) or '') for name in ('attendee_name', 'member_id', 'status')}
    item.attendee_name = cleaned['attendee_name']
    item.status = cleaned['status']
    if 'member' in cleaned:
        item.member = cleaned['member']
    current = {name: str(getattr(item, name) or '') for name in previous}
    if not reference:
        existing = EventAttendance.objects.filter(pk=item.pk).first()
        if existing:
            original = existing.history.filter(action='recorded').first()
            if (existing.event_id == event.pk and original and original.actor_id == user.pk
                    and original.notes == cleaned['notes']
                    and all(original.changes.get('member' if name == 'member_id' else name, {}).get('after') == value
                            for name, value in current.items())):
                return existing  # The same submitted form is safe to retry.
            raise ValidationError('This attendance form has already been used. Open a new form.')
    if event.status in ('draft', 'cancelled') or event.published_at is None:
        raise ValidationError('Publish this event before recording attendance.')
    if timezone.now() < event.starts_at:
        raise ValidationError('Record attendance only after the event starts.')
    changes = {('member' if name == 'member_id' else name): {'before': previous[name] if reference else '', 'after': value}
               for name, value in current.items() if not reference or previous[name] != value}
    if not changes:
        raise ValidationError('Change the attendee name, member link or attendance status before saving.')
    item.version += 1
    item.full_clean()
    item.save()
    record_attendance_log(item, user=user, action='corrected' if reference else 'recorded',
        notes=cleaned['notes'], changes=changes, address=address)
    return item


# Annual observances use their own aggregate, permissions and audit history.
OBSERVANCE_CONTENT_FIELDS = (
    'title', 'target_audience', 'who_may_participate', 'month', 'category', 'recurrence_kind', 'recurrence_rule', 'day_start',
    'day_end', 'legal_basis', 'source_url', 'description', 'image', 'image_alt',
)
OBSERVANCE_SNAPSHOT_FIELDS = (*OBSERVANCE_CONTENT_FIELDS, 'status', 'published_at', 'published_by_label')
OBSERVANCE_TRANSITIONS = {
    'draft': (('published', 'Publish'), ('archived', 'Archive')),
    'published': (('draft', 'Withdraw to draft'), ('archived', 'Archive')),
    'archived': (('draft', 'Restore to draft'),),
}


def observance_storage_ready():
    """Keep public pages safe while the separately approved local migration is pending.

    No exception fallback, migration, cache, or reference-catalogue publication.
    """
    from django.db import connection
    from .models import AnnualObservance, AnnualObservanceRevision, AnnualObservanceLog
    tables = set(connection.introspection.table_names())
    return all(model._meta.db_table in tables for model in (
        AnnualObservance, AnnualObservanceRevision, AnnualObservanceLog))


def _observance_actor(user, *permissions):
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied
    if not (user.is_authenticated and user.is_active and user.is_staff):
        raise PermissionDenied
    try:
        actor = get_user_model().objects.get(pk=user.pk)
    except get_user_model().DoesNotExist:
        raise PermissionDenied
    require_workspace_permissions(actor, 'events.view_annualobservance', *permissions)
    return actor


def _observance_snapshot(item):
    return {name: item.image.name if name == 'image' else getattr(item, name)
            for name in OBSERVANCE_SNAPSHOT_FIELDS}


def _record_observance(item, *, actor, action, reason, before, address=None):
    from .models import AnnualObservanceRevision, AnnualObservanceLog
    after = _observance_snapshot(item)
    revision = AnnualObservanceRevision.objects.create(observance=item, version=item.version,
        actor=actor, actor_label=actor.get_username(), action=action, reason=reason, **after)
    changes = {name: {'before': str(before.get(name, '')), 'after': str(value)}
               for name, value in after.items() if before.get(name) != value}
    AnnualObservanceLog.objects.create(observance=item, revision=revision, version=item.version,
        actor=actor, actor_label=actor.get_username(), action=action, reason=reason,
        changes=changes, address=address or None)


def save_observance(*, user, data, files=None, pk=None, address=None, creation_id=None, publish=False,
                    simplified_editor=False):
    from .models import AnnualObservance
    from .observance_forms import AnnualObservanceEditForm, AnnualObservanceForm
    permissions = ['events.change_annualobservance' if pk else 'events.add_annualobservance']
    if publish:
        permissions.append('events.publish_annualobservance')
    actor = _observance_actor(user, *permissions)
    saved_file = None
    try:
        with transaction.atomic():
            item = AnnualObservance.objects.select_for_update().get(pk=pk) if pk else AnnualObservance(
                created_by=actor, **({'id': creation_id} if creation_id is not None else {}))
            if item.status != 'draft' and not (publish and item.status == 'published'):
                raise ValidationError('Withdraw or restore this observance to draft before editing.')
            before = _observance_snapshot(item) if pk else {}
            expected = item.version if pk else 0
            form_class = AnnualObservanceEditForm if simplified_editor else AnnualObservanceForm
            form = form_class(data, files, instance=item, publishing=publish)
            if not form.is_valid():
                raise ValidationError([str(message) for errors in form.errors.values() for message in errors])
            if form.cleaned_data['version'] != expected:
                raise ValidationError('This observance changed. Reload the page before continuing.')
            item = form.save(commit=False)
            if publish:
                require_participation_details(item)
            if item.image and not item.image._committed:
                item.image.save(item.image.name, item.image.file, save=False)
                saved_file = (item.image.storage, item.image.name)
            if publish:
                if item.image and not item.image.storage.exists(item.image.name):
                    raise ValidationError('Replace or remove the missing photo before publishing.')
                item.status = 'published'
                item.published_at = timezone.now()
                item.published_by = actor
                item.published_by_label = actor.get_username()
            item.updated_by = actor
            item.version = expected + 1
            item.full_clean()
            item.save(force_insert=not pk)
            _record_observance(item, actor=actor, action='published' if publish else ('updated' if pk else 'created'),
                reason=form.cleaned_data['notes'], before=before, address=address)
            # Earlier files remain referenced by immutable history, even after removal.
            return item
    except Exception:
        if saved_file:
            remove_file(*saved_file)
        raise


@transaction.atomic
def change_observance_publication(pk, *, user, version, action, notes, address=None):
    from .models import AnnualObservance
    actor = _observance_actor(user, 'events.publish_annualobservance')
    item = AnnualObservance.objects.select_for_update().get(pk=pk)
    check_version(item, version)
    check_notes(notes)
    if action not in dict(OBSERVANCE_TRANSITIONS[item.status]):
        raise ValidationError('Choose an allowed publication change.')
    before = _observance_snapshot(item)
    if action == 'published':
        require_participation_details(item)
    item.status = action
    item.published_at = timezone.now() if action == 'published' else None
    item.published_by = actor if action == 'published' else None
    item.published_by_label = actor.get_username() if action == 'published' else ''
    if action == 'published' and item.image and not item.image.storage.exists(item.image.name):
        raise ValidationError('Replace or remove the missing photo before publishing.')
    item.updated_by = actor
    item.version += 1
    item.full_clean()
    item.save()
    _record_observance(item, actor=actor, action=action, reason=notes.strip(), before=before, address=address)
    return item
