from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from .models import ScoringPolicyRevision, CalculationDiagnosticRun
from .evidence import digest
from .evidence_forms import ConfirmedForm
from .scoring_forms import ScoringPolicyForm
from .scoring_inputs import VIEW, READINESS_VIEW, policy_context, applicant_readiness
from .scoring_policy import BARRIERS, proposal_reasons
from .scoring_services import record_scoring_policy, record_applicant_diagnostic, validate_run


@never_cache
@dashboard_required
@require_safe
def scoring_list(request):
    require_workspace_permissions(request.user, *VIEW)
    from accounts.authority_services import enlisted
    from .durable_services import PERMISSION
    return render(request, 'ewaf/scoring_list.html', {'page': Paginator(Program.objects.order_by('name', 'pk'), 20).get_page(request.GET.get('page')),
        'development_available': enlisted() and request.user.has_perm(PERMISSION)})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def scoring_policy(request, pk):
    require_workspace_permissions(request.user, *VIEW)
    can_record = request.user.has_perm('ewaf.record_scoringpolicyrevision')
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'ewaf.record_scoringpolicyrevision')
    program = get_object_or_404(Program, pk=pk)
    context = policy_context(program)
    current = ScoringPolicyRevision.objects.filter(program=program).first()
    config = context['configuration']
    validation = config['histories'].get('validations')
    form = ScoringPolicyForm(request.POST if request.method == 'POST' else None, initial={
        'expected_context': digest(context), 'configuration_id': config['configuration'],
        'validation_id': validation['id'] if validation else None, 'evidence_policy_id': config['source']['policy']})
    if request.method == 'POST' and form.is_valid():
        try:
            record_scoring_policy(pk, user=request.user, **form.cleaned_data)
            return redirect('ewaf:scoring_policy', pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    can_inspect = request.user.has_perms(READINESS_VIEW)
    return render(request, 'ewaf/scoring_policy.html', {'program': program, 'current': current,
        'page': Paginator(ScoringPolicyRevision.objects.filter(program=program), 10).get_page(request.GET.get('page')),
        'applications': Paginator(ProgramApplication.objects.filter(program=program).order_by('pk'), 20).get_page(request.GET.get('applications')) if can_inspect else None,
        'can_record': can_record, 'form': form, 'barriers': BARRIERS,
        'pending': proposal_reasons(current.proposal) if current else [{'code': 'SCORING_POLICY_MISSING'}]})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def scoring_diagnostics(request, reference):
    require_workspace_permissions(request.user, *READINESS_VIEW)
    application = get_object_or_404(ProgramApplication, pk=reference)
    result = applicant_readiness(reference, user=request.user)
    can_record = request.user.has_perm('ewaf.record_calculationdiagnosticrun')
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'ewaf.record_calculationdiagnosticrun')
    form = ConfirmedForm(request.POST if request.method == 'POST' else None, initial={'expected_context': result['context_digest']})
    if request.method == 'POST' and form.is_valid():
        try:
            record_applicant_diagnostic(reference, user=request.user, program_id=application.program_id, **form.cleaned_data)
            return redirect('ewaf:scoring_history', reference=reference)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, 'ewaf/scoring_diagnostics.html', {'application': application, 'result': result,
        'can_record': can_record, 'form': form})


@never_cache
@dashboard_required
@require_safe
def scoring_history(request, reference):
    require_workspace_permissions(request.user, *READINESS_VIEW)
    application = get_object_or_404(ProgramApplication, pk=reference)
    current = applicant_readiness(reference, user=request.user)
    page = Paginator(CalculationDiagnosticRun.objects.filter(items__application=application, program=application.program), 10).get_page(request.GET.get('page'))
    entries = []
    for run in page:
        valid = True
        try:
            validate_run(run)
        except ValidationError:
            valid = False
        entries.append({'run': run, 'valid': valid, 'outdated': run.context_digest != current['context_digest']})
    return render(request, 'ewaf/scoring_history.html', {'application': application, 'entries': entries, 'page': page})
