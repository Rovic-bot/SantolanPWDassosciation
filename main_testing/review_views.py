"""Port-8000 document review with an authorized return to its applicant page."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from documents.forms import ReviewForm
from documents.models import MembershipApplicationDocument
from documents.services import file_digest, verify_document
from members.models import Member
from programs.models import ProgramApplication


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def document_review(request, document_id):
    require_workspace_permissions(request.user, 'members.view_member',
        'documents.view_membershipapplicationdocument', 'documents.verify_document')
    document = get_object_or_404(MembershipApplicationDocument, pk=document_id)
    member = get_object_or_404(Member, application_id=document.application_id)
    application = None
    if request.GET.get('application'):
        require_workspace_permissions(request.user, 'programs.view_program', 'programs.view_programapplication')
        from uuid import UUID
        from django.http import Http404
        try:
            reference = UUID(request.GET['application'])
        except ValueError:
            raise Http404
        application = get_object_or_404(ProgramApplication, pk=reference, member=member)
    latest = document.verifications.first()
    initial = {'member_version': member.version, 'verified': 'yes' if latest and latest.verified else 'no',
               'expires_on': latest.expires_on if latest else None}
    form = ReviewForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            # Preserve the existing source-writer lock and immutable review history.
            from programs.terms import terms_lock

            @terms_lock()
            def save():
                current = document.verifications.first()
                if (request.POST.get('review_id') != str(current.pk if current else 0)
                        or request.POST.get('document_digest') != file_digest(document)):
                    raise ValidationError('This document or its review changed. Reload and review the current version.')
                return verify_document(document_id, user=request.user, **form.cleaned_data)

            save()
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Document review saved. Earlier reviews are retained; affected eligibility must be checked again.')
            return redirect(request.get_full_path())
    return render(request, 'main_testing/document_review.html', {
        'form': form, 'document': document, 'member': member,
        'review_id': latest.pk if latest else 0, 'document_digest': file_digest(document),
        'history': document.verifications.all(),
        'applicant_url': reverse('programs:application_detail', args=[application.program_id, application.pk])
                         if application else None})
