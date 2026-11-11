"""Public declarations reuse the Association form; PWD identity is immutable."""
from django import forms
from django.core.exceptions import ValidationError

from membership.forms import StyledForm
from membership.pdf_registration_forms import AssociationPDFForm
from .registration_form import MemberRegistrationForm


class UpdateIdentityForm(StyledForm, forms.Form):
    control_number = forms.CharField(label='PWD number', max_length=100)
    full_name = forms.CharField(label='Full name', max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class UpdateCodeForm(StyledForm, forms.Form):
    code = forms.RegexField(r'^\d{6}$', label='Verification code', max_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class PublicMemberUpdateForm(MemberRegistrationForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, data=None, *, instance, request_key):
        super().__init__(data, instance=instance)
        allowed = set(AssociationPDFForm.base_fields) | {'acknowledgement', 'request_key'}
        for name in set(self.fields) - allowed:
            self.fields.pop(name)
        self.initial['request_key'] = request_key
        self.fields['pwd_number'].disabled = True
        self.fields['pwd_number'].help_text = 'Your PWD number identifies your existing record and cannot be changed here.'
        self.fields['acknowledgement'].label = 'I confirm these updated details are correct and request staff review. I understand an office interview or screening is needed before approval.'

    @property
    def profile_sections(self):
        return [(title, [self[name] for name in names]) for title, names in AssociationPDFForm.groups] + [
            ('Confirmation', [self['acknowledgement']])]

    def clean(self):
        values = super().clean()
        if 'pwd_number' in self.data and self.data['pwd_number'] != self.instance.control_number:
            self.add_error('pwd_number', 'The PWD number cannot be changed.')
        if self.files:
            raise ValidationError('Submit information only. Bring supporting documents to your office interview.')
        return values


class UpdateReviewForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    member_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    reason = forms.CharField(label='Review notes', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 3}), required=False,
        help_text='Required when approving information or marking Needs verification.')
    interview_confirmed = forms.BooleanField(required=False,
        label='I confirm the member attended the office interview or screening and the updated information was verified.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['reason'].widget.attrs['placeholder'] = 'For example: Interview completed and supporting information confirmed.'
