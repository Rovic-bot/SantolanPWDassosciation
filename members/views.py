from pathlib import Path
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from documents.models import MembershipApplicationDocument
from .forms import MemberStatusForm
from .registration_form import member_edit_form
from .models import Member
from .services import change_status, record_event, update_member
from .profile import profile_sections
from .printing import registration_print_data
from .directory import directory_context, member_preview
from .portraits import member_portrait
from .registration_presentation import overview_details, registration_tabs
from .document_services import document_inventory
from ewaf.access_invalidation import membership_access_writer
from assistance.models import AssistanceRelease
from assistance.services import VIEW_PERMISSIONS, previous_assistance_count
from membership.registration_handoff import require_linked_access
from membership.registration_policy import RegistrationUnavailable


@never_cache
@dashboard_required
@require_safe
def member_list(request):
    require_workspace_permissions(request.user, 'members.view_member')
    status = request.GET.get('status', 'active')
    query = request.GET.get('q', '').strip()[:200]
    return render(request, 'members/list.html', directory_context(user=request.user, query=query,
                  status=status, disability=request.GET.get('disability', '').strip()[:20], page=request.GET.get('page')))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def member_detail(request, pk):
    require_workspace_permissions(request.user, 'members.view_member')
    member = get_object_or_404(Member.objects.select_related('application'), pk=pk)
    form = MemberStatusForm(initial={'version': member.version, 'status': member.status})
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'members.change_member_status')
        form = MemberStatusForm(request.POST)
        if form.is_valid():
            try:
                change_status(pk, user=request.user, address=request.META.get('REMOTE_ADDR'), **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Member status updated. History has been retained.')
                return redirect('members:detail', pk=pk)
    history = (Paginator(member.events.all(), 20).get_page(request.GET.get('page'))
               if request.user.has_perm('members.view_memberevent') else None)
    documents = (list(member.application.documents.select_related('requirement'))
                 if request.user.has_perm('documents.view_membershipapplicationdocument') else [])
    portrait, portrait_url = member_portrait(member, request.user, documents)
    can_view_assistance = request.user.has_perms([*VIEW_PERMISSIONS, 'assistance.view_assistancerelease'])
    from .review_services import available as reviews_available
    original_sections = None
    approval_email_context = {}
    if request.user.has_perm('membership.view_membershipapplication'):
        try:
            intake = require_linked_access(member.application_id, request.user)
            if intake:
                from membership.registration_services import audit_access
                audit_access(intake, user=request.user, action='staff_completed_form_viewed',
                             revision=intake.revisions.get(number=intake.current_revision))
            source = member.application.registration_profile
            original_sections = (source.get('profile_sections', []) + source.get('digital_sections', [])
                if source.get('profile_kind') == 'association_pdf_v1' else profile_sections(member.application))
            from membership.approval_email import notification_context
            approval_email_context = notification_context(intake, request.user)
        except (PermissionDenied, RegistrationUnavailable):
            # The Member Directory permission does not grant private intake access.
            pass
    return render(request, 'members/detail.html', {**approval_email_context, 'member': member, 'form': form, 'history': history,
        'original_registration_sections': original_sections,
        'original_registration_tabs': registration_tabs(original_sections),
        'member_overview': overview_details(member),
        'membership_documents': document_inventory(member, request.user, documents),
        'record_summary': member_preview(member, request.user), 'portrait': portrait, 'portrait_url': portrait_url,
        'reviews_available': reviews_available(),
        'can_view_assistance': can_view_assistance,
        'previous_assistance': previous_assistance_count(member) if can_view_assistance else None,
        'assistance_history': (Paginator(AssistanceRelease.objects.filter(application__member=member).select_related('application__program'), 10)
                               .get_page(request.GET.get('assistance_page')) if can_view_assistance else None),
        'event_history': (Paginator(member.event_registrations.select_related('event').order_by('-event__starts_at', '-pk'), 10)
                          .get_page(request.GET.get('event_page'))
                          if request.user.has_perms(['events.view_event', 'events.view_eventregistration']) else None),
        'open_attendance_history': (Paginator(member.event_attendance.select_related('event').order_by('-event__starts_at', '-pk'), 10)
                                    .get_page(request.GET.get('attendance_page'))
                                    if request.user.has_perms(['events.view_event', 'events.view_eventattendance']) else None),
        'documents': documents,
        'program_history': (Paginator(member.program_applications.select_related('program').order_by('-submitted_at', '-pk'), 10)
                            .get_page(request.GET.get('program_page'))
                            if request.user.has_perms(['programs.view_program', 'programs.view_programapplication']) else None),
        'profile_sections': profile_sections(member)})


@never_cache
@dashboard_required
@require_safe
@xframe_options_sameorigin
def registration_print(request, pk):
    require_workspace_permissions(request.user, 'members.view_member', 'membership.view_membershipapplication')
    member = get_object_or_404(Member.objects.select_related('application'), pk=pk,
                               application__status='approved')
    try:
        intake = require_linked_access(member.application_id, request.user)
        if intake:
            from membership.registration_services import audit_access
            revision = intake.revisions.get(number=intake.current_revision)
            audit_access(intake, user=request.user, action='staff_completed_form_viewed', revision=revision)
    except RegistrationUnavailable:
        return render(request, 'membership/registration/unavailable.html', status=503)
    template = ('members/registration_print_document.html' if request.GET.get('preview') == '1'
                else 'members/registration_print.html')
    return render(request, template, {
        'member': member, 'submitted': registration_print_data(member.application),
        'reference': intake.reference if intake else member.application.reference,
        'reference_kind': 'association' if intake else 'membership',
        'revision_number': intake.current_revision if intake else None,
        'member_number': member.control_number, 'approved_at': member.application.decided_at,
    })


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def member_edit(request, pk):
    require_workspace_permissions(request.user, 'members.view_member', 'members.change_member')
    member = get_object_or_404(Member, pk=pk)
    form = member_edit_form(request.POST if request.method == 'POST' else None, request.FILES or None, instance=member)
    if getattr(request, 'upload_limit_exceeded', False):
        form.add_error(None, 'The upload exceeded the allowed size. No changes were saved.')
        return render(request, 'members/edit.html', {'form': form, 'member': member,
            'membership_documents': document_inventory(member, request.user)}, status=413)
    if request.method == 'POST' and form.is_valid():
        try:
            update_member(pk, user=request.user, version=form.cleaned_data['version'],
                data=request.POST,
                files=request.FILES or None,
                notes=form.cleaned_data['notes'], address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Member profile updated. Original registration details and earlier documents are retained.')
            return redirect('members:detail', pk=pk)
    return render(request, 'members/edit.html', {'member': member, 'form': form,
        'membership_documents': document_inventory(member, request.user)})


@never_cache
@dashboard_required
@require_safe
@membership_access_writer()
def download_document(request, pk, document_id):
    require_workspace_permissions(request.user, 'members.view_member', 'documents.view_membershipapplicationdocument')
    member = get_object_or_404(Member, pk=pk)
    document = get_object_or_404(MembershipApplicationDocument, pk=document_id, application_id=member.application_id)
    require_linked_access(document.application_id, request.user, documents=True)
    try:
        handle = document.file.open('rb')
    except FileNotFoundError:
        raise Http404('This document is unavailable.')
    try:
        record_event(member, request.user, 'document_downloaded', 'Private membership document downloaded.',
                     address=request.META.get('REMOTE_ADDR'))
    except Exception:
        handle.close()
        raise
    response = FileResponse(handle, as_attachment=request.GET.get('preview') != '1',
        filename=f'document-{document.pk}{Path(document.file.name).suffix}', content_type=document.content_type)
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['X-Content-Type-Options'] = 'nosniff'
    return response
