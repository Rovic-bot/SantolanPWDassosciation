"""Staff editing of the retained applicant contract, without review-note inputs."""
import re

from django import forms
from django.http import QueryDict

from .registration_forms import RegistrationForm
from .pdf_registration_forms import ASSOCIATION_PDF_KIND


class RegistrationEditorForm(RegistrationForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    office_verification_confirmed = forms.BooleanField(required=False,
        label='I confirm that the applicant visited the barangay office and I verified their information in person.')
    prpwd_lookup_number = forms.CharField(required=False, max_length=100, widget=forms.HiddenInput)
    assigned_member_number = forms.CharField(max_length=100, required=False,
        label='Assigned member number', help_text='Required for approval. Enter the assigned Association member/control number.')

    def __init__(self, data=None, *, revision, version, editable=True, files=None, member_number=''):
        # Existing attachments stay private and attached to their source revision.
        # Corrections here change applicant fields, not document acceptance.
        policy = {**revision.policy_snapshot, 'upload_slots': []}
        initial = {**revision.data, 'version': version, 'assigned_member_number': member_number}
        super().__init__(data, files, initial=initial, policy=policy)
        from .office_verification import required
        self.requires_office_verification = required(revision.intake)
        if not self.requires_office_verification:
            self.fields.pop('office_verification_confirmed')
        self.uses_pwd_number = revision.data.get('profile_kind') == ASSOCIATION_PDF_KIND
        self.member_number_field = 'pwd_number' if self.uses_pwd_number else 'assigned_member_number'
        if self.uses_pwd_number:
            # One declaration drives both the reviewed form and new Member.
            # Historical profiles retain their existing identifier contract.
            self.fields.pop('assigned_member_number')
            # Show the requirement before approval while retaining the ability
            # to decline an incomplete online submission without an ID number.
            self.fields['pwd_number'].required = self.data.get('action') != 'decline_registration'
            self.fields['pwd_number'].label = 'PWD No.'
            self.fields['pwd_number'].help_text = (
                'Required for approval. The applicant\'s PWD ID number becomes their member number. '
                'Use digits and hyphens as shown on the ID. Leading zeros are retained.')
            # Retain older incomplete submissions, but do not erase the address
            # supplied on a new online application when approving it.
            if revision.intake.channel == 'online' and revision.data.get('email'):
                self.fields['email'].required = self.data.get('action') != 'decline_registration'
                self.fields['email'].help_text = 'Office-verification instructions and the final membership confirmation are sent separately to this address.'
        self.fields['acknowledgement'].disabled = True
        self.fields['acknowledgement'].required = False
        self.fields['acknowledgement'].widget = forms.HiddenInput()
        if not editable:
            if self.is_bound:
                merged = QueryDict('', mutable=True)
                for name in self.data:
                    merged.setlist(name, self.data.getlist(name) if hasattr(self.data, 'getlist') else [self.data[name]])
                for name in self.fields:
                    if name not in ('version', 'assigned_member_number', 'prpwd_lookup_number', 'office_verification_confirmed'):
                        value = initial.get(name, '')
                        merged.setlist(name, value if isinstance(value, list) else [value if value is not None else ''])
                self.data = merged
                if self.profile_form:
                    self.profile_form = type(self.profile_form)(merged, initial=initial)
            for name, field in self.fields.items():
                if name not in ('version', 'assigned_member_number', 'prpwd_lookup_number', 'office_verification_confirmed'):
                    field.disabled = True

    def clean_assigned_member_number(self):
        value = self.cleaned_data['assigned_member_number'].strip().upper()
        if value.startswith('AMR-'):
            raise forms.ValidationError('Enter the assigned member number, not the AMR registration reference.')
        return value

    def clean(self):
        values = super().clean()
        if self.data.get('action') == 'approve_registration':
            number = values.get(self.member_number_field)
            if not number:
                label = 'PWD No.' if self.uses_pwd_number else 'assigned member number'
                self.add_error(self.member_number_field, f'Enter the {label} to approve this registration.')
            elif self.uses_pwd_number and not re.fullmatch(r'[0-9]+(?:-[0-9]+)*', number):
                self.add_error('pwd_number', 'Enter the PWD No. using digits and hyphens as shown on the ID.')
        if (self.uses_pwd_number and values.get('pwd_number')
                and self.data.get('action') in ('approve_registration', 'decline_registration')
                and values.get('prpwd_lookup_number') != values['pwd_number']):
            self.add_error(None, 'Open PRPWD for this PWD No. and review the result before recording your decision.')
        return values

    @property
    def editor_sections(self):
        if self.profile_form:
            return [(title, [self[name] for name in names if not self[name].is_hidden])
                    for title, names in self.profile_groups]
        return [('Applicant information', [field for field in self.visible_fields()
                                           if field.name not in ('assigned_member_number', 'office_verification_confirmed')])]

    def changed_payload(self, previous):
        payload = self.submitted_data()
        # Reopening a form on a later birthday does not itself correct the
        # submission. Preserve its frozen age/labels when no input changed.
        fields = self.profile_input_fields if self.profile_form else (
            'full_name', 'birthdate', 'address', 'contact_number')
        return payload if any(payload.get(name) != previous.get(name) for name in fields) else previous
