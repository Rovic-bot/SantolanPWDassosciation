from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from .evidence import VIEW, ALL_CRITERIA, approval_context, source_context, digest
from .models import EvidencePolicyRevision, CriterionAssessment
from .evidence_forms import AssessmentForm, PolicyForm, ReadinessForm
from .evidence_services import record_policy, record_assessment, record_readiness
from .readiness import assess_readiness


@never_cache
@dashboard_required
@require_safe
def evidence_queue(request):
    require_workspace_permissions(request.user, *VIEW)
    page = Paginator(ProgramApplication.objects.select_related('program').order_by('-submitted_at'), 20).get_page(request.GET.get('page'))
    return render(request, 'ewaf/evidence_queue.html', {'page': page})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def evidence_policy(request, pk):
    require_workspace_permissions(request.user, *VIEW, 'ewaf.record_evidencepolicyrevision')
    program = get_object_or_404(Program, pk=pk)
    latest = EvidencePolicyRevision.objects.filter(program=program).first()
    form = PolicyForm(request.POST if request.method == 'POST' else None, initial={
        'expected_revision': latest.revision if latest else 0,
        'expected_context': digest({'program_version': program.version, 'approval': approval_context(program)})})
    if request.method == 'POST' and form.is_valid():
        try:
            record_policy(program.pk, user=request.user, **form.cleaned_data)
            return redirect('ewaf:evidence_policy', pk=program.pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, 'ewaf/evidence_policy.html', {'program': program, 'form': form,
        'page': Paginator(EvidencePolicyRevision.objects.filter(program=program), 10).get_page(request.GET.get('page'))})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def evidence_review(request, reference, criterion):
    require_workspace_permissions(request.user, *VIEW)
    if not request.user.has_perm('ewaf.declare_criterionassessment'):
        require_workspace_permissions(request.user, 'ewaf.review_criterionassessment')
    if criterion not in ALL_CRITERIA:
        from django.http import Http404
        raise Http404
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member__application'), pk=reference)
    if criterion == 'PR' and request.method == 'GET':
        from django.urls import reverse
        return redirect(reverse('programs:application_detail',
            kwargs={'pk': application.program_id, 'reference': reference}) + '#qualification')
    policy = EvidencePolicyRevision.objects.filter(program=application.program).first()
    latest = CriterionAssessment.objects.filter(application=application, criterion=criterion).first()
    context = source_context(application)
    form = AssessmentForm(request.POST if request.method == 'POST' else None, criterion=criterion, user=request.user,
        initial={'policy_id': policy.pk if policy else None, 'expected_revision': latest.revision if latest else 0,
                 'expected_context': digest(context)})
    if policy and 'HI' in policy.snapshot['criteria'] and criterion != 'PR':
        from .household_criteria import SOURCES
        from .evidence import reviewed_value
        source = SOURCES.get(criterion)
        rule = policy.snapshot['criteria'].get(criterion)
        if source and rule:
            form.fields['source_type'].choices = [(source, source.replace('_', ' ').capitalize())]
            form.initial['source_type'] = source
            if criterion != 'PA':
                try:
                    form.initial['value'] = reviewed_value(application, criterion, source, None, rule)[0]
                except ValidationError as error:
                    form.fields['value'].help_text = '; '.join(error.messages)
                form.fields['value'].disabled = True
    if request.method == 'POST' and form.is_valid():
        try:
            record_assessment(reference, user=request.user, criterion=criterion, **form.cleaned_data)
            return redirect('programs:application_detail', pk=application.program_id, reference=reference)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, 'ewaf/evidence_review.html', {'application': application, 'criterion': criterion,
        'form': form, 'policy': policy, 'latest': latest, 'documents': context['supporting_documents'],
        'criterion_rule': policy.snapshot['criteria'].get(criterion) if policy else None})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def evidence_readiness(request, reference):
    require_workspace_permissions(request.user, *VIEW)
    application = get_object_or_404(ProgramApplication.objects.select_related('program'), pk=reference)
    result = assess_readiness(reference, user=request.user)
    form = ReadinessForm(request.POST if request.method == 'POST' else None, initial={
        'expected_context': result['context_digest'],
        'expected_assessments': {row['criterion']: row['assessment'] for row in result['criteria']}})
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'ewaf.record_eligibilityreadinesssnapshot')
        if form.is_valid():
            try:
                record_readiness(reference, user=request.user, **form.cleaned_data)
                return redirect('ewaf:evidence_history', reference=reference)
            except ValidationError as error:
                form.add_error(None, error)
    return render(request, 'ewaf/readiness.html', {'application': application, 'result': result, 'form': form})


@never_cache
@dashboard_required
@require_safe
def evidence_history(request, reference):
    require_workspace_permissions(request.user, *VIEW)
    application = get_object_or_404(ProgramApplication, pk=reference)
    return render(request, 'ewaf/evidence_history.html', {'application': application,
        'page': Paginator(application.criterion_assessments.order_by('-recorded_at', '-pk'), 20).get_page(request.GET.get('page')),
        'snapshots': Paginator(application.readiness_snapshots.all(), 10).get_page(request.GET.get('snapshots'))})
