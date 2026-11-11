from django import forms
from .evidence_forms import ConfirmedForm
from .scoring_policy import proposal


class ProposalField(forms.JSONField):
    def prepare_value(self, value):
        return '' if value is None else super().prepare_value(value)


class ScoringPolicyForm(ConfirmedForm):
    configuration_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    validation_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    evidence_policy_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    proposed = ProposalField(label='Scoring-policy proposal (JSON)', widget=forms.Textarea(attrs={'rows': 16}),
        help_text='Exactly criteria SI, ES, PA, ND, PR. Empty criterion objects remain pending. No applicant values or identifying information.')

    def clean_proposed(self):
        return proposal(self.cleaned_data['proposed'])
