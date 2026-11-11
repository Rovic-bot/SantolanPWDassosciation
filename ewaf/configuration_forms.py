from django import forms
from .ahp_validation import CRITERIA, PAIRS
from .evidence_forms import ConfirmedForm
from .policy_reference import CRITERION_LABELS


class DraftForm(ConfirmedForm):
    policy_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    input_mode = forms.ChoiceField(choices=[('pairs', 'Ten independent comparisons'), ('matrix', 'Full matrix')])
    matrix = forms.JSONField(required=False, label='Full matrix (optional)', widget=forms.Textarea(attrs={'rows': 5}),
        help_text='For full-matrix entry, provide five rows in SI, ES, PA, ND, PR order. Use decimal strings; no weights are preselected.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for pair in PAIRS:
            a, b = pair.split(':')
            self.fields['pair_' + a + '_' + b] = forms.CharField(required=False, max_length=96,
                label=f'{a} ({CRITERION_LABELS[a]}) compared with {b} ({CRITERION_LABELS[b]})',
                widget=forms.TextInput(attrs={'class': 'form-control'}),
                help_text=f'1 means equal importance; greater than 1 favors {a}; less than 1 favors {b}. '
                    'This compares criterion importance, not whether higher applicant values mean greater need. '
                    'Enter a positive decimal, not a fraction. Blank remains pending; the server calculates the reciprocal.')

    def clean(self):
        values = super().clean()
        mode = values.pop('input_mode', 'pairs')
        matrix = values.pop('matrix', None)
        pairs = {pair: values.pop('pair_' + pair.replace(':', '_'), '') or None for pair in PAIRS}
        values['judgments'] = {'criteria': list(CRITERIA), 'mode': mode, 'values': matrix if mode == 'matrix' else pairs}
        return values


class ValidationForm(ConfirmedForm):
    configuration_id = forms.IntegerField(widget=forms.HiddenInput)


class ReviewForm(ValidationForm):
    validation_id = forms.IntegerField(widget=forms.HiddenInput)
    finding = forms.ChoiceField(choices=[('REVIEWED', 'Review completed'), ('CORRECTIONS_REQUESTED', 'Corrections requested')])
    correction_requests = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))


class AuthorityEvidenceForm(ValidationForm):
    validation_id = forms.IntegerField(widget=forms.HiddenInput)
    authority_reference = forms.CharField(max_length=500, label='Documentary authority reference',
        help_text='Record the reference only. Do not copy private documents or identification details.')
    stated_scope = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Describe the scope stated in the document. Recording it does not establish authorization.')
    attested = forms.BooleanField(label='I attest that I reviewed the cited document; this record is non-effective')
