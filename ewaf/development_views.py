"""Private fictional development interface; absent outside registered sessions."""
import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.decorators import dashboard_required
from . import generation_processing as processing, durable_services as durable
from .four_criterion_development import ahp, PAIRS, SCALE, fictional_demonstration, policy_readiness
from .four_criterion_reference import REFERENCE_PAIRS


def _actor(request):
    from accounts.authority_services import enlisted
    if not enlisted():
        raise Http404
    return durable._authorize(request.user)


class ComparisonForm(forms.Form):
    pending = forms.BooleanField(required=False, label='Keep fictional DEMO-C awaiting review',
        help_text='An unresolved applicant remains in the inventory and blocks this complete-pool example.')
    selected = forms.ChoiceField(required=False, label='Human selection demonstration',
        choices=[('', 'No selection'), ('DEMO-A', 'Fictional DEMO-A'), ('DEMO-B', 'Fictional DEMO-B')],
        help_text='Illustrates a separate human choice. It records no beneficiary decision or actual receipt.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reference = {f'{a}:{b}': value for a, b, value in REFERENCE_PAIRS}
        for pair in PAIRS:
            a, b = pair.split(':')
            self.fields['pair_' + pair.replace(':', '_')] = forms.ChoiceField(
                label=f'{a} compared with {b}', choices=[(value, value) for value in SCALE], initial=reference[pair],
                help_text=f'1 means equal importance; above 1 favors {a}; below 1 favors {b}. '
                          'This expresses relative importance, not the direction of applicant need.')
        self.order_fields(['pair_' + pair.replace(':', '_') for pair in PAIRS] + ['pending', 'selected'])
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-select'

    def judgments(self):
        return {pair: self.cleaned_data['pair_' + pair.replace(':', '_')] for pair in PAIRS}


class CalculationForm(forms.Form):
    expected = forms.JSONField(widget=forms.HiddenInput)
    expected_context = forms.CharField(max_length=64, widget=forms.HiddenInput)
    request_key = forms.CharField(max_length=64, widget=forms.HiddenInput)
    previous_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, label='Development recalculation reason',
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def laboratory(request):
    actor = _actor(request)
    from .durable_models import DurableRequest
    form = ComparisonForm(request.POST if request.method == 'POST' else None)
    demo = fictional_demonstration() if request.method == 'GET' else None
    if request.method == 'POST' and form.is_valid():
        try:
            demo = fictional_demonstration(judgments=form.judgments(), pending=form.cleaned_data['pending'],
                                          selected=form.cleaned_data['selected'])
        except ValidationError as error:
            form.add_error(None, error)
    programs = list(DurableRequest.objects.filter(actor=actor).order_by('program__name').values(
        'program_id', 'program__name').distinct())
    return render(request, 'ewaf/development.html', {'form': form, 'demo': demo,
        'readiness': policy_readiness(), 'programs': programs})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def development_program(request, pk):
    actor = _actor(request)
    from programs.models import Program
    from .durable_models import DurableRequest, DurableRun
    from .generation_models import RunSourceBinding
    program = get_object_or_404(Program, pk=pk)
    prior_request = DurableRequest.objects.filter(program=program, actor=actor).order_by('-pk').first()
    if not prior_request:
        raise Http404('A harness-created fictional evaluation contract is required.')
    latest = RunSourceBinding.objects.filter(run__program=program, run__actor=actor).order_by('-run_id').first()
    current, blockers, context = None, [], None
    try:
        current = processing.inspect_current(pk, user=actor)
    except ValidationError as error:
        blockers.extend(error.messages)
    try:
        context = processing.inspect_context(pk, user=actor, contract=prior_request.contract)
    except ValidationError as error:
        blockers.extend(error.messages)
    form = CalculationForm(request.POST if request.method == 'POST' else None, initial={
        'expected': context['expected'] if context else {},
        'expected_context': context['context_digest'] if context else '',
        'request_key': str(uuid.uuid4()), 'previous_id': latest.run_id if latest else None})
    if request.method == 'POST' and form.is_valid():
        try:
            accepted = processing.accept_request(pk, user=actor, contract=prior_request.contract, **form.cleaned_data)
            processing.process_request(accepted.pk, program_id=pk, user=actor)
            return redirect('ewaf:development_program', pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
            # Acceptance may already have invalidated the predecessor before a
            # later processing failure. Never reuse the pre-POST current claim.
            current = None
    history = []
    from django.core.paginator import Paginator
    page = Paginator(DurableRun.objects.filter(program=program, actor=actor).order_by('-pk'), 10).get_page(request.GET.get('page'))
    for run in page:
        valid = True
        try:
            durable.inspect_development_history(run.pk, program_id=pk, user=actor)
        except ValidationError:
            valid = False
        results = list(run.results.prefetch_related('traces').order_by('application_id')) if valid else []
        from .four_policy import POOL_ENGINE
        is_four = run.snapshot.get('engine') == POOL_ENGINE
        if valid and is_four:
            from .four_review import ordered_results
            results = ordered_results(results)
        history.append({'run': run, 'valid': valid, 'current': bool(current and current['run_id'] == run.pk),
            'four_criterion': is_four, 'results': results})
    from .four_policy import PROFILE
    return render(request, 'ewaf/development_program.html', {'program': program, 'form': form,
        'four_criterion': prior_request.contract.get('profile') == PROFILE,
        'context': context, 'current': current, 'blockers': sorted(set(blockers)), 'history': history, 'page': page})
