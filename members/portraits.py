"""Resolve an existing private membership photo without copying its file."""
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from membership.registration_handoff import require_linked_access
from membership.registration_policy import RegistrationUnavailable
from membership.registration_services import active_attachments


def member_portrait(member, user, documents):
    try:
        intake = require_linked_access(member.application_id, user, documents=True)
    except (PermissionDenied, RegistrationUnavailable):
        return None, ''

    if user.has_perm('documents.view_membershipapplicationdocument'):
        updated = member.document_uploads.filter(slot='photo_2x2', content_type__in=('image/jpeg', 'image/png')).first()
        if updated:
            return updated, reverse('members:uploaded_document', args=[member.pk, updated.pk]) + '?preview=1'

    photos = {document.requirement.capture_key: document for document in documents
              if document.requirement.capture_key in ('photo_2x2', 'photo_1x1')
              and document.content_type in ('image/jpeg', 'image/png')}
    photo = photos.get('photo_2x2')
    if not photo and intake:
        revision = intake.revisions.get(number=intake.current_revision)
        photo = active_attachments(revision).filter(
            slot='photo_2x2', content_type__in=('image/jpeg', 'image/png')).first()
        if photo:
            return photo, reverse('membership:registration_document', args=[photo.pk]) + '?preview=1'
    photo = photo or photos.get('photo_1x1')
    if photo:
        return photo, reverse('members:document', args=[member.pk, photo.pk]) + '?preview=1'
    return None, ''
