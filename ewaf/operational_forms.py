"""Guided policy fields; empty values remain unresolved, never production defaults."""
from django import forms
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .evidence import SOURCE_TYPES
from .four_criterion_development import SCALE
from .household_criteria import CRITERIA, criteria_for, pairs_for, SOURCES

EMPTY = [('', 'Not configured')]


class ConfigurationForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    criteria_profile = forms.CharField(required=False, widget=forms.HiddenInput)
    slider_proposal = forms.JSONField(required=False, widget=forms.HiddenInput)
    weight_review = forms.CharField(required=False, widget=forms.HiddenInput)
    accept_derived_weights = forms.BooleanField(required=False,
        label='I reviewed the resulting AHP weights and accept these slider-derived comparisons. They are not independently elicited judgments.')
    authority_reference = forms.CharField(required=False, max_length=500, label='Association authority reference')
    authorized_scope = forms.CharField(required=False, max_length=2000, label='Authorized program scope')
    approval_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    effective_from = forms.DateTimeField(required=False, widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    effective_until = forms.DateTimeField(required=False, widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    selection_rule = forms.ChoiceField(required=False, choices=EMPTY + [('reasoned_human_within_slots', 'Reasoned individual human decisions within approved slots')])
    tie_rule = forms.ChoiceField(required=False, choices=EMPTY + [('hold', 'Hold exact ties for review'), ('reasoned_human', 'Apply the documented human tie procedure')])
    tie_procedure = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Approved tie procedure and authority')
    classification_mode = forms.ChoiceField(required=False, choices=EMPTY + [('none', 'Explicitly authorized: no need classifications'), ('thresholds', 'Approved threshold classifications')])
    classifications = forms.JSONField(required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text='Only for thresholds: [{"label":"Approved label","lower":"0","upper":"100"}]. These are format placeholders, not policy values. Ranges use lower-inclusive/upper-exclusive boundaries; 100 is included in the final range.')
    edge_cases = forms.ChoiceField(required=False, choices=EMPTY + [('block', 'Block missing, disputed, stale, equal-bound and out-of-range input')])
    pa_scope = forms.ChoiceField(required=False, choices=EMPTY + [('all_programs', 'All programs'), ('this_program', 'This program only')])
    pa_period = forms.ChoiceField(required=False, choices=EMPTY + [('all_retained', 'All retained successful releases'), ('date_range', 'Explicit inclusive release-date interval')])
    pa_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    pa_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    attested = forms.BooleanField(required=False, label='I verified these exact rules, evidence definitions, scope and dates against the recorded Association authority.')

    def __init__(self, *args, configuration=None, program=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.configuration = configuration
        self.criteria = criteria_for(configuration.policy) if configuration else CRITERIA
        self.pairs = pairs_for(self.criteria)
        self.initial['criteria_profile'] = 'household_five' if self.criteria == CRITERIA else 'legacy_four'
        self.program = program
        self.weight_provenance = None
        for pair in self.pairs:
            self.fields['pair_' + pair.replace(':', '_')] = forms.ChoiceField(required=False,
                choices=EMPTY + [(v, v) for v in SCALE], widget=forms.HiddenInput,
                label='AHP ' + pair.replace(':', ' compared with '))
        for code in self.criteria:
            fields = {
                'measure': forms.CharField(required=False, max_length=1000),
                'source_type': forms.ChoiceField(required=False, choices=EMPTY + [(v, v.replace('_', ' ')) for v in ((SOURCES[code],) if self.criteria == CRITERIA else SOURCE_TYPES[code])]),
                'value_type': forms.ChoiceField(required=False, choices=EMPTY + [(v, v) for v in ('decimal', 'integer', 'text', 'category')]),
                'unit': forms.CharField(required=False, max_length=100),
                'direction': forms.ChoiceField(required=False, choices=EMPTY + [('benefit', 'Higher verified value means greater need'), ('inverse', 'Lower verified value means greater need')]),
                'lower': forms.CharField(required=False, max_length=100, label=code + ' lower normalization bound'),
                'upper': forms.CharField(required=False, max_length=100, label=code + ' upper normalization bound'),
                'encoding': forms.JSONField(required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='Exact category-to-number JSON mapping; numeric criteria may leave this empty.'),
                'observation_period': forms.CharField(required=False, max_length=1000),
            }
            for key, field in fields.items():
                if not field.label:
                    field.label = code + ' ' + key.replace('_', ' ')
                self.fields[code + '_' + key] = field
        for role in ('functional_need', 'consent', 'accessible_alternative'):
            for key in ('item', 'accepted_outcome'):
                self.fields['PR_' + role + '_' + key] = forms.CharField(required=False, max_length=100,
                    label='PR ' + role.replace('_', ' ') + ': rubric ' + key.replace('_', ' '))
        if configuration:
            self.initial.update({key: value for key, value in configuration.policy.items() if key in self.fields})
            for name in ('effective_from', 'effective_until'):
                value = self.initial.get(name)
                if value:
                    parsed = parse_datetime(value)
                    if parsed is not None and timezone.is_aware(parsed):
                        self.initial[name] = timezone.localtime(parsed)
            for code, rule in configuration.policy.get('criteria', {}).items():
                for key, value in {**rule, **rule.get('bounds', {})}.items():
                    self.initial[code + '_' + key] = value
            for role, rule in configuration.policy.get('eligibility', {}).items():
                for key, value in rule.items():
                    self.initial['PR_' + role + '_' + key] = value
            for pair, value in configuration.judgments.items():
                self.initial['pair_' + pair.replace(':', '_')] = value
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else ('form-select' if isinstance(field.widget, forms.Select) else 'form-control')

    def clean(self):
        values = super().clean()
        proposal = values.get('slider_proposal')
        if proposal is not None:
            from .weight_input import accept
            if not values.get('accept_derived_weights'):
                raise forms.ValidationError('Explicitly accept the previewed AHP weights before saving a slider proposal.')
            judgments, self.weight_provenance = accept(values.get('weight_review', ''), proposal,
                program=self.program.pk, expected=values.get('expected'))
            for pair, value in judgments.items():
                values['pair_' + pair.replace(':', '_')] = value
        elif self.configuration:
            judgments = {pair: values.get('pair_' + pair.replace(':', '_')) for pair in self.pairs}
            if judgments == self.configuration.judgments:
                self.weight_provenance = self.configuration.policy.get('weight_input')
        return values

    def proposed(self):
        values = self.cleaned_data
        result = {key: (value.isoformat() if hasattr(value, 'isoformat') else value) for key, value in values.items()
                  if key not in ('expected', 'criteria_profile', 'reason', 'attested', 'slider_proposal', 'weight_review', 'accept_derived_weights') and not key.startswith(('pair_', 'HI_', 'SI_', 'ES_', 'PA_', 'ND_', 'HM_', 'PR_'))}
        if self.weight_provenance:
            result['weight_input'] = self.weight_provenance
        result['criteria'] = {}
        for code in self.criteria:
            rule = {key: values[code + '_' + key] for key in ('measure', 'source_type', 'value_type', 'unit', 'direction', 'encoding', 'observation_period')}
            rule['bounds'] = {'method': 'fixed', 'lower': values[code + '_lower'], 'upper': values[code + '_upper']}
            rule['edge_cases'] = result['edge_cases']
            result['criteria'][code] = rule
        result['eligibility'] = {role: {key: values['PR_' + role + '_' + key] for key in ('item', 'accepted_outcome')}
                                 for role in ('functional_need', 'consent', 'accessible_alternative')}
        return result

    def judgments(self):
        return {pair: self.cleaned_data['pair_' + pair.replace(':', '_')] for pair in self.pairs}

    def sections(self):
        groups = [('Authority and selection policy', [name for name in self.fields if not name.startswith(('pair_', 'HI_', 'SI_', 'ES_', 'PA_', 'ND_', 'HM_', 'PR_')) and name not in ('expected', 'criteria_profile', 'reason', 'attested', 'slider_proposal', 'weight_review', 'accept_derived_weights')])]
        groups += [(code + ' measurement and normalization', [name for name in self.fields if name.startswith(code + '_')]) for code in self.criteria]
        groups += [('Program Relevance eligibility', [name for name in self.fields if name.startswith('PR_')]),
                   ('Review confirmation', ['reason', 'attested'])]
        return [(label, [self[name] for name in names]) for label, names in groups]


class WeightConfigurationForm(ConfigurationForm):
    """Change weights only; recorded scoring definitions never come from this POST."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        keep = {'criteria_profile', 'expected', 'slider_proposal', 'weight_review', 'accept_derived_weights', 'reason', 'attested'}
        for name in list(self.fields):
            if name not in keep and not name.startswith('pair_'):
                del self.fields[name]
        self.fields['attested'].label = 'I confirm these weights under the recorded program authority.'

    def proposed(self):
        from copy import deepcopy
        result = deepcopy(self.configuration.policy) if self.configuration else {
            'criteria': {code: {} for code in self.criteria}}
        result.pop('weight_input', None)
        if self.weight_provenance:
            result['weight_input'] = self.weight_provenance
        return result


class GenerateForm(forms.Form):
    audit_reason = 'Generated EWAF ranking using the current approved configuration and accepted applicant information.'
    expected = forms.JSONField(widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)


class DecisionForm(forms.Form):
    run_id = forms.IntegerField(widget=forms.HiddenInput)
    application_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    outcome = forms.ChoiceField(choices=[('DEFERRED', 'Defer for review'), ('SELECTED', 'Select beneficiary'), ('NOT_SELECTED', 'Not selected')], widget=forms.Select(attrs={'class': 'form-select'}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    tie_reason = forms.CharField(required=False, max_length=2000, label='Application of the approved tie procedure', widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))


class SelectAssistanceForm(forms.Form):
    audit_reason = 'Administrator selected this applicant for assistance from the current EWAF ranking.'
    run_id = forms.IntegerField(widget=forms.HiddenInput)
    application_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    tie_reason = DecisionForm.base_fields['tie_reason']


class UnselectAssistanceForm(forms.Form):
    run_id = forms.IntegerField(widget=forms.HiddenInput)
    application_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
