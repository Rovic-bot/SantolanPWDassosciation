"""Weights are the only editable shared configuration inputs."""
from django import forms
from .household_criteria import CRITERIA, NAMES
from .weight_input import METHOD, CURRENT_METHOD, initial_state, project, proposal_criteria
from .dataset_methods import SES


def saaty_state(configuration=None):
    """Keep usable saved weights; use the document's unequal proposal otherwise."""
    from copy import deepcopy
    from .vault_weights import compile_weights
    from .revised.math import DEFAULTS
    state = initial_state(configuration)
    origin = (configuration.policy.get('weight_input') or {}) if configuration else {}
    if origin.get('method') == METHOD and proposal_criteria(origin.get('proposal')) == CRITERIA:
        # Reopening a saved proposal must not quantize its calculated weights a second time.
        state['proposal'] = deepcopy(origin['proposal'])
        state['resetProposal'] = deepcopy(origin['proposal'])
        state['startingLabel'] = 'Starting from the saved slider proposal and its calculated Saaty weights.'
    elif not state['startingFromSaved'] or set(state['proposal']['weights']) != set(CRITERIA):
        _, origin = compile_weights(dict(zip(CRITERIA, DEFAULTS)))
        state['proposal'] = origin['proposal']
        state['resetProposal'] = origin['proposal']
        state['names'] = {code: NAMES[code] for code in CRITERIA}
        state['startingLabel'] = 'Starting from the computation document percentages. Review the calculated Saaty weights before approval.'
    return state


class PercentageWeightsForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Reason for this weight version', max_length=2000,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, configuration=None, **kwargs):
        from decimal import Decimal
        from .vault_weights import initial_values
        from .revised.math import CRITERIA, NAMES, LIMITS
        super().__init__(*args, **kwargs)
        for code, name, (lower, upper) in zip(CRITERIA, NAMES, LIMITS):
            self.fields[code] = forms.DecimalField(label=f'{name} ({code})',
                min_value=Decimal(lower), max_value=Decimal(upper), decimal_places=2, max_digits=5,
                initial=initial_values(configuration)[code],
                help_text=f'{lower}% to {upper}%.', widget=forms.NumberInput(attrs={
                    'class': 'form-control', 'step': '0.01', 'data-vault-percentage': code}))

    def clean(self):
        from .vault_weights import compile_weights
        from .revised.math import CRITERIA
        data = super().clean()
        if all(code in data for code in CRITERIA[:4]):
            data['values'] = {code: str(data[code]) for code in CRITERIA[:4]}
            compile_weights(data['values'])
        return data

    @property
    def weight_fields(self):
        from .revised.math import CRITERIA
        return [self[code] for code in CRITERIA[:4]]

    @property
    def remainder(self):
        from .revised.math import CRITERIA, proposal, display, CalculationError
        try:
            values = {code: str(self[code].value()) for code in CRITERIA[:4]}
            return display(proposal(values)[-1] * 100)
        except CalculationError:
            return 'Invalid'


class VaultForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    slider_proposal = forms.JSONField(widget=forms.HiddenInput)

    def __init__(self, *args, configuration=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['slider_proposal'] = initial_state(configuration)['proposal']

    def clean_slider_proposal(self):
        proposal = self.cleaned_data['slider_proposal']
        if proposal_criteria(proposal) != CRITERIA:
            raise forms.ValidationError('Include all five registered household criteria.')
        self.comparisons, self.validation, self.provenance = project(proposal)
        return proposal


class SaatyWeightsForm(VaultForm):
    weight_method = forms.ChoiceField(choices=[(METHOD, METHOD)], initial=METHOD,
        widget=forms.HiddenInput)
    reason = forms.CharField(label='Reason for this weight version', max_length=2000,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, configuration=None, **kwargs):
        super().__init__(*args, configuration=configuration, **kwargs)
        self.initial['slider_proposal'] = saaty_state(configuration)['proposal']


def ses_empty_state(method=SES):
    """Visible controls with no selected or stored weight vector."""
    from .dataset_methods import SES_CRITERIA, SES_METHODS, COMPOSITE
    if method not in SES_METHODS:
        raise forms.ValidationError('Choose a supported SES method.')
    names = {code: NAMES[code] for code in SES_CRITERIA}
    if method == COMPOSITE:
        names['SES'] = 'Income-based SES with a verified 4Ps adjustment'
    return {'proposal': None, 'resetProposal': None, 'criteria': list(SES_CRITERIA), 'names': names,
        'hasSavedWeights': False, 'startingFromSaved': False,
        'startingLabel': 'No weights selected. Move the top slider to begin; the remaining weight is shared below it. '
            'Then adjust the second and third sliders. Nothing is saved until you save a draft.',
        'requireSavedProposal': True, 'approvableProposal': None}


def ses_proposal_state(proposal, method=SES):
    """Render an explicitly chosen, unsaved proposal in the shared slider editor."""
    from copy import deepcopy
    from .dataset_methods import SES_CRITERIA, COMPOSITE
    if proposal_criteria(proposal) != SES_CRITERIA:
        raise forms.ValidationError('Include exactly SES, ES, PA and HM.')
    project(proposal, method=CURRENT_METHOD if method == COMPOSITE else METHOD)
    return ses_empty_state(method) | {
        'proposal': deepcopy(proposal), 'resetProposal': deepcopy(proposal),
        'startingLabel': 'Unsaved starting weights chosen by you. Adjust the sliders, then save a weight draft for review.'}


def ses_state(configuration):
    from .dataset_methods import SES_CRITERIA, is_ses
    if not configuration or not is_ses(configuration.policy):
        return None
    origin = configuration.policy.get('weight_input', {})
    if origin.get('method') not in (METHOD, CURRENT_METHOD) or proposal_criteria(origin.get('proposal')) != SES_CRITERIA:
        return None
    state = ses_proposal_state(origin['proposal'], configuration.policy['method'])
    return state | {
        'hasSavedWeights': configuration.status == 'LOCKED', 'startingFromSaved': True,
        'startingLabel': f'SES weight version {configuration.revision} — {configuration.get_status_display()}. '
            'Slider-generated comparisons processed by AHP. No historical weights were converted.',
        'requireSavedProposal': True,
        'approvableProposal': state['proposal'] if configuration.status == 'DRAFT' else None}


class SesSetupForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    calculation_method = forms.ChoiceField(choices=[(SES, SES)], initial=SES, widget=forms.HiddenInput)
    reason = forms.CharField(label='Weight draft explanation', max_length=2000,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, method=SES, **kwargs):
        from decimal import Decimal
        from .dataset_methods import SES_CRITERIA
        super().__init__(*args, **kwargs)
        if not self.is_bound or self.data.get('action') == 'ADJUST_WEIGHTS':
            self.fields['reason'].required = False
            self.fields['reason'].help_text = 'Optional until you save a weight draft.'
        self.fields['calculation_method'].choices = [(method, method)]
        self.initial['calculation_method'] = method
        for code in SES_CRITERIA:
            self.fields[code] = forms.DecimalField(label=NAMES[code], min_value=Decimal('0.01'),
                max_value=Decimal('99.99'), decimal_places=2, max_digits=5,
                widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))

    def clean(self):
        from .dataset_methods import SES_CRITERIA
        data = super().clean()
        if all(code in data for code in SES_CRITERIA):
            weights = {code: int(data[code] * 100) for code in SES_CRITERIA}
            data['slider_proposal'] = {'order': sorted(SES_CRITERIA, key=lambda code: -weights[code]), 'weights': weights}
            project(data['slider_proposal'])
        return data

    @property
    def weight_fields(self):
        from .dataset_methods import SES_CRITERIA
        return [self[code] for code in SES_CRITERIA]


class SesWeightsForm(SaatyWeightsForm):
    calculation_method = forms.ChoiceField(choices=[(SES, SES)], initial=SES, widget=forms.HiddenInput)
    weight_review = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, configuration=None, method=SES, **kwargs):
        forms.Form.__init__(self, *args, **kwargs)
        self.fields['calculation_method'].choices = [(method, method)]
        self.initial['calculation_method'] = method
        state = ses_state(configuration)
        self.initial.setdefault('slider_proposal', state['proposal'] if state else None)

    def clean_slider_proposal(self):
        from .dataset_methods import SES_CRITERIA, COMPOSITE
        value = self.cleaned_data['slider_proposal']
        if proposal_criteria(value) != SES_CRITERIA:
            raise forms.ValidationError('Include exactly SES, ES, PA and HM.')
        self.comparisons, self.validation, self.provenance = project(value,
            method=CURRENT_METHOD if self.initial['calculation_method'] == COMPOSITE else METHOD)
        return value
