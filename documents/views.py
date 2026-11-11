from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from members.models import Member
from .forms import ReviewForm
from .models import MembershipApplicationDocument
from .services import verify_document


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def review(request, document_id):
    require_workspace_permissions(request.user, 'members.view_member', 'documents.view_membershipapplicationdocument', 'documents.verify_document')
    document = get_object_or_404(MembershipApplicationDocument, pk=document_id)
    from membership.registration_handoff import require_linked_access
    require_linked_access(document.application_id, request.user, documents=True)
    member = get_object_or_404(Member, application_id=document.application_id)
    form = ReviewForm(request.POST if request.method == 'POST' else None, initial={'member_version': member.version})
    if request.method == 'POST' and form.is_valid():
        try:
            verify_document(document_id, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None,error)
        else:
            messages.success(request,'Document review saved with source provenance and history.')
            return redirect('documents:review', document_id=document_id)
    return render(request,'documents/review.html', {'form':form,'document':document,'member':member,'history':document.verifications.all()})
