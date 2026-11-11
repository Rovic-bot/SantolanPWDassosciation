from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.utils.crypto import salted_hmac
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from accounts.decorators import dashboard_required
from accounts.backends import reserve_windows
from documents.models import MembershipApplicationDocument
from .forms import ApplicationForm, DecisionForm, PROFILE_FIELDS, VerificationForm, QuickApprovalForm
from .guidance import membership_guidance
from .models import MembershipApplication, MembershipSettings, SubmissionWindow
from .services import approve_checked_application, decide_application, record_event, record_verification, require_capability, submit_application
from ewaf.access_invalidation import membership_access_writer
from members.profile import profile_sections
from .registration_policy import available as registration_available
from .registration_handoff import require_linked_access


@never_cache
@require_safe
def register(request):
    from core.content import published_content
    from .pdf_registration_forms import AssociationPDFForm, SOURCE_LINKS
    is_open = registration_available('public')
    preview_sections = ()
    if not is_open:
        # Display the applicant form without accepting data, creating a session,
        # or requiring the pending-intake schema/policy to be operational.
        preview = AssociationPDFForm(prefix='preview')
        for field in preview.fields.values():
            field.disabled = True
        preview_sections = preview.profile_sections
    return render(request, 'membership/guidelines.html', {
        **membership_guidance(),
        'registration_source_links': SOURCE_LINKS,
        'membership_content': published_content('membership'),
        'contact_content': published_content('contact'),
        'registration_available': is_open,
        'pdao_registration_available': getattr(settings, 'PDAO_REGISTRATION_ENABLED', False),
        'registration_preview_sections': preview_sections,
    })


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def encode(request):
    require_capability(request.user, 'membership.encode_membershipapplication')
    # Current Association intake shares the online applicant contract and its
    # pending review. Retain the historical writer for older policy/role setups.
    if (registration_available('staff')
            and settings.ASSOCIATION_REGISTRATION_POLICY.get('applicant_profile') == 'association_pdf_v1'
            and request.user.has_perms(['membership.view_registrationintake',
                                       'membership.encode_registrationintake'])):
        from .registration_views import encode as encode_registration
        return encode_registration(request, channel='walk_in')
    form = ApplicationForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    status = 200
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The combined uploads exceed the limit. Choose smaller files.')
            status = 413
        elif form.is_valid():
            try:
                application = submit_application(form, user=request.user, address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Onsite registration recorded. Complete manual verification and membership review.')
                return redirect('membership:detail', reference=application.reference)
    return render(request, 'membership/encode.html', {**membership_guidance(), 'form': form,
        'registration_retrieval_available': registration_available('staff') and request.user.has_perm('membership.view_registrationintake'),
        'file_limit_mb': settings.MEMBERSHIP_FILE_MAX_BYTES // 1048576,
        'total_limit_mb': settings.MEMBERSHIP_TOTAL_MAX_BYTES // 1048576}, status=status)


@never_cache
@require_safe
def submitted(request):
    return redirect('core:membership')


@never_cache
@dashboard_required
@require_safe
def application_list(request):
    require_capability(request.user, 'membership.view_membershipapplication')
    # The owner retired the separate "Other onsite applications" list. Keep
    # bookmarked URLs safe without deleting legacy records or their audit trail.
    return redirect('membership:review_home')


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def application_detail(request, reference):
    require_capability(request.user, 'membership.view_membershipapplication')
    application = get_object_or_404(MembershipApplication.objects.select_related('prpwd_verified_by', 'decided_by'), reference=reference)
    require_linked_access(application.pk, request.user)
    verification_form = VerificationForm(initial={'version': application.version}, auto_id='verify_%s')
    decision_form = DecisionForm(initial={'version': application.version}, auto_id='decision_%s')
    approval_form = QuickApprovalForm(initial={'version': application.version}, auto_id='approve_%s')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ('verify', 'decide', 'approve'):
            return render(request, '400.html', status=400)
        capability = 'membership.verify_membershipapplication' if action == 'verify' else 'membership.decide_membershipapplication'
        require_capability(request.user, capability)
        form = (QuickApprovalForm(request.POST, auto_id='approve_%s') if action == 'approve' else
                VerificationForm(request.POST, auto_id='verify_%s') if action == 'verify'
                else DecisionForm(request.POST, auto_id='decision_%s'))
        if action == 'approve':
            approval_form = form
        elif action == 'verify':
            verification_form = form
        else:
            decision_form = form
        if form.is_valid():
            try:
                service = approve_checked_application if action == 'approve' else record_verification if action == 'verify' else decide_application
                service(reference, user=request.user, address=request.META.get('REMOTE_ADDR'), **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Membership approved.' if action == 'approve' else 'Verification saved.' if action == 'verify' else 'Membership decision saved.')
                return redirect('membership:detail', reference=reference)
    documents = list(application.documents.all())
    uploaded_ids = {doc.requirement_id for doc in documents}
    return render(request, 'membership/detail.html', {
        **membership_guidance(),
        'application': application, 'verification_form': verification_form, 'decision_form': decision_form,
        'approval_form': approval_form,
        'profile_sections': profile_sections(application),
        'documents': documents,
        'missing_documents': [item for item in application.requirements_snapshot if item['id'] not in uploaded_ids],
        'policy': MembershipSettings.objects.filter(pk=1).first(),
    })


@never_cache
@dashboard_required
@require_safe
@membership_access_writer(intake=True)
def download_document(request, document_id):
    require_capability(request.user, 'documents.view_membershipapplicationdocument')
    document = get_object_or_404(MembershipApplicationDocument.objects.select_related('application'), pk=document_id)
    require_linked_access(document.application_id, request.user, documents=True)
    try:
        handle = document.file.open('rb')
    except FileNotFoundError:
        raise Http404('This document is unavailable. Contact the administrator.')
    try:
        record_event(document.application, 'document_downloaded', 'Private application document downloaded.',
                     request.user, request.META.get('REMOTE_ADDR'))
    except Exception:
        handle.close()
        raise
    response = FileResponse(handle, as_attachment=request.GET.get('preview') != '1',
        filename=f'document-{document.pk}{Path(document.file.name).suffix}', content_type=document.content_type)
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['X-Content-Type-Options'] = 'nosniff'
    return response
