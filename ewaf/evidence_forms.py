from django import forms
from .models import CriterionAssessment
from .evidence import SOURCE_TYPES


class ConfirmedForm(forms.Form):
    expected_context = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Review explanation', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Describe the finding and source references. Do not copy identification details or document contents.')
    confirmed = forms.BooleanField(label='I confirm that this records a review finding and does not authorize EWAF processing.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                    else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')


class PolicyForm(ConfirmedForm):
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    authority_reference = forms.CharField(max_length=500,
        help_text='Reference the source of these definitions. Recording a reference does not approve the policy.')
    snapshot = forms.JSONField(label='Evidence definitions (JSON)', widget=forms.Textarea(attrs={'rows': 14}),
        help_text='Household criteria: HI (household income), SI (4Ps), ES, PA, HM (household members), plus PR for eligibility. Retained historical policies use SI, ES, PA, ND, PR. Each needs definition and source_types. No scores or weights.')


class AssessmentForm(ConfirmedForm):
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    policy_id = forms.IntegerField(widget=forms.HiddenInput)
    state = forms.ChoiceField(choices=CriterionAssessment.STATES)
    source_type = forms.ChoiceField()
    value = forms.CharField(required=False, max_length=200,
        help_text='Leave blank to use the recorded profile or release count. Assessment/category findings require an explicit value.')
    supporting_review_ids = forms.CharField(required=False,
        label='Supporting document review IDs', help_text='Comma-separated current verification IDs listed below; ownership and freshness are checked.')
    observation_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    observation_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    disputed = forms.BooleanField(required=False, label='This finding is disputed and needs review')
    rubric_findings = forms.JSONField(required=False, label='Relevance item findings (JSON)',
        widget=forms.Textarea(attrs={'rows': 6}),
        help_text='One entry per recorded rubric item: item_id, outcome, explanation and review_ids. Cite evidence; do not copy document contents.')
    rubric_attested = forms.BooleanField(required=False,
        label='I attest that each relevance finding is supported by the cited evidence and rubric authority')

    def __init__(self, *args, criterion, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_type'].choices = [(item, item.replace('_', ' ').capitalize()) for item in SOURCE_TYPES[criterion]]
        if criterion != 'PR':
            del self.fields['rubric_findings']
            del self.fields['rubric_attested']
        if not user.has_perm('ewaf.review_criterionassessment'):
            self.fields['state'].choices = [('DECLARED', 'Declared')]
        elif not user.has_perm('ewaf.declare_criterionassessment'):
            self.fields['state'].choices = [pair for pair in CriterionAssessment.STATES if pair[0] != 'DECLARED']

    def clean_value(self):
        return self.cleaned_data['value'] or None

    def clean_supporting_review_ids(self):
        text = self.cleaned_data['supporting_review_ids'].strip()
        try:
            return [int(part.strip()) for part in text.split(',')] if text else []
        except ValueError:
            raise forms.ValidationError('Use comma-separated integer review IDs.') from None


class ReadinessForm(ConfirmedForm):
    expected_assessments = forms.JSONField(widget=forms.HiddenInput)
