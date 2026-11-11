from pathlib import Path
from ewaf.access_invalidation import private_access_writer

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from members.models import Member
from .forms import ProgramSetupForm, RequirementForm, PublicationForm, PublishProgramForm, RegistrationForm, ApplicationForm, ApplicationStatusForm
from .models import Program, ProgramRequirement, ProgramApplication, ProgramDocument
from .services import (save_program, save_requirement, change_publication, change_application, verify_member,
                       reserve_verification, grant_valid, submit_application, record_log, require_disability)


def page(request, records, size=20):
    return Paginator(records, size).get_page(request.GET.get('page'))


def application_receipt_response(request, pk):
    if request.headers.get('X-Program-Application') == '1':
        return JsonResponse({'redirect': reverse('programs:submitted', args=[pk])})
    return redirect('programs:submitted', pk=pk)


@never_cache
@require_safe
def public_list(request):
    from .public_catalog import catalog_context
    return render(request, 'programs/public_catalog.html', catalog_context(request))


@never_cache
@require_safe
def public_detail(request, pk):
    at = timezone.now()
    program = get_object_or_404(Program.objects.public(at=at).with_public_application_status(at=at), pk=pk)
    from .application_workflow import enabled, availability
    if enabled() and program.public_application_status == 'open' and not availability(program):
        program.public_application_status = 'unavailable'
    from .public_deadlines import prepare_registration_notice
    prepare_registration_notice(program, at=at)
    return render(request, 'programs/public_detail.html', {'program': program,
        'requirements': program.configured_requirements.filter(is_active=True)})


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def verify(request, pk):
    program = get_object_or_404(Program.objects.public(), pk=pk)
    form = RegistrationForm(request.POST if request.method == 'POST' else None, initial={'version': program.version})
    if request.method == 'POST':
        request.session.pop('program_verification', None)
        if not reserve_verification(request.POST.get('control_number', '')[:100], request.META.get('REMOTE_ADDR', '')):
            response = render(request, 'programs/limited.html', {'program': program}, status=429)
            response['Retry-After'] = str(settings.PROGRAM_VERIFICATION_WINDOW_SECONDS)
            return response
        if form.is_valid():
            try:
                grant = verify_member(pk, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                request.session['program_verification'] = grant
                return redirect('programs:apply', pk=pk)
    return render(request, 'programs/verify.html', {'program': program, 'form': form})


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def apply(request, pk):
    program = get_object_or_404(Program.objects.public(), pk=pk)
    grant = request.session.get('program_verification')
    if not grant_valid(grant, program):
        return redirect('programs:verify', pk=pk)
    # Never reveal the stored member profile through the public verification flow.
    member = Member.objects.filter(pk=grant.get('member')).first()
    if not member or not member.is_active or member.archived_at or member.version != grant.get('member_version'):
        request.session.pop('program_verification', None)
        return redirect('programs:verify', pk=pk)
    try:
        require_disability(program, member)
    except ValidationError as error:
        request.session.pop('program_verification', None)
        return render(request, 'programs/ineligible.html', {'program': program, 'error': error.messages[0]}, status=400)
    existing = program.applications.filter(member=member).first()
    if existing and existing.status != 'CLOSED':
        request.session['program_receipt'] = str(existing.pk)
        return application_receipt_response(request, pk)
    from .application_workflow import CONTRACT
    form_class, initial = ApplicationForm, {}
    if grant.get('application_workflow') == CONTRACT:
        from .confirmation_forms import ConfirmedApplicationForm
        form_class = ConfirmedApplicationForm
        initial = {'applicant_name': grant.get('entered_name', '')}
    form = form_class(request.POST if request.method == 'POST' else None, request.FILES or None,
        program=program, member=member, initial=initial)
    status_code = 200
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The combined uploads are too large. Choose smaller files.')
            status_code = 413
        elif form.is_valid():
            try:
                application = submit_application(pk, grant=grant, data=request.POST, files=request.FILES)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                request.session['program_receipt'] = str(application.pk)
                request.session.pop('program_verification', None)
                return application_receipt_response(request, pk)
        if request.headers.get('X-Program-Application') == '1':
            return JsonResponse({'errors': form.errors.get_json_data()}, status=status_code if status_code != 200 else 422)
    return render(request, 'programs/apply.html', {'program': program, 'form': form,
        'confirmed_application': grant.get('application_workflow') == CONTRACT,
        'cancelled': bool(existing and existing.status == 'CLOSED'),
        'file_limit_mb': settings.MEMBERSHIP_FILE_MAX_BYTES // 1048576,
        'total_limit_mb': settings.MEMBERSHIP_TOTAL_MAX_BYTES // 1048576}, status=status_code)


@never_cache
@require_safe
def submitted(request, pk):
    program = get_object_or_404(Program.objects.public(), pk=pk)
    reference = request.session.get('program_receipt')
    application = program.applications.filter(pk=reference).first() if reference else None
    if not application:
        return redirect('programs:detail', pk=pk)
    from .tracking_views import tracking_url
    from .information_confirmation import declaration
    report = declaration(application)
    return private_status_response(render(request, 'programs/submitted.html', {
        'program': program, 'application': application,
        'information_change_reported': isinstance(report, dict) and report.get('current_information') in ('changed', 'uncertain'),
        'tracking_url': tracking_url(application.public_reference) if settings.PROGRAM_TRACKING_ENABLED else '',
    }))


def private_status_response(response):
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Cache-Control'] = 'no-store, private'
    return response


@never_cache
@require_safe
def application_status(request, token):
    return private_status_response(HttpResponse('Keep your Application Reference Number and monitor official Announcements. Contact the Barangay Santolan PWD Association Help Desk for assistance.', status=410, content_type='text/plain'))


@never_cache
@require_safe
def application_qr(request, token):
    return application_status(request, token)


@never_cache
@dashboard_required
@require_safe
def manage_list(request):
    require_workspace_permissions(request.user, 'programs.view_program')
    from .portfolio import portfolio_context
    return render(request, 'programs/manage_list.html', portfolio_context(request))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request, pk=None):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.change_program' if pk else 'programs.add_program')
    program = get_object_or_404(Program, pk=pk) if pk else Program()
    builder_request = request.headers.get('X-Program-Builder') == '1'
    if program.status in ('published', 'cancelled'):
        require_workspace_permissions(request.user, 'programs.publish_program')
    form = ProgramSetupForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=program)
    from .forms import NewRequirementFormSet
    from .services import save_program_with_requirements
    additions = NewRequirementFormSet(
        request.POST if request.method == 'POST' and 'requirements-TOTAL_FORMS' in request.POST else None,
        prefix='requirements')
    additions_valid = not additions.is_bound or additions.is_valid()
    if request.method == 'POST' and form.is_valid() and additions_valid:
        try:
            item = save_program_with_requirements(user=request.user, data=request.POST, files=request.FILES, pk=pk,
                requirements=[row for row in additions.cleaned_data if row] if additions.is_bound else [],
                address=request.META.get('REMOTE_ADDR'), setup_only=True)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            if builder_request:
                # Reuse the audited save service; return refreshed HTML, not a new API.
                return render(request, 'programs/builder/page.html', {
                    'program': item, 'form': ProgramSetupForm(instance=item), 'editing': True,
                    'additions': NewRequirementFormSet(prefix='requirements'),
                    'requirements': item.configured_requirements.all(), 'builder_saved': True,
                    'builder_created': not pk,
                })
            messages.success(request, 'Program updated.' if pk else 'Program saved. Review details and requirements before publishing.')
            return redirect('programs:manage_detail', pk=item.pk)
    return render(request, 'programs/builder/page.html', {'program': program, 'form': form, 'editing': bool(pk),
        'additions': additions, 'requirements': program.configured_requirements.all() if pk else []})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def manage_detail(request, pk=None):
    require_workspace_permissions(request.user, 'programs.view_program')
    if pk is None:
        pk = request.GET.get('program')
        if not pk:
            if request.method == 'POST':
                raise Http404('Select a program first.')
            return redirect('program_portfolio')
    try:
        program = get_object_or_404(Program.objects.prefetch_related('eligible_disability_types'), pk=pk)
    except (ValidationError, ValueError):
        raise Http404('Program not found.')
    pk = program.pk
    from .catalog import capacity_context
    capacity_context(program, request.user)
    program.applicant_count = program.applications.count()
    can_publish = request.user.has_perm('programs.publish_program') and program.status != 'published'
    publishing = request.method == 'POST' and request.POST.get('action') == 'published'
    publish_form = PublishProgramForm(request.POST if publishing else None,
        auto_id='id_publish_%s', initial={'version': program.version})
    actions = []
    if request.user.has_perm('programs.publish_program'):
        if program.status == 'published':
            actions = [('unpublish', 'Unpublish to draft')]
        elif program.status == 'draft':
            actions = [('archived', 'Archive')]
        else:
            actions = [('draft', 'Return to draft')]
    from .application_workflow import enabled as workflow_enabled, publication_configuration_problem
    if program.status == 'published' and not program.policy_authorized_at and request.user.has_perm('programs.publish_program'):
        actions.insert(0, ('authorize_policy', 'Authorize program policy'))
    archive_action = next((action for action, label in actions if action in ('unpublish', 'archived')), '')
    archive_label = 'Unpublish to draft' if archive_action == 'unpublish' else 'Archive program'
    requested_action = request.POST.get('action') if request.method == 'POST' else request.GET.get('action')
    archiving = bool(archive_action and requested_action == archive_action)
    if archiving:
        actions = [(archive_action, archive_label)]
    form = PublicationForm(request.POST if request.method == 'POST' and not publishing else None,
        actions=actions, archive_action=archive_action if archiving else '',
        initial={'version': program.version, 'action': archive_action})
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'programs.publish_program')
        submitted = publish_form if publishing else form
        if submitted.is_valid():
            action = 'published' if publishing else form.cleaned_data['action']
            try:
                change_publication(pk, user=request.user, version=submitted.cleaned_data['version'], action=action,
                                   notes='' if publishing else form.cleaned_data['notes'], address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                submitted.add_error(None, error)
            else:
                messages.success(request, 'Program published. Applications open according to its schedule.' if publishing else
                    'Program policy authorized. Current applications still require photo and eligibility review.'
                    if action == 'authorize_policy' else
                    'Program returned to draft. You can edit and publish it again. Applications and history are retained.' if action == 'unpublish' else
                    'Program archived. Applications and history are retained.' if action == 'archived' else
                    'Program status updated. Applications and history are retained.')
                return redirect('programs:manage_detail', pk=pk)
    live_edit = program.status not in ('published', 'cancelled') or request.user.has_perm('programs.publish_program')
    from .approval_policy import require_binding
    try:
        control = getattr(program, 'approval_control', None)
        if not control or not control.active_binding_id:
            raise ValidationError('Approval not recorded.')
        require_binding(program, first_publication=program.published_at is None)
        pdao_status = 'Approval recorded'
    except ValidationError:
        pdao_status = 'Approval or renewed review required'
    from .detail_workspace import detail_context
    ewaf_problem = publication_configuration_problem(program) if workflow_enabled() else ''
    return render(request, 'programs/manage_detail.html', {**detail_context(program, request.user,
        ewaf_problem=ewaf_problem, pdao_status=pdao_status), 'program': program, 'form': form, 'actions': actions,
        'publish_form': publish_form, 'can_publish': can_publish,
        'archive_action': archive_action, 'archive_label': archive_label, 'archiving': archiving,
        'pdao_status': pdao_status, 'pdao_enforcement_enabled': settings.PDAO_ENFORCEMENT_ENABLED,
        'ewaf_publication_problem': ewaf_problem,
        'requirements': program.configured_requirements.all(),
        'can_edit': live_edit and request.user.has_perm('programs.change_program'),
        'can_configure': live_edit and request.user.has_perm('programs.configure_program'),
        'history': page(request, program.history.filter(application__isnull=True)) if request.user.has_perm('programs.view_programlog') else None})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def requirement_edit(request, pk, requirement_id=None):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.configure_program')
    program = get_object_or_404(Program, pk=pk)
    if program.status in ('published', 'cancelled'):
        require_workspace_permissions(request.user, 'programs.publish_program')
    item = get_object_or_404(ProgramRequirement, pk=requirement_id, program=program) if requirement_id else ProgramRequirement(program=program)
    form = RequirementForm(request.POST if request.method == 'POST' else None, instance=item, initial={'version': program.version})
    if request.method == 'POST' and form.is_valid():
        try:
            save_requirement(pk, user=request.user, data=request.POST, requirement_id=requirement_id, address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Requirement saved. Existing applications retain their original requirements.')
            return redirect('programs:manage_detail', pk=pk)
    return render(request, 'programs/requirement_edit.html', {'program': program, 'form': form, 'editing': bool(requirement_id)})


@never_cache
@dashboard_required
@require_safe
def applications(request, pk):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.view_programapplication')
    program = get_object_or_404(Program, pk=pk)
    items = program.applications.select_related('member', 'assistance_case__eligibility', 'current_photo')
    query = request.GET.get('q', '').strip()[:200]
    status = request.GET.get('status', '')
    status = status if status in ProgramApplication.Status.values else ''
    if query:
        from core.reference_services import filter_reference
        items = filter_reference(items, 'program', query, Q(member__full_name__icontains=query) |
            Q(member__control_number__icontains=query) | Q(public_reference__icontains=query) | Q(reference__icontains=query))
    if status:
        items = items.filter(status=status)
    membership = request.GET.get('membership', '')
    if membership == 'active':
        items = items.filter(member__is_active=True, member__archived_at__isnull=True)
    elif membership == 'inactive':
        items = items.filter(member__is_active=False, member__archived_at__isnull=True)
    elif membership == 'archived':
        items = items.filter(member__archived_at__isnull=False)
    else:
        membership = ''
    ordering = {'newest': ('-submitted_at', '-pk'), 'oldest': ('submitted_at', 'pk'),
                'az': ('member__full_name', 'pk'), 'za': ('-member__full_name', 'pk')}
    sort = request.GET.get('sort', 'newest')
    sort = sort if sort in ordering else 'newest'
    from assistance.models import EligibilityStatus
    from assistance.services import VIEW_PERMISSIONS
    can_view_eligibility = request.user.has_perms(VIEW_PERMISSIONS)
    eligibility = request.GET.get('eligibility', '') if can_view_eligibility else ''
    if eligibility == 'unreviewed':
        items = items.filter(assistance_case__isnull=True)
    elif eligibility in EligibilityStatus.Code.values:
        items = items.filter(assistance_case__eligibility_id=eligibility)
    else:
        eligibility = ''
    applicant_page = page(request, items.order_by(*ordering[sort]))
    from .review_context import identity_status
    for item in applicant_page:
        item.identity_status = identity_status(item, request.user)
    return render(request, 'programs/applications.html', {'program': program, 'page_obj': applicant_page,
        'sort': sort, 'membership': membership,
        'can_view_eligibility': can_view_eligibility,
        'eligibility': eligibility, 'eligibility_statuses': EligibilityStatus.objects.all(),
        'query': query, 'status': status, 'statuses': ProgramApplication.Status.choices})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def application_detail(request, pk, reference):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.view_programapplication')
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member', 'current_photo'), pk=reference, program_id=pk)
    document_action = request.method == 'POST' and request.POST.get('action') == 'document_review'
    document_review, document_review_saved = None, False
    if document_action:
        require_workspace_permissions(request.user, 'members.view_member',
            'documents.view_membershipapplicationdocument', 'documents.verify_document')
        from uuid import UUID
        from documents.models import MembershipApplicationDocument
        from documents.forms import QuickReviewForm
        from documents.services import mark_document_reviewed
        try:
            document_id = UUID(request.POST.get('document_id', ''))
        except (ValueError, TypeError, AttributeError):
            raise Http404
        document = get_object_or_404(MembershipApplicationDocument, pk=document_id,
                                    application_id=application.member.application_id)
        review_form = QuickReviewForm(request.POST, prefix=f'document-{document.pk}')
        if review_form.is_valid():
            try:
                mark_document_reviewed(document.pk, user=request.user, **review_form.cleaned_data)
            except ValidationError as error:
                review_form.add_error(None, error)
            else:
                document_review_saved = True
                application.refresh_from_db()
                application.member.refresh_from_db()
        if not document_review_saved:
            document_review = (document.pk, review_form)
    from .review_context import applicant_context
    from .forms import PhotoReviewForm
    from .workflow import PHOTO_VIEW, review_photo
    from assistance.forms import EligibilityForm, DecisionForm
    from assistance.models import AssistanceCase
    from assistance.services import VIEW_PERMISSIONS
    from .review_services import (complete_eligibility_review, review_submitted_application,
                                 DIRECT_REVIEW_PERMISSIONS, decision_availability)
    from .review_forms import ApplicationDecisionForm
    direct_action = request.method == 'POST' and request.POST.get('action') == 'review_decision'
    can_decide_application = request.user.has_perms(DIRECT_REVIEW_PERMISSIONS)
    decision_form = ApplicationDecisionForm(request.POST if direct_action else None,
        application=application, auto_id='decision_%s') if can_decide_application else None
    from ewaf.evidence import VIEW as EVIDENCE_VIEW
    from ewaf.models import EvidencePolicyRevision, CriterionAssessment
    from .review_forms import QualificationForm, SimpleQualificationForm, SimpleEligibilityForm
    qualification_action = request.method == 'POST' and request.POST.get('action') == 'qualification'
    qualification_policy = EvidencePolicyRevision.objects.filter(program=application.program).first() if (
        application.program.ewaf_applicable and request.user.has_perms(EVIDENCE_VIEW)) else None
    can_qualify = bool(qualification_policy and qualification_policy.snapshot['criteria']['PR'].get('rubric_definition')
                       and request.user.has_perm('ewaf.review_criterionassessment'))
    qualification_class = (QualificationForm if qualification_action and not request.POST.get('qualification-simplified')
                           else SimpleQualificationForm)
    qualification_form = qualification_class(request.POST if qualification_action else None,
        application=application, policy=qualification_policy, prefix='qualification') if can_qualify else None
    eligibility_action = request.method == 'POST' and request.POST.get('action') == 'eligibility'
    return_action = request.method == 'POST' and request.POST.get('action') == 'return_review'
    return_form = DecisionForm(request.POST if return_action else None, prefix='return',
        initial={'version': application.version, 'decision': 'pending'})
    from django import forms as django_forms
    return_form.fields['decision'].widget = django_forms.HiddenInput()
    return_form.fields['decision'].choices = [('pending', 'Return for review')]
    case = AssistanceCase.objects.filter(application=application).first() if request.user.has_perms(VIEW_PERMISSIONS) else None
    eligibility_initial = {'version': application.version}
    if case:
        eligibility_initial['eligibility'] = case.eligibility_id
        for item in case.checklist:
            if item['key'] == 'other_requirements':
                eligibility_initial['other_requirements'] = item['result']
            elif item['key'].isdigit():
                eligibility_initial['check_' + item['key']] = item['result']
    eligibility_form = SimpleEligibilityForm(request.POST if eligibility_action else None,
        application=application, initial=eligibility_initial, auto_id='eligibility_%s')
    for field in eligibility_form.checklist_fields:
        field.field.widget.attrs['form'] = 'eligibility-decision-form'
    photo_action = request.method == 'POST' and request.POST.get('action') == 'photo'
    photo_form = PhotoReviewForm(request.POST if photo_action else None,
        initial={'version': application.version, 'photo_id': application.current_photo_id}, auto_id='photo_%s')
    form = ApplicationStatusForm(request.POST if request.method == 'POST' and request.POST.get('action', '') not in ('photo', 'eligibility', 'qualification', 'return_review', 'document_review', 'review_decision') else None,
                                 initial={'version': application.version, 'status': application.status}, auto_id='application_%s')
    if direct_action:
        require_workspace_permissions(request.user, *DIRECT_REVIEW_PERMISSIONS)
        if decision_form.is_valid():
            try:
                review_submitted_application(reference, user=request.user, data=request.POST,
                                             address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                decision_form.add_error(None, error)
            else:
                label = dict(decision_form.fields['eligibility'].choices)[decision_form.cleaned_data['eligibility']]
                messages.success(request, f'Application marked {label}. The review has been recorded.')
                return redirect('programs:application_detail', pk=pk, reference=reference)
    elif document_action:
        pass  # Render the current applicant and refreshed evidence on this same page.
    elif return_action:
        require_workspace_permissions(request.user, *VIEW_PERMISSIONS, 'assistance.decide_assistance')
        if return_form.is_valid():
            from assistance.services import decide_assistance
            try:
                decide_assistance(reference, user=request.user, data=return_form.cleaned_data,
                    address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                return_form.add_error(None, error)
            else:
                messages.success(request, 'Returned for review. Earlier reviews and decisions are retained.')
                return redirect('programs:application_detail', pk=pk, reference=reference)
    elif qualification_action:
        require_workspace_permissions(request.user, *EVIDENCE_VIEW, 'ewaf.review_criterionassessment')
        if not qualification_form:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest('Program qualification definitions are required.')
        if qualification_form.is_valid():
            from ewaf.evidence_services import record_assessment
            try:
                values = qualification_form.cleaned_data
                record_assessment(reference, user=request.user, criterion='PR', state='VERIFIED',
                    source_type='program_relevance', value=values['value'], policy_id=values['policy_id'],
                    expected_context=values['expected_context'], expected_revision=values['expected_revision'],
                    reason=values['reason'], confirmed=values['confirmed'], rubric_attested=values['confirmed'],
                    rubric_findings=qualification_form.findings())
            except ValidationError as error:
                qualification_form.add_error(None, error)
            else:
                messages.success(request, 'Program qualification verified. It is not a numerical EWAF criterion.')
                return redirect('programs:application_detail', pk=pk, reference=reference)
    elif eligibility_action:
        require_workspace_permissions(request.user, *VIEW_PERMISSIONS, 'assistance.review_eligibility')
        if eligibility_form.is_valid():
            try:
                complete_eligibility_review(reference, user=request.user, data=request.POST, address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                eligibility_form.add_error(None, error)
            else:
                messages.success(request, 'Eligibility saved. The program applicant list has been updated.')
                return redirect('programs:application_detail', pk=pk, reference=reference)
    elif photo_action:
        require_workspace_permissions(request.user, *PHOTO_VIEW, 'programs.review_applicationphoto')
        if photo_form.is_valid():
            try:
                review_photo(reference, user=request.user, data=request.POST, address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                photo_form.add_error(None, error)
            else:
                messages.success(request, 'Photo verification saved with retained review history.')
                return redirect('programs:application_detail', pk=pk, reference=reference)
    elif request.method == 'POST':
        require_workspace_permissions(request.user, 'programs.change_programapplication')
        if form.is_valid():
            try:
                change_application(reference, user=request.user, address=request.META.get('REMOTE_ADDR'), **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Application status updated with retained history.')
                return redirect('programs:application_detail', pk=pk, reference=reference)
    # A form opened before the combined review still receives useful validation
    # errors, without bringing back its separate review controls.
    legacy_review_forms = [eligibility_form, photo_form, qualification_form]
    if document_review:
        legacy_review_forms.append(document_review[1])
    legacy_review_errors = [str(error) for review in legacy_review_forms if review and review.is_bound
                            for errors in review.errors.values() for error in errors]
    from .decision_email import notification_context
    decision_available, decision_unavailable_reason = decision_availability(application) if can_decide_application else (False, '')
    return render(request, 'programs/application_detail.html', {'program': application.program, 'application': application,
        **notification_context(application, request.user),
        'form': form, 'photo_form': photo_form, **applicant_context(application, request.user,
            document_review=document_review, include_member_information=False),
        'document_review_saved': document_review_saved,
        'eligibility_form': eligibility_form, 'case': case,
        'decision_form': decision_form,
        'legacy_review_errors': legacy_review_errors,
        'can_decide_application': can_decide_application,
        'decision_available': decision_available, 'decision_unavailable_reason': decision_unavailable_reason,
        'completed_reassessment': decision_available and application.status == 'COMPLETED',
        'return_form': return_form,
        'can_return_review': request.user.has_perms((*VIEW_PERMISSIONS, 'assistance.decide_assistance')),
        'qualification_form': qualification_form, 'qualification_policy': qualification_policy,
        'can_review_eligibility': request.user.has_perms((*VIEW_PERMISSIONS, 'assistance.review_eligibility')),
        'eligibility_history': application.assistance_history.filter(action='eligibility_reviewed')
            if request.user.has_perm('assistance.view_assistancelog') else [],
        'photo_reviews': application.current_photo.reviews.all() if application.current_photo_id and request.user.has_perms(PHOTO_VIEW) else [],
        'history': page(request, application.history.all()) if request.user.has_perm('programs.view_programlog') else None})


@never_cache
@dashboard_required
@require_safe
@private_access_writer('document_downloaded')
def download_document(request, pk, reference, document_id, revision_id=None):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.view_programapplication', 'programs.view_programdocument')
    document = get_object_or_404(ProgramDocument.objects.select_related('application__program'), pk=document_id,
                                application_id=reference, application__program_id=pk)
    application = document.application
    if revision_id is not None:
        require_workspace_permissions(request.user, 'programs.view_programdocumentrevision')
        document = get_object_or_404(document.revisions, pk=revision_id)
    try:
        handle = document.file.open('rb')
    except FileNotFoundError:
        raise Http404('This document is unavailable.')
    try:
        record_log(application.program, 'document_downloaded', f'Private program document downloaded: {document_id}; revision: {revision_id or "current"}.',
                   user=request.user, application=application, address=request.META.get('REMOTE_ADDR'))
    except Exception:
        handle.close()
        raise
    response = FileResponse(handle, as_attachment=request.GET.get('preview') != '1', filename=f'document-{document.pk}{Path(document.file.name).suffix}',
                            content_type=document.content_type)
    response['Cache-Control'] = 'no-store, private'
    response['Referrer-Policy'] = 'no-referrer'
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['X-Content-Type-Options'] = 'nosniff'
    return response
