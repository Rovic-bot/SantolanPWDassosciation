from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from programs.review_context import applicant_context
from .forms import EligibilityForm, DecisionForm, ReceiptForm, VoidForm, StatusForm
from .models import AssistanceCase, AssistanceRelease, EligibilityStatus, AssistanceLog
from .services import VIEW_PERMISSIONS, decide_assistance, record_actual_receipt, void_release


@never_cache
@dashboard_required
@require_safe
def queue(request):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS)
    program_id = request.GET.get('program')
    if request.GET.get('eligibility') != 'eligible' and request.GET.get('decision') != 'approved':
        if program_id:
            try:
                program = get_object_or_404(Program, pk=program_id)
            except ValidationError:
                from django.http import Http404
                raise Http404
            from django.urls import reverse
            filters = request.GET.copy()
            filters.pop('program', None)
            return redirect(reverse('programs:applications', kwargs={'pk': program.pk}) + '?' + filters.urlencode())
        return redirect('core:application_programs')
    if not program_id:
        query = request.GET.get('q', '').strip()[:200]
        programs = Program.objects.all().order_by('-created_at', 'pk')
        selection = request.GET.get('eligibility') == 'eligible'
        if selection:
            programs = programs.filter(ewaf_applicable=False)
        if query:
            programs = programs.filter(name__icontains=query)
        return render(request, 'admin_portal/application_programs.html', {
            'page_obj': Paginator(programs, 20).get_page(request.GET.get('page')),
            'query': query, 'heading': 'Non-EWAF selection' if selection else 'Eligibility review',
            'destination': 'eligibility', 'selection': selection})
    try:
        program = get_object_or_404(Program, pk=program_id)
    except ValidationError:
        from django.http import Http404
        raise Http404
    items = ProgramApplication.objects.select_related('member', 'program', 'assistance_case__eligibility').order_by('-submitted_at', '-pk')
    items = items.filter(program=program).annotate(has_release=Exists(
        AssistanceRelease.objects.successful().filter(application_id=OuterRef('pk'))))
    query = request.GET.get('q', '').strip()[:200]
    status = request.GET.get('eligibility', '')
    decision = request.GET.get('decision', '')
    if query:
        items = items.filter(Q(member__full_name__icontains=query) | Q(member__control_number__icontains=query) | Q(program__name__icontains=query))
    if status == 'unreviewed':
        items = items.filter(assistance_case__isnull=True)
    elif status in EligibilityStatus.Code.values:
        items = items.filter(assistance_case__eligibility_id=status)
    else:
        status = ''
    if decision in AssistanceCase.Decision.values:
        items = items.filter(assistance_case__decision=decision)
    else:
        decision = ''
    return render(request, 'assistance/queue.html', {'page_obj': Paginator(items, 20).get_page(request.GET.get('page')),
        'program': program, 'query': query, 'status': status, 'decision': decision, 'statuses': EligibilityStatus.objects.all(), 'decisions': AssistanceCase.Decision.choices})


@never_cache
@dashboard_required
@require_safe
def detail(request, reference):
    """Retired duplicate profile: keep old bookmarks pointing to an existing record."""
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS)
    application = get_object_or_404(ProgramApplication, pk=reference)
    if request.user.has_perm('members.view_member'):
        return redirect('members:detail', pk=application.member_id)
    return redirect('programs:application_detail', pk=application.program_id, reference=application.pk)


from programs.review_services import complete_eligibility_review

ACTIONS = {
    'review': ('assistance.review_eligibility', 'Assess eligibility', EligibilityForm, complete_eligibility_review),
    'decision': ('assistance.decide_assistance', 'Record administrative decision', DecisionForm, decide_assistance),
}


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def action(request, reference, action):
    permission, title, form_class, service = ACTIONS[action]
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS, permission)
    application = get_object_or_404(ProgramApplication.objects.select_related('member', 'program'), pk=reference)
    if action == 'review' and request.method in ('GET', 'HEAD'):
        return redirect(reverse('programs:application_detail',
            kwargs={'pk': application.program_id, 'reference': reference}) + '#eligibility')
    if action == 'decision' and application.program.ewaf_applicable:
        from ewaf.operational_services import available, actor
        from ewaf.operational_models import OperationalRun
        actor(request.user, 'ewaf.decide_operational')
        latest = OperationalRun.objects.filter(program=application.program).first() if available() else None
        if latest:
            return redirect('ewaf:operational_run', pk=application.program_id, run_id=latest.pk)
        return redirect('ewaf:operational_workspace', pk=application.program_id)
    if action == 'review':
        from programs.views import application_detail
        request.POST = request.POST.copy()
        request.POST['action'] = 'eligibility'
        return application_detail(request, application.program_id, reference)
    return_url = reverse('assistance:queue') + f'?program={application.program_id}&eligibility=eligible'
    initial = {'version': application.version}
    options = {}
    if action == 'review':
        options['application'] = application
        case = AssistanceCase.objects.filter(application=application).first()
        if case:
            initial['eligibility'] = case.eligibility_id
            for item in case.checklist:
                if item['key'] == 'other_requirements':
                    initial['other_requirements'] = item['result']
                elif item['key'].isdigit():
                    initial[f'check_{item["key"]}'] = item['result']
    form = form_class(request.POST if request.method == 'POST' else None, initial=initial, **options)
    if request.method == 'POST' and form.is_valid():
        try:
            service(reference, user=request.user, data=request.POST, address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Saved with retained history.')
            if action == 'review':
                return redirect('programs:application_detail', pk=application.program_id, reference=reference)
            return redirect(return_url)
    return render(request, 'assistance/action.html', {'application': application, 'form': form, 'title': title, 'action': action,
        'return_url': return_url, 'return_label': 'Beneficiary decisions',
        **applicant_context(application, request.user)})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def release(request, reference):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS, 'assistance.view_assistancerelease',
                                  'assistance.record_release')
    application = get_object_or_404(ProgramApplication.objects.select_related('member', 'program'), pk=reference)
    return_url = reverse('assistance:program_releases', args=[application.program_id])
    from .receipt_readiness import receipt_blocker
    blocker = receipt_blocker(application)
    form = ReceiptForm(request.POST if request.method == 'POST' else None,
        initial={'version': application.version, 'program_version': application.program.version})
    if request.method == 'POST' and not blocker and form.is_valid():
        try:
            record_actual_receipt(reference, user=request.user, data=request.POST,
                                  address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
            blocker = receipt_blocker(application)
        else:
            messages.success(request, f'Actual receipt recorded for {application.member.full_name} — {application.program.name}.')
            return redirect(return_url + f'#receipt-{application.pk}')
    return render(request, 'assistance/claimant_receipt.html', {
        'application': application, 'program': application.program, 'form': form,
        'release_blocker': blocker,
        'return_url': return_url, 'representative_fields': [form[name] for name in form.representative_fields]})


@never_cache
@dashboard_required
@require_safe
def release_programs(request):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS, 'assistance.view_assistancerelease')
    from .release_portfolio import workspace
    return render(request, 'assistance/release_programs.html', workspace(request))


@never_cache
@dashboard_required
@require_safe
def program_releases(request, pk):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS, 'assistance.view_assistancerelease')
    program = get_object_or_404(Program, pk=pk)
    rows = program.applications.select_related('member', 'assistance_case').prefetch_related(
        'assistance_releases').order_by('member__full_name', 'pk')
    current_run = None
    decisions = {}
    if program.ewaf_applicable:
        from ewaf.operational_services import available, latest_decisions, delivery_decision_problem
        from ewaf.operational_models import OperationalRun
        if available():
            current_run = OperationalRun.objects.filter(program=program).first()
            decisions = {item.application_id: item for item in latest_decisions(program)}
    releases = {item.application_id: item for item in AssistanceRelease.objects.successful().filter(application__program=program)}
    from announcements.release_publication import published_selection
    published_references, _ = published_selection(program)
    from .receipt_email import notification_context
    for item in rows:
        item.ewaf_decision = decisions.get(item.pk)
        item.receipt = releases.get(item.pk)
        item.receipt_email = notification_context(item.receipt, request.user)
        item.release_published = item.public_reference in published_references
        item.release_selection_problem = delivery_decision_problem(current_run, item.ewaf_decision) if program.ewaf_applicable else ''
        item.release_selection_stale = bool(program.ewaf_applicable and item.ewaf_decision and current_run
            and item.ewaf_decision.run_id != current_run.pk)
        item.release_approved = not item.release_selection_problem if program.ewaf_applicable else (
            getattr(item, 'assistance_case', None) and item.assistance_case.decision == 'approved')
        score = current_run.calculations.get(str(item.pk)) if current_run else None
        item.ewaf_score = score['score_0_100'] if score else None
        item.ewaf_rank = score['comparison']['higher'] + 1 if score else None
    rows = sorted(rows, key=lambda row: (row.ewaf_rank is None, row.ewaf_rank or 0, row.member.full_name))
    return render(request, 'assistance/program_releases.html', {
        'program': program, 'run': current_run, 'page_obj': Paginator(rows, 50).get_page(request.GET.get('page'))})


@never_cache
@dashboard_required
@require_http_methods(['POST'])
def retry_receipt_email(request, reference, release_id):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS,
        'assistance.view_assistancerelease', 'assistance.record_release')
    release = get_object_or_404(AssistanceRelease.objects.select_related('application'),
                               pk=release_id, application_id=reference)
    from .receipt_email import retry_receipt_email as retry
    try:
        retry(release.pk, application_id=reference, user=request.user,
              confirmed=request.POST.get('confirm') == '1')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    return redirect(reverse('assistance:program_releases', args=[release.application.program_id])
                    + f'#receipt-{reference}')


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def void(request, reference, release_id):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS, 'assistance.view_assistancerelease', 'assistance.void_release')
    application = get_object_or_404(ProgramApplication.objects.select_related('member', 'program'), pk=reference)
    release = get_object_or_404(AssistanceRelease, pk=release_id, application=application)
    form = VoidForm(request.POST if request.method == 'POST' else None, initial={'version': application.version})
    if request.method == 'POST' and form.is_valid():
        try:
            void_release(reference, release_id, user=request.user, data=request.POST, address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Release voided and retained. A replacement needs renewed assessment and approval.')
            return redirect('assistance:program_releases', pk=application.program_id)
    return render(request, 'assistance/action.html', {'application': application, 'release': release, 'form': form, 'title': 'Void incorrect release', 'action': 'void',
        'return_url': reverse('assistance:program_releases', args=[application.program_id]), 'return_label': 'Assistance releases'})


@never_cache
@dashboard_required
@require_http_methods(['POST'])
def undo_receipt(request, reference, release_id):
    require_workspace_permissions(request.user, *VIEW_PERMISSIONS,
        'assistance.view_assistancerelease', 'assistance.void_release')
    application = get_object_or_404(ProgramApplication, pk=reference)
    get_object_or_404(AssistanceRelease, pk=release_id, application=application)
    try:
        void_release(reference, release_id, user=request.user, data={
            'version': request.POST.get('version'),
            'confirm': request.POST.get('confirm') == '1',
            'notes': 'Receipt recorded in error; undone by staff.',
        }, address=request.META.get('REMOTE_ADDR'))
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Receipt undone. Review and approval are required before recording a replacement.')
    return redirect(reverse('assistance:program_releases', args=[application.program_id])
                    + f'#receipt-{reference}')


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def statuses(request, code=None):
    require_workspace_permissions(request.user, 'assistance.view_eligibilitystatus')
    if request.method == 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    return render(request, 'assistance/statuses.html', {'statuses': EligibilityStatus.objects.all(),
        'history': Paginator(AssistanceLog.objects.filter(application__isnull=True), 20).get_page(request.GET.get('page')) if request.user.has_perm('assistance.view_assistancelog') else None})
