import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.permissions import require_workspace_permissions
from .forms import AnnouncementForm, AnnouncementComposerForm
from .models import Announcement, AnnouncementEvent

logger = logging.getLogger(__name__)


def record_event(item, user, action, description, address):
    AnnouncementEvent.objects.create(announcement=item, actor=user, actor_label=user.get_username(),
        action=action, description=description, address=address or None)


def remove_file(storage, name):
    try:
        storage.delete(name)
    except OSError:
        logger.exception('Could not remove an obsolete announcement image.')


def save_announcement(*, user, data, files=None, pk=None, address=None, composer=False):
    require_workspace_permissions(user, 'announcements.view_announcement',
                                  'announcements.change_announcement' if pk else 'announcements.add_announcement')
    saved_file = None
    try:
        with transaction.atomic():
            item = Announcement.objects.select_for_update().get(pk=pk) if pk else Announcement(created_by=user)
            if item.program_id:
                raise ValidationError('Program applicant announcements are generated from application records; their content cannot be manually edited.')
            if item.status == 'deleted':
                raise ValidationError('Deleted announcements cannot be edited.')
            if item.status == 'published':
                require_workspace_permissions(user, 'announcements.publish_announcement')
            if item.linked_program_id:
                require_workspace_permissions(user, 'programs.view_program')
            previous = {name: str(getattr(item, name)) for name in
                        ('title', 'content', 'image', 'image_alt', 'source_office', 'linked_program_id', 'status')}
            old_image = item.image.name
            expected_version = item.version
            form_class = AnnouncementComposerForm if composer else AnnouncementForm
            form = form_class(data, files, instance=item, user=user)
            if not form.is_valid():
                raise ValidationError([str(message) for errors in form.errors.values() for message in errors])
            if form.cleaned_data['version'] != expected_version:
                raise ValidationError('Another administrator changed this announcement. Reload the page before continuing.')
            item = form.save(commit=False)
            item.status = Announcement.Status.DRAFT
            if item.image and not item.image._committed:
                item.image.save(item.image.name, item.image.file, save=False)
                saved_file = (item.image.storage, item.image.name)
            item.updated_by = user
            item.version += 1
            item.save()
            changed = [name for name in previous if previous[name] != str(getattr(item, name))]
            record_event(item, user, 'updated' if pk else 'created',
                         'Saved for review as a private draft. Updated: ' + ', '.join(changed) if pk else 'Announcement saved as a private draft.', address)
            if old_image and old_image != item.image.name:
                transaction.on_commit(lambda: remove_file(item.image.storage, old_image))
            return item
    except Exception:
        if saved_file:
            remove_file(*saved_file)
        raise


@transaction.atomic
def change_publication(pk, *, user, version, action, address=None):
    require_workspace_permissions(user, 'announcements.view_announcement',
        'announcements.delete_announcement' if action == 'deleted' else 'announcements.publish_announcement')
    if action == 'published' and Announcement.objects.filter(pk=pk, program__isnull=False).exists():
        from .results import publish_results
        return publish_results(pk, user=user, version=version, address=address)
    item = Announcement.objects.select_for_update().get(pk=pk)
    if item.version != version:
        raise ValidationError('Another administrator changed this announcement. Reload the page before continuing.')
    if action not in Announcement.Status.values or item.status == 'deleted' or action == item.status:
        raise ValidationError('This publication change is not available.')
    previous = item.status
    item.status = action
    if action == 'published':
        if not item.source_office.strip():
            raise ValidationError('Identify the responsible source or office before publishing.')
        if item.linked_program_id:
            from .notices import announcement_programs
            require_workspace_permissions(user, 'programs.view_program')
            if not announcement_programs().filter(pk=item.linked_program_id).exists():
                raise ValidationError('The linked program must be available or upcoming and published before this notice can be published.')
        if not item.title.strip() or not item.content.strip() or (item.image and not item.image_alt.strip()):
            raise ValidationError('Complete the announcement and image description before publishing.')
        if item.image and not item.image.storage.exists(item.image.name):
            raise ValidationError('The image is missing. Replace or remove it before publishing.')
        item.published_at = timezone.now()
    item.updated_by = user
    item.version += 1
    item.save()
    record_event(item, user, action, f'Status changed from {previous} to {action}.', address)
    return item
