"""Private, disposable-only four-criterion guided workflow within the Admin shell."""
from uuid import UUID
from django import forms
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from .development_views import _actor, ComparisonForm
from .four_criterion_development import policy_readiness
from . import generation_processing as processing, generation_services as generation
from . import four_policy as four, four_services, four_decisions
from .configuration_services import configuration_context
from .models import ScoringPolicyRevision, CriterionAssessment
from .evidence import digest, source_context
from .readiness import evaluate


class FourConfigurationForm(ComparisonForm):
    expected = forms.JSONField(widget=forms.HiddenInput)
    expected_context = forms.CharField(max_length=64, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, label='Fictional configuration change reason',
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['pending']
        del self.fields['selected']
        self.fields['reason'].widget.attrs['class'] = 'form-control'


class HumanChoiceForm(forms.Form):
    expected = forms.JSONField(widget=forms.HiddenInput)
    expected_decisions = forms.JSONField(required=False, widget=forms.HiddenInput)
    run_id = forms.IntegerField(widget=forms.HiddenInput)
    application_id = forms.TypedChoiceField(coerce=UUID, label='Confirmed eligible fictional application')
    decision = forms.ChoiceField(label='Human demonstration decision', choices=[
        ('DEFER_FOR_REVIEW', 'Defer for human review'), ('SELECT_FOR_DEMONSTRATION', 'Select in this demonstration only'),
        ('WITHDRAW_DEMO', 'Withdraw a fictional choice')])
    reason = forms.CharField(max_length=1000, label='Human decision reason',
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))

    def __init__(self, *args, choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['application_id'].choices = choices
        for name in ('application_id', 'decision'):
            self.fields[name].widget.attrs['class'] = 'form-select'


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def workspace(request, pk):
    actor = _actor(request)
    with processing._fence(pk, actor) as (actor, authority, program, state, applications):
        policy = ScoringPolicyRevision.objects.filter(program=program).first()
        if not policy or policy.profile != four.PROFILE:
            raise Http404('A harness-created four-criterion test policy is required.')
        policy.clean()
        expected = generation._token(state, authority)
        inventory = []
        for application in applications:
            readiness = evaluate(application, context=source_context(application))
            relevance_ready = False
            from .four_pool import eligibility
            assessment = CriterionAssessment.objects.filter(application=application, criterion='PR').first()
            if assessment and readiness['criterion_completeness']:
                try:
                    assessment.clean()
                    eligibility(assessment, policy.proposal['eligibility'])
                    relevance_ready = True
                except ValidationError:
                    pass
            inventory.append({'id': application.pk, 'status': application.status,
                'membership_and_eligibility': readiness['eligibility_readiness'],
                'verified_evidence': readiness['criterion_completeness'], 'program_relevance': relevance_ready,
                'reasons': readiness['reasons']})
        config_context = digest(configuration_context(program))
        configuration = policy.configuration
        mathematical = policy.validation.result
    current, result_choices, findings = None, [], []
    try:
        current = processing.inspect_current(pk, user=actor)
        from .durable_models import DurableRun
        run = DurableRun.objects.get(pk=current['run_id'], actor=actor)
        if run.snapshot['engine'] == four.POOL_ENGINE:
            result_choices = [(row.application_id, 'Fictional application ' + str(row.application_id)) for row in run.results.all()]
    except ValidationError as error:
        findings = error.messages
    # The submitted token, never a fresh substitute, is used by either mutation.
    from .decision_models import DevelopmentHumanDecision
    from . import decision_services
    decision_versions = {str(key): {'revision': 0, 'previous': None} for key, label in result_choices}
    from django.db.models import OuterRef, Subquery
    latest = DevelopmentHumanDecision.objects.filter(program=program,
        application_id=OuterRef('application_id')).order_by('-revision').values('pk')[:1]
    for row in DevelopmentHumanDecision.objects.filter(program=program, application_id__in=decision_versions,
            pk=Subquery(latest)):
        decision_versions[str(row.application_id)] = {'revision': row.revision, 'previous': row.pk}
    can_decide = actor.has_perm('assistance.decide_assistance')
    try:
        decision_page = max(1, min(int(request.GET.get('decision_page', 1)), 9223372036854775807))
    except (ValueError, TypeError):
        decision_page = 1
    decision_history = decision_services.inspect_history(pk, user=actor, page=decision_page) if can_decide else None
    action = request.POST.get('action') if request.method == 'POST' else None
    configuration_form = FourConfigurationForm(request.POST if action == 'configuration' else None,
        auto_id='config_%s',
        initial={'expected': expected, 'expected_context': config_context,
            **{'pair_' + pair.replace(':', '_'): value for pair, value in configuration.judgments.items()}})
    choice_form = HumanChoiceForm(request.POST if action in ('choice', 'record') else None, choices=result_choices,
        auto_id='choice_%s',
        initial={'expected': expected, 'run_id': current['run_id'] if current else None,
                 'expected_decisions': decision_versions})
    choice = None
    if action == 'configuration' and configuration_form.is_valid():
        try:
            four_services.record_configuration(pk, user=actor, expected={str(pk): configuration_form.cleaned_data['expected']},
                expected_context=configuration_form.cleaned_data['expected_context'],
                judgments=configuration_form.judgments(), proposed=policy.proposal,
                reason=configuration_form.cleaned_data['reason'])
            return redirect('ewaf:four_workspace', pk=pk)
        except ValidationError as error:
            configuration_form.add_error(None, error)
    elif action in ('choice', 'record') and choice_form.is_valid():
        try:
            values = dict(choice_form.cleaned_data)
            versions = values.pop('expected_decisions')
            if action == 'record':
                version = (versions or {}).get(str(values['application_id'])) if isinstance(versions, dict) else None
                if not isinstance(version, dict) or set(version) != {'revision', 'previous'}:
                    raise ValidationError('HUMAN_DECISION_VERSION_REQUIRED')
                values['decision'] = {'SELECT_FOR_DEMONSTRATION': 'SELECT_DEMO',
                    'DEFER_FOR_REVIEW': 'DEFER_REVIEW', 'WITHDRAW_DEMO': 'WITHDRAW_DEMO'}[values['decision']]
                decision_services.record(pk, user=actor, expected_revision=version['revision'],
                    expected_previous=version['previous'], **values)
                return redirect('ewaf:four_workspace', pk=pk)
            choice = four_decisions.demonstrate(pk, user=actor, **values)
        except ValidationError as error:
            choice_form.add_error(None, error)
            current = None
    return render(request, 'ewaf/four_workspace.html', {'program': program, 'inventory': inventory,
        'policy': policy, 'readiness': policy_readiness(), 'mathematical': mathematical,
        'configuration_form': configuration_form, 'choice_form': choice_form, 'choice': choice,
        'current': current, 'findings': findings, 'decision_history': decision_history, 'can_decide': can_decide})
