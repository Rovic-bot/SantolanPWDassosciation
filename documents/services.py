import hashlib
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.permissions import require_workspace_permissions
from members.models import Member
from ewaf.member_invalidation import member_writer
from .models import MembershipApplicationDocument, DocumentVerification


def file_digest(document):
    try:
        with document.file.open('rb') as source:
            return hashlib.file_digest(source, 'sha256').hexdigest()
    except OSError:
        return None


def reusable_documents(member, requirements):
    if not member or not member.is_active or member.archived_at:
        return {}
    found = {}
    documents = MembershipApplicationDocument.objects.filter(application_id=member.application_id).select_related('requirement')
    by_type = {}
    for document in documents:
        review = document.verifications.first()
        if (review and review.verified and review.member_version == member.version
                and (review.expires_on is None or review.expires_on >= timezone.localdate())
                and file_digest(document) == review.file_digest):
            by_type[document.requirement.document_type_id] = (document, review)
    for requirement in requirements:
        if requirement.get('reusable_document_type_id') in by_type:
            found[requirement['id']] = by_type[requirement['reusable_document_type_id']]
    return found


def program_document_current(document, member):
    if not document.file.storage.exists(document.file.name):
        return False
    if not document.source_document_id:
        return True  # Applicant uploads still require the Admin eligibility checklist.
    review = document.source_document.verifications.first()
    return bool(review and review.pk == document.source_verification_id and review.verified
                and review.member_version == member.version
                and (review.expires_on is None or review.expires_on >= timezone.localdate())
                and file_digest(document) == review.file_digest)


def mark_document_reviewed(document_id, *, user, member_version, review_id, document_digest):
    """Record the officer's one-click review without changing a recorded expiry."""
    from programs.terms import terms_lock
    require_workspace_permissions(user, 'members.view_member',
        'documents.view_membershipapplicationdocument', 'documents.verify_document')
    # Use the same first lock as all member/document writers. The existing writer
    # below retains its audit, transaction and source-invalidation protections.
    with terms_lock():
        document = MembershipApplicationDocument.objects.get(pk=document_id)
        from membership.registration_handoff import require_linked_access
        require_linked_access(document.application_id, user, documents=True)
        member = Member.objects.get(application_id=document.application_id)
        if member.version != member_version:
            raise ValidationError('The Member record changed. Reload before reviewing this document.')
        digest = file_digest(document)
        if not digest:
            raise ValidationError('The private document is unavailable.')
        if digest != document_digest:
            raise ValidationError('The document changed. Reload and preview it before reviewing.')
        latest = document.verifications.first()
        if (latest and latest.verified and latest.member_version == member.version
                and latest.file_digest == digest
                and (latest.expires_on is None or latest.expires_on >= timezone.localdate())):
            return latest  # Repeated clicks/retries must not duplicate review history.
        if (latest.pk if latest else 0) != review_id:
            raise ValidationError('The document review changed. Reload before reviewing it again.')
        return verify_document(document_id, user=user, member_version=member_version,
            verified=True, expires_on=latest.expires_on if latest else None,
            reason='Document marked reviewed from the applicant page.')


@member_writer('document')
@transaction.atomic
def verify_document(document_id, *, user, member_version, verified, expires_on, reason):
    require_workspace_permissions(user, 'members.view_member', 'documents.view_membershipapplicationdocument', 'documents.verify_document')
    document = MembershipApplicationDocument.objects.select_related('application').get(pk=document_id)
    from membership.registration_handoff import require_linked_access
    require_linked_access(document.application_id, user, documents=True)
    member = Member.objects.select_for_update().get(application=document.application)
    if member.version != member_version:
        raise ValidationError('The Member record changed. Reload before reviewing this document.')
    if not reason.strip():
        raise ValidationError('Record a reason for the document review.')
    if expires_on and expires_on < timezone.localdate() and verified:
        raise ValidationError('An expired document cannot be marked current and verified.')
    digest = file_digest(document)
    if not digest:
        raise ValidationError('The private document is unavailable.')
    review = DocumentVerification.objects.create(document=document, verified=verified, expires_on=expires_on,
        member_version=member.version, file_digest=digest, reason=reason.strip(), reviewer=user, reviewer_label=user.get_username())
    from members.services import record_event
    record_event(member, user, 'document_verified' if verified else 'document_verification_failed', reason,
        {'document': {'before': None, 'after': str(document.pk)}, 'review': {'before': None, 'after': review.pk}})
    return review
