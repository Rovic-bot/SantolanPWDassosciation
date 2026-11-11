from copy import deepcopy
from django import forms
from documents.models import DocumentType, DocumentVerification
from ewaf.vault_models import VaultRevision
from .live_models import SharedDatasetPolicy
from . import contracts, live_evidence, si, member_record_evidence, automatic_inputs
from .engine import CRITERIA, ES
from ewaf import dataset_methods as methods


class PolicyDraftForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    calculation_method = forms.ChoiceField(choices=list(methods.LABELS.items()), required=False, widget=forms.HiddenInput)
    weight = forms.ModelChoiceField(queryset=VaultRevision.objects.filter(status='LOCKED'), required=False,
                                   label='A. Exact locked weight version to reuse')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Draft revision explanation')
    from .shared_application import CUTOFFS
    shared_cutoff = forms.ChoiceField(choices=[('', 'Choose once for all covered programs'), *CUTOFFS.items()],
        required=False, label='Shared assessment cutoff rule',
        help_text='After central approval, apply these exact weights and rules automatically to compatible programs without a scoring binding. Existing calculations and scoring bindings retain their versions.')
    shared_cutoff_at = forms.DateTimeField(required=False, label='Fixed cutoff (only for the fixed-date rule)')

    def __init__(self, *args, content, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = deepcopy(content)
        if self.is_bound and methods.is_composite(content):
            self.content['choices']['evidence_rule']['value'] = self.data.get('evidence_rule', '')
        self.initial['calculation_method'] = content['method']
        shared = content.get('program_application', {})
        self.initial['shared_cutoff'] = shared.get('cutoff_rule', '')
        self.initial['shared_cutoff_at'] = shared.get('cutoff_at', '')
        compatible = [row.pk for row in VaultRevision.objects.filter(status='LOCKED')
                      if methods.method_of(row.policy) in methods.compatible_weight_methods(content['method'])]
        self.fields['weight'].queryset = VaultRevision.objects.filter(pk__in=compatible)
        self.fields['weight'].label_from_instance = lambda row: f'Locked Vault version {row.revision} — {row.recorded_at}'
        for key, (group, label, kind) in contracts.specifications(content).items():
            if not contracts.applicable(self.content, key):
                continue
            options = dict(required=False, label=label, initial=content['choices'][key]['value'])
            if isinstance(kind, dict):
                choices = [('', 'Unspecified'), *kind.items()]
                if not methods.is_ses(content) and self.content['choices']['si_rubric']['value'] == si.METHOD and key in ('si_rubric', 'input_domain'):
                    value = si.METHOD if key == 'si_rubric' else 'document_values'
                    choices = [(value, kind[value])]
                field = forms.ChoiceField(choices=choices, **options)
            elif kind == 'integer':
                field = forms.IntegerField(min_value=1, max_value=3660 if key == 'evidence_max_age_days' else 120, **options)
            elif kind == 'datetime':
                field = forms.DateTimeField(**options)
            elif kind == 'documents':
                field = forms.ModelMultipleChoiceField(queryset=DocumentType.objects.order_by('name'), **options)
            else:
                field = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 2}), **options)
            field.help_text = content['proposals'].get(key, 'Unspecified')
            if key in ('method_rules', 'input_domain'):
                field.help_text = ('For new rankings, employment uses Employed=1, Self-Employed=2, '
                    'Student=3, Retired=4, Unemployed=5. This supersedes the historical employment '
                    'encoding below; other retained calculation rules still apply. ' + field.help_text)
            if not methods.is_ses(content) and self.content['choices']['si_rubric']['value'] == si.METHOD:
                if key == 'si_rubric':
                    field.help_text = 'Confirmed SI scores: 5 for both; 2.5 for either one; 0 for neither. Review both findings.'
                elif key == 'input_domain':
                    field.help_text = contracts.SPECS[key][2]['document_values']
            self.fields[key] = field
            self.fields['specified_' + key] = forms.BooleanField(required=False,
                label='This exact choice is specified for policy review', initial=content['choices'][key]['specified'])
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                    else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')

        if automatic_inputs.enabled(self.content):
            from members.profile import EMPLOYMENT
            from ewaf.employment_scoring import VERSION, MAPPING, SCORES
            mapping = MAPPING
            self.content['registration_inputs'] = {'version': VERSION, 'employment': dict(MAPPING)}
            for key, label in EMPLOYMENT:
                self.fields['employment_map_' + key] = forms.ChoiceField(required=True, disabled=True,
                    choices=[(mapping[key], f'{mapping[key]} = {SCORES[mapping[key]]}')],
                    initial=mapping.get(key, ''), label='Recorded ' + label + ': scoring category',
                    widget=forms.Select(attrs={'class': 'form-select'}))

    def clean_calculation_method(self):
        value = self.cleaned_data['calculation_method'] or self.content['method']
        if value != self.content['method']:
            raise forms.ValidationError('Reload the policy editor for the selected method.')
        return value

    def policy_content(self):
        result = deepcopy(self.content)
        from .shared_application import VERSION, SCOPE
        cutoff = self.cleaned_data['shared_cutoff_at']
        result['program_application'] = {'version': VERSION, 'scope': SCOPE,
            'cutoff_rule': self.cleaned_data['shared_cutoff'], 'cutoff_at': cutoff.isoformat() if cutoff else ''}
        for key, (_, _, kind) in contracts.specifications(self.content).items():
            if not contracts.applicable(self.content, key):
                result['choices'][key] = {'value': '', 'specified': False}
                continue
            value = self.cleaned_data[key]
            if kind == 'documents':
                value = list(value.values_list('pk', flat=True)) if value is not None else []
            elif kind == 'datetime':
                value = value.isoformat() if value else ''
            result['choices'][key] = {'value': value, 'specified': self.cleaned_data['specified_' + key]}
        if automatic_inputs.enabled(result):
            from members.profile import EMPLOYMENT
            from ewaf.employment_scoring import VERSION
            result['registration_inputs'] = {'version': VERSION,
                'employment': {key: self.cleaned_data['employment_map_' + key] for key, _ in EMPLOYMENT
                               if self.cleaned_data['employment_map_' + key]}}
        else:
            result.pop('registration_inputs', None)
        return result

    @property
    def employment_mapping_fields(self):
        return [self[key] for key in self.fields if key.startswith('employment_map_')]

    def groups(self):
        return [{'code': group, 'decisions': contracts.decisions(self.content)[group],
                 'rows': [{'field': self[key], 'specified': self['specified_' + key]}
                          for key, (code, _, _) in contracts.specifications(self.content).items()
                          if code == group and contracts.applicable(self.content, key)]}
                for group in ('A', 'B', 'C')]


class ApprovalForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    group_A = forms.BooleanField(label='A: I authorize reuse of the exact displayed compatible locked vector, with its recorded provenance.')
    group_B = forms.BooleanField(label='B: I authorize the displayed SI rubric, definitions and assessor authority.')
    group_C = forms.BooleanField(label='C: I authorize every displayed specified data-handling rule and effective scope; no unresolved item is hidden.')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Approval authority and review record')

    def __init__(self, *args, content=None, **kwargs):
        super().__init__(*args, **kwargs)
        if methods.is_ses(content):
            self.fields['group_B'].label = 'B: I authorize the income-based SES measure, assessment authority and discrepancy-review procedure.'
        if methods.is_composite(content):
            self.fields['group_B'].label = 'B: I authorize SES = I × (0.90 + 0.10 × P), its fixed internal coefficients, and the household 4Ps/evidence/relationship review procedures.'
        if content and content.get('program_application'):
            self.fields['group_C'].label = 'C: I authorize every displayed rule, including automatic application to all compatible unbound programs and the shared assessment cutoff rule.'


class BindingForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    policy = forms.ModelChoiceField(queryset=SharedDatasetPolicy.objects.filter(status='APPROVED'), label='Exact approved scoring-policy version')
    cutoff = forms.DateTimeField(label='Assessment cutoff (Philippine time unless a timezone is supplied)',
        help_text='At or after approved application closing. This does not change either application date.')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Program binding explanation')


class InputReviewForm(forms.Form):
    expected = forms.CharField(widget=forms.HiddenInput)
    employment = forms.ChoiceField(choices=[('', 'Unresolved'), *[(key, key) for key in ES]], required=False)
    household_members = forms.IntegerField(min_value=1, required=False)
    history_complete = forms.BooleanField(required=False, label='The selected verified evidence establishes complete PA coverage for the displayed period.')
    assessment_finding = forms.CharField(required=False, max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Review explanation')
    confirmed = forms.BooleanField(label='I reviewed these findings and their supporting evidence under the displayed policy.')

    def __init__(self, *args, application, configuration, **kwargs):
        super().__init__(*args, **kwargs)
        self.configuration = configuration
        from ewaf.employment_scoring import SCORES
        self.fields['employment'].choices = [('', 'Unresolved'), *[(key, f'{key} — score {score}') for key, score in SCORES.items()]]
        record_source = member_record_evidence.enabled(configuration.policy)
        if record_source:
            self.fields['history_complete'].label = 'I reviewed the Association release ledger for the displayed period.'
            self.fields['confirmed'].label = 'I reviewed these findings against the member record and the displayed rules.'
            self.fields['assessment_finding'].label = 'Member-record assessment'
        for i in range(configuration.policy['income_months']):
            self.fields[f'income_{i}'] = forms.CharField(required=False, max_length=160, label=f'Accepted household income for month {i + 1} (oldest first)')
        if methods.is_ses(configuration.policy):
            self.fields['income_consistency'] = forms.ChoiceField(required=False,
                label='SES income and evidence consistency review', choices=[('', 'Not reviewed'),
                    ('consistent', 'Reviewed: dates, income and evidence are consistent'),
                    ('resolved', 'A discrepancy was reviewed and resolved'), ('unresolved', 'Needs review: discrepancy unresolved')],
                help_text=methods.ses_description(configuration.policy))
            self.fields['income_resolution'] = forms.CharField(required=False, max_length=4000,
                label='Discrepancy resolution and accepted-income basis', widget=forms.Textarea(attrs={'rows': 3}),
                help_text='For a resolved discrepancy, explain the period, circumstances and why the accepted income is supported. '
                    'Accepted PHP 100,000 stays PHP 100,000 even with 4Ps or indigency evidence.')
        elif si.document_rule(configuration.policy):
            for name, label in [('four_ps', 'SI: Is the member a verified 4Ps member?'),
                                ('indigency', 'SI: Has the member provided a verified Certificate of Indigency?')]:
                self.fields['si_' + name] = forms.ChoiceField(required=False, label=label,
                    choices=[('', 'Not reviewed'), ('yes', 'Yes'), ('no', 'No')], help_text=si.LABEL)
        else:
            for name, label in [('food', 'Food access'), ('housing', 'Housing and essential utilities'), ('care', 'Necessary care and daily support')]:
                self.fields['si_' + name] = forms.ChoiceField(required=False, label=label,
                    choices=[('', 'Unresolved'), ('none', 'No unmet barrier'), ('occasional', 'Occasional'), ('recurrent', 'Recurrent'), ('critical', 'Current critical barrier')])
        if methods.is_composite(configuration.policy):
            self.fields['household_four_ps'] = forms.ChoiceField(required=False,
                label='Reviewed household 4Ps participation at cutoff',
                choices=[('', 'Unresolved / not reviewed'), ('yes', 'Verified Yes'), ('no', 'Verified No')],
                help_text='Missing, expired or disputed information is unresolved, not No. Follow the approved review procedure; no DSWD database access is assumed.')
            self.fields['four_ps_household_confirmed'] = forms.BooleanField(required=False,
                label='I reviewed the applicant’s household relationship and whether current 4Ps participation applies under the approved process.')
            self.fields['four_ps_household_review'] = forms.CharField(required=False, max_length=4000,
                label='Household 4Ps finding, relationship and evidence basis', widget=forms.Textarea(attrs={'rows': 3}),
                help_text='Identify the permitted SES supporting evidence/assessment and approved procedure for this Yes or No finding. '
                    'A shared assessment can support income and 4Ps when authorized; no additional certificate is prescribed here.')
            if record_source:
                self.fields['four_ps_household_review'].label = 'Household 4Ps and relationship review'
                self.fields['four_ps_household_review'].help_text = 'Record the basis for confirming the household information in the member record. No separate ranking upload is required.'
        for code in (() if record_source else methods.criteria(configuration.policy)):
            self.fields['evidence_' + code] = forms.ModelMultipleChoiceField(required=False,
                queryset=DocumentVerification.objects.filter(document__application=application.member.application,
                    document__requirement__document_type_id__in=configuration.policy['evidence_' + code],
                    verified=True, member_version=application.member.version), label=(
                        'SES verified supporting evidence for income and household 4Ps review' if code == 'SES' and methods.is_composite(configuration.policy)
                        else code + ' verified supporting evidence'))
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                    else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')

    def findings(self):
        if methods.is_ses(self.configuration.policy):
            si_findings = {key: self.cleaned_data[key] for key in ('income_consistency', 'income_resolution')}
            if methods.is_composite(self.configuration.policy):
                si_findings.update(household_four_ps={'yes': True, 'no': False}.get(self.cleaned_data['household_four_ps']),
                    **{key: self.cleaned_data[key] for key in ('four_ps_household_confirmed', 'four_ps_household_review')})
        elif si.document_rule(self.configuration.policy):
            si_findings = {'si_documents': {key: {'yes': True, 'no': False}.get(self.cleaned_data['si_' + key])
                for key in ('four_ps', 'indigency')}}
        else:
            si_findings = {'si_domains': {key: self.cleaned_data['si_' + key] for key in ('food', 'housing', 'care')}}
        return {**live_evidence.periods(self.configuration),
            'income_monthly': [self.cleaned_data[f'income_{i}'] for i in range(self.configuration.policy['income_months'])],
            **si_findings,
            **{key: self.cleaned_data[key] for key in ('employment', 'household_members', 'history_complete', 'assessment_finding')}}

    def selections(self):
        if member_record_evidence.enabled(self.configuration.policy):
            return {}
        return {code: list(self.cleaned_data['evidence_' + code].values_list('pk', flat=True))
                for code in methods.criteria(self.configuration.policy)}
