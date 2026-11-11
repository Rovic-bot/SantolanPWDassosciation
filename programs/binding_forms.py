from django import forms
from membership.forms import StyledForm


class TermsActionForm(StyledForm, forms.Form):
    action = forms.ChoiceField(choices=[('capture', 'Record terms'), ('bind', 'Bind approval')])
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    program_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    digest = forms.CharField(max_length=64, required=False, widget=forms.HiddenInput)
    revision_id = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    approval_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    approval_id = forms.TypedChoiceField(coerce=int, required=False, label='Specific PDAO history entry')
    confirmed = forms.BooleanField(label='I reviewed the displayed terms. When binding, I confirm that the selected manual approval or legacy attestation covers these exact terms.')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}), label='Reason for this review')

    def __init__(self, *args, approvals, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['approval_id'].choices = [('', 'Choose an entry for binding')] + [
            (entry.pk, f'Entry {entry.version}: {entry.get_kind_display()}') for entry in approvals]
        self.style_fields()
        self.fields['confirmed'].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        values = super().clean()
        if values.get('action') == 'bind' and (not values.get('approval_id') or not values.get('revision_id')):
            raise forms.ValidationError('Record the displayed terms, then select a specific approval entry to bind.')
        return values
