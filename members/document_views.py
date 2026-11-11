from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from ewaf.access_invalidation import membership_access_writer
from membership.registration_handoff import require_linked_access
from .document_models import MemberDocumentUpload
from .models import Member
from .services import record_event


@never_cache
@dashboard_required
@require_safe
@membership_access_writer(member_upload=True)
def uploaded_document(request, pk, document_id):
    require_workspace_permissions(request.user, 'members.view_member', 'documents.view_membershipapplicationdocument')
    member = get_object_or_404(Member, pk=pk)
    require_linked_access(member.application_id, request.user, documents=True)
    document = get_object_or_404(MemberDocumentUpload, pk=document_id, member=member)
    try:
        handle = document.file.open('rb')
    except FileNotFoundError:
        raise Http404('This document is unavailable.') from None
    try:
        record_event(member, request.user, 'document_downloaded', 'Private membership document downloaded.',
                     address=request.META.get('REMOTE_ADDR'))
    except Exception:
        handle.close()
        raise
    preview = request.GET.get('preview') == '1' and document.content_type in ('application/pdf', 'image/jpeg', 'image/png')
    response = FileResponse(handle, as_attachment=not preview, content_type=document.content_type,
        filename=f'member-document-{document.pk}{Path(document.file.name).suffix}')
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['X-Content-Type-Options'] = 'nosniff'
    return response
