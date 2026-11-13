import json
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from documents.models import DocumentVerification
from programs.models import ProgramApplication
from . import vault_services as service, vault_sources
from .vault_policy import enabled, scoring_pending, SOURCE_LABELS, SCORING_PENDING_MESSAGE
from .vault_forms import (VaultForm, PercentageWeightsForm, SaatyWeightsForm, saaty_state,
                          SesSetupForm, SesWeightsForm, ses_state, ses_proposal_state, ses_empty_state)
from .vault_models import VaultRevision
from .operational_services import actor, latest_configuration
from .weight_input import preview, percentages, proposal_criteria
from .household_criteria import CRITERIA, NAMES, criteria_for
from . import dataset_methods as methods


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def vault(request):
    if not enabled():
        raise Http404
    current = actor(request.user)
    can_configure = current.has_perm('ewaf.configure_operational')
    can_authorize = current.has_perm('ewaf.authorize_operational')
    # The active editor opens composite SES. Explicit historical links and
    # already-open forms keep their own signature; never relabel their weights.
    default_method = methods.HOUSEHOLD if request.method == 'POST' else methods.COMPOSITE
    method = request.POST.get('calculation_method', request.GET.get('method', default_method))
    if method not in methods.SIGNATURES:
        raise Http404
    codes = methods.criteria(method)
    latest = service.latest_for(method)
    if request.method == 'POST' and request.POST.get('action') == 'PREVIEW_WEIGHTS':
        if not (can_configure or can_authorize):
            raise PermissionDenied
        try:
            if request.POST.get('expected') != service.token():
                raise ValidationError('The vault changed. Reload before previewing weights.')
            proposal = json.loads(request.POST.get('slider_proposal', ''))
            if proposal_criteria(proposal) != codes:
                raise ValidationError('The proposal must match the selected method and criterion codes.')
            scope = 'ewaf-vault:' + method if method == methods.COMPOSITE else 'ewaf-vault'
            from .weight_input import CURRENT_METHOD, METHOD
            return JsonResponse(preview(proposal, program=scope, expected=service.token(),
                method=CURRENT_METHOD if method == methods.COMPOSITE else METHOD) |
                {'method': method, 'configuration_version': latest.revision if latest else None})
        except (ValidationError, ValueError) as error:
            return JsonResponse({'errors': error.messages if isinstance(error, ValidationError) else ['Invalid proposal.']}, status=400)
    # Already-open editors retain their explicit method; new pages use Saaty sliders.
    weight_state = ses_state(latest) if method in methods.SES_METHODS else saaty_state(latest)
    legacy_post = request.method == 'POST' and 'weight_method' not in request.POST
    if method in methods.SES_METHODS:
        if request.POST.get('action') == 'ADJUST_WEIGHTS':
            form_class = SesSetupForm
        elif method == methods.COMPOSITE and not (
                request.method == 'POST' and 'slider_proposal' not in request.POST
                and any(code in request.POST for code in codes)):
            # First visits use the volume editor directly. Older open setup
            # forms may still submit their explicit four percentages safely.
            form_class = SesWeightsForm
        else:
            form_class = SesWeightsForm if weight_state or 'slider_proposal' in request.POST else SesSetupForm
    else:
        form_class = (VaultForm if 'slider_proposal' in request.POST else PercentageWeightsForm) if legacy_post else SaatyWeightsForm
    options = {} if form_class is SesSetupForm else {'configuration': latest}
    if method in methods.SES_METHODS:
        options['method'] = method
    form = form_class(request.POST if request.method == 'POST' else None,
                     initial={'expected': service.token()}, **options)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action in ('ADJUST_WEIGHTS', 'DRAFT') and method in methods.SES_METHODS:
            if not can_configure:
                raise PermissionDenied
        elif not can_authorize:
            raise PermissionDenied
        if action == 'ADJUST_WEIGHTS' and isinstance(form, SesSetupForm):
            if form.is_valid():
                if form.cleaned_data['expected'] != service.token():
                    form.add_error(None, 'The vault changed. Reload before adjusting weights.')
                else:
                    weight_state = ses_proposal_state(form.cleaned_data['slider_proposal'], method)
                    form = SesWeightsForm(method=method, initial={
                        'expected': form.cleaned_data['expected'],
                        'reason': form.cleaned_data['reason'], 'slider_proposal': weight_state['proposal']})
        elif action not in (('DRAFT', 'LOCKED') if method in methods.SES_METHODS else ('LOCKED',)):
            form.add_error(None, 'Choose Approve configuration to save the shared weights.')
        elif form.is_valid():
            try:
                if method == methods.COMPOSITE and action == 'LOCKED':
                    approved = service.approve_current_weights(user=current, expected=form.cleaned_data['expected'],
                        proposal=form.cleaned_data['slider_proposal'], review=form.cleaned_data.get('weight_review', ''),
                        reason=form.cleaned_data['reason'])
                elif method in methods.SES_METHODS:
                    approved = service.record_ses_weights(user=current, expected=form.cleaned_data['expected'],
                        proposal=form.cleaned_data['slider_proposal'], reason=form.cleaned_data['reason'], status=action, method=method)
                elif isinstance(form, SaatyWeightsForm):
                    approved = service.approve(user=current, expected=form.cleaned_data['expected'],
                        proposal=form.cleaned_data['slider_proposal'], reason=form.cleaned_data['reason'],
                        preserve_saved=False)
                elif isinstance(form, VaultForm):
                    approved = service.approve(user=current, expected=form.cleaned_data['expected'],
                        proposal=form.cleaned_data['slider_proposal'])
                else:
                    approved = service.approve_percentages(user=current, expected=form.cleaned_data['expected'],
                        values=form.cleaned_data['values'], reason=form.cleaned_data['reason'])
            except ValidationError as error:
                form.add_error(None, error)
            else:
                from django.contrib import messages
                if action == 'DRAFT':
                    messages.success(request, 'Unapproved SES weight draft saved. Review its calculated AHP weights before approval.')
                elif method == methods.COMPOSITE:
                    messages.success(request, 'Configuration approved for programs without published results. Programs with published results keep their ranking weights and can still generate rankings. Open EWAF Ranking and select a ready program.')
                elif scoring_pending(approved.policy):
                    messages.warning(request, SCORING_PENDING_MESSAGE)
                else:
                    messages.success(request, 'EWAF configuration approved. New programs inherit this version.')
                if method in methods.SES_METHODS:
                    from django.urls import reverse
                    return redirect(reverse('ewaf:vault') + '?method=' + method)
                return redirect('ewaf:vault')
    if isinstance(form, SesWeightsForm) and not weight_state:
        # Keep an unsaved proposal editable after a missing reason or stale save.
        proposed = getattr(form, 'cleaned_data', {}).get('slider_proposal')
        if proposed:
            weight_state = ses_proposal_state(proposed, method)
        elif method == methods.COMPOSITE:
            weight_state = ses_empty_state(method)
    active = service.active(method)
    if method == methods.COMPOSITE and weight_state:
        weight_state['requireSavedProposal'] = False
        if not weight_state['startingFromSaved']:
            weight_state['startingLabel'] = 'Choose your weights, calculate the AHP result, then approve the configuration.'
    weights = percentages(active.validation['weights']) if active else {}
    history = Paginator(VaultRevision.objects.all(), 20).get_page(request.GET.get('page'))
    for item in history:
        retained_weights = percentages(item.validation['weights']) if item.validation else {}
        item.display_rows = [{'name': NAMES[code], 'rule': item.policy.get('criteria', {}).get(code, {}),
            'weight': f'{retained_weights[code] / 100:.2f}%' if retained_weights else 'Not configured'} for code in criteria_for(item.policy)]
        item.method_label = methods.LABELS.get(methods.method_of(item.policy), 'Historical method')
    from .revised import live_services
    from .revised.live_models import SharedDatasetPolicy
    policy_enabled = live_services.enabled() and live_services.schema_available()
    scoring_policy = SharedDatasetPolicy.objects.filter(method=method).first() if policy_enabled else None
    from .vault_weights import is_direct
    display_names = {'SES': 'Income SES & 4Ps' if method == methods.COMPOSITE else 'Income SES',
        'ES': 'Employment Status', 'PA': 'Previous Assistance', 'HM': 'Household Members',
        'HI': 'Household Income', 'SI': 'Socioeconomic Indicator', 'ND': 'Dependents'}
    source_labels = {'SES': 'Income & 4Ps' if method == methods.COMPOSITE else 'Household income',
        'ES': 'Employment status', 'PA': 'Release history', 'HM': 'Registration count',
        'HI': 'Registered income', 'SI': '4Ps information', 'ND': 'Registered dependents'}
    if weight_state:
        weight_state['displayNames'] = display_names
        weight_state['sourceLabels'] = source_labels
    if 'reason' in form.fields:
        form.fields['reason'].widget.attrs['placeholder'] = 'Reason for adjusting weights...'
    return render(request, 'ewaf/vault.html', {'form': form, 'latest': latest, 'active': active,
        'direct_weights': bool(active and is_direct(active.policy)),
        'weight_state': weight_state,
        'is_ses': method in methods.SES_METHODS, 'ses_setup': isinstance(form, SesSetupForm),
        'method': method, 'method_label': methods.LABELS[method],
        'ses_description': methods.ses_description(method), 'is_composite': method == methods.COMPOSITE,
        'dataset_policy_enabled': policy_enabled, 'scoring_policy': scoring_policy,
        'can_configure': can_configure, 'can_authorize': can_authorize,
        'weight_rows': [{'name': NAMES[code], 'display_name': display_names[code],
            'source_label': source_labels[code], 'value': f'{weights[code] / 100:.2f}'}
            for code in sorted(codes, key=lambda code: -weights[code])] if active else [],
        'history': history, 'one_click': True,
        'fixed_scoring': method == methods.COMPOSITE,
        'scoring_pending': bool(active and method != methods.COMPOSITE and scoring_pending(active.policy)),
        'scoring_pending_message': SCORING_PENDING_MESSAGE,
        'source_rows': [{'code': code, 'name': NAMES[code], 'source': service.vault_policy.source_policy(method)['criteria'][code]['measure']}
                        for code in codes]})


class RegisteredReviewForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    observation_start = forms.DateField(label='Verified information covers dates from', widget=forms.DateInput(attrs={'type': 'date'}))
    observation_end = forms.DateField(label='Through', widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}), label='Review explanation')
    confirmed = forms.BooleanField(label='I verified these registered values against the selected evidence and the approved assessment period.')

    def __init__(self, *args, application, configuration, **kwargs):
        super().__init__(*args, **kwargs)
        for code in CRITERIA:
            if code == 'PA':
                continue
            allowed = configuration.policy['criteria'][code]['evidence_document_types']
            self.fields['evidence_' + code] = forms.ModelMultipleChoiceField(
                queryset=DocumentVerification.objects.filter(document__application=application.member.application,
                    document__requirement__document_type_id__in=allowed, verified=True,
                    member_version=application.member.version).select_related('document__requirement'),
                label=NAMES[code] + ' - verified supporting documents', widget=forms.CheckboxSelectMultiple)
        for field in self.fields.values():
            if not field.widget.is_hidden and not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def registered_review(request, reference):
    if not enabled():
        raise Http404
    current = actor(request.user, 'ewaf.review_criterionassessment')
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member__application'), pk=reference)
    try:
        configuration = latest_configuration(application.program)
    except ValidationError:
        return redirect('programs:manage_detail', pk=application.program_id)
    if not configuration.vault_revision_id:
        raise Http404
    form = RegisteredReviewForm(request.POST if request.method == 'POST' else None,
        application=application, configuration=configuration,
        initial={'expected': vault_sources.review_token(application, configuration)})
    if request.method == 'POST' and form.is_valid():
        try:
            data = form.cleaned_data
            vault_sources.record_review(reference, user=current, expected=data['expected'], reason=data['reason'],
                observation_start=data['observation_start'], observation_end=data['observation_end'], confirmed=data['confirmed'],
                supporting_review_ids={code: list(data['evidence_' + code].values_list('pk', flat=True)) for code in CRITERIA if code != 'PA'})
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect('ewaf:operational_workspace', pk=application.program_id)
    source = vault_sources.sources(application, configuration, vault_sources.source_context(application))
    return render(request, 'ewaf/registered_review.html', {'application': application, 'form': form,
        'configuration': configuration, 'rows': [{'name': NAMES[code], **source['inputs'][code]} for code in CRITERIA]})
