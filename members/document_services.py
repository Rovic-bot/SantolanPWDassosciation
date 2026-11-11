"""Resolve private registration uploads and retain member-upload replacements."""
import hashlib
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.urls import reverse

from core.permissions import require_workspace_permissions
from ewaf.membership_invalidation import remember_membership_upload
from membership.registration_handoff import require_linked_access
from membership.registration_policy import RegistrationUnavailable, SLOTS
from membership.registration_services import active_attachments
from .document_models import MemberDocumentUpload, member_document_write


def document_label(slot, alternative=''):
    if slot == 'civil_document' and alternative in ('birth', 'marriage'):
        return {'birth': 'Birth Certificate', 'marriage': 'Marriage Certificate'}[alternative]
    return SLOTS.get(slot, slot)


def document_inventory(member, user, legacy_documents=None):
    try:
        intake = require_linked_access(member.application_id, user, documents=True)
    except (PermissionDenied, RegistrationUnavailable):
        return {'allowed': False, 'current': [], 'previous': []}
    legacy_allowed = user.has_perm('documents.view_membershipapplicationdocument')
    current, previous = {}, []
    if legacy_allowed:
        documents = legacy_documents if legacy_documents is not None else member.application.documents.select_related('requirement')
        for doc in documents:
            url = reverse('members:document', args=[member.pk, doc.pk])
            key = doc.requirement.capture_key or str(doc.pk)
            current[key] = {'label': doc.label, 'url': url, 'preview_url': url + '?preview=1',
                'review_url': reverse('documents:review', args=[doc.pk]), 'uploaded_at': doc.uploaded_at}
    if intake:
        revision = intake.revisions.get(number=intake.current_revision)
        for doc in active_attachments(revision):
            url = reverse('membership:registration_document', args=[doc.pk])
            if doc.slot in current:
                previous.append(current[doc.slot])
            current[doc.slot] = {'label': document_label(doc.slot, doc.alternative), 'url': url,
                'preview_url': url + '?preview=1', 'uploaded_at': doc.uploaded_at}
    if legacy_allowed:
        # Apply versions oldest first; the final item for each slot is current.
        for doc in member.document_uploads.order_by('member_version', 'uploaded_at', 'pk'):
            url = reverse('members:uploaded_document', args=[member.pk, doc.pk])
            if doc.slot in current:
                previous.append(current[doc.slot])
            current[doc.slot] = {'label': document_label(doc.slot, doc.alternative), 'url': url,
                'preview_url': url + '?preview=1', 'uploaded_at': doc.uploaded_at}
    return {'allowed': legacy_allowed or intake is not None,
        'current': list(current.values()), 'previous': list(reversed(previous))}


def save_member_uploads(form, member, user):
    uploads = {slot: form.cleaned_data.get(slot) for slot in SLOTS if form.cleaned_data.get(slot)}
    if not uploads:
        return
    require_workspace_permissions(user, 'documents.view_membershipapplicationdocument')
    require_linked_access(member.application_id, user, documents=True)
    with member_document_write():
        for slot, upload in uploads.items():
            digest = hashlib.sha256()
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
            previous = member.document_uploads.filter(slot=slot).first()
            document = MemberDocumentUpload(member=member, member_version=member.version, slot=slot,
                alternative=form.cleaned_data.get('civil_alternative', '') if slot == 'civil_document' else '',
                original_name=Path(upload.name).name[:255], content_type=upload.content_type, size=upload.size,
                digest=digest.hexdigest(), predecessor=previous, actor=user, actor_label=user.get_username())
            document.file.save(upload.name, upload, save=False)
            remember_membership_upload((document.file.storage, document.file.name))
            document.save()
