"""Onsite claimant attestations retained with the private release snapshot."""
from django import forms
from django.utils import timezone
from membership.forms import StyledForm


class ClaimantForm(StyledForm, forms.Form):
    claimant_type = forms.ChoiceField(label='Who received the assistance?',
        choices=[('', 'Choose who received it'), ('beneficiary', 'Beneficiary personally'),
                 ('representative', 'Guardian / authorized representative')])
    representative_name = forms.CharField(max_length=200, required=False, label='Representative full name')
    representative_relationship = forms.CharField(max_length=120, required=False, label='Relationship to beneficiary')
    absence_reason = forms.CharField(max_length=1000, required=False,
        label='Why could the beneficiary not attend?', widget=forms.Textarea(attrs={'rows': 2}))
    beneficiary_identity_verified = forms.BooleanField(
        label='I verified the beneficiary’s identity against this record.')
    receipt_confirmed = forms.BooleanField(label='I confirm assistance was actually handed to the named recipient.')

    representative_fields = ('representative_name', 'representative_relationship', 'absence_reason')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        for name in self.representative_fields:
            self.fields[name].widget.attrs['data-representative-input'] = ''
        for field in self.fields.values():
            if isinstance(field, forms.BooleanField):
                field.widget.attrs['class'] = 'form-check-input'

    def clean(self):
        values = super().clean()
        if values.get('claimant_type') == 'representative':
            for name in self.representative_fields:
                if not values.get(name) and name not in self.errors:
                    self.add_error(name, 'Complete this verification before recording a representative’s receipt.')
        else:
            for name in self.representative_fields:
                values[name] = False if isinstance(self.fields[name], forms.BooleanField) else ''
        return values

    def claimant_snapshot(self, *, member, user):
        values = self.cleaned_data
        return {**values, 'schema_version': 3,
                'claimant_name': values['representative_name'] if values['claimant_type'] == 'representative' else member.full_name,
                'beneficiary_id': str(member.pk), 'beneficiary_name': member.full_name,
                'verified_by_id': str(user.pk), 'verified_by_label': user.get_username(),
                'verified_at': timezone.now().isoformat()}
