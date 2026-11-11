from django import forms

from membership.forms import StyledForm
from .models import PDAOApprovalRecord


class PDAOApprovalForm(StyledForm, forms.ModelForm):
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    expected_program_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    manual_confirmation = forms.BooleanField(
        label='I confirm that manual PDAO approval was obtained.',
        help_text='For an official record, I checked the signed/stamped physical letter kept at the Association office. '
                  'For a legacy attestation, the Association attests to prior approval, the letter is missing, '
                  'and replacement approval is being obtained. This is not an official letter record.')

    class Meta:
        model = PDAOApprovalRecord
        fields = ('kind', 'approval_date', 'signatory', 'manual_confirmation', 'reason')
        labels = {'kind': 'Record type', 'signatory': 'PDAO signatory', 'reason': 'Reason / recording context'}
        widgets = {'approval_date': forms.DateInput(attrs={'type': 'date'}),
                   'reason': forms.Textarea(attrs={'rows': 3})}
        help_texts = {
            'approval_date': 'Required for an official record. For a legacy attestation, leave blank if unknown; do not estimate.',
            'signatory': 'Required for an official record. For a legacy attestation, leave blank if unknown; do not invent a name.',
            'reason': 'Explain the entry or correction. For missing letters, record the circumstances. Do not include member information.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['manual_confirmation'].widget.attrs['class'] = 'form-check-input'
