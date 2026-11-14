from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from documents.validators import validate_document
from .forms import StyledForm, validate_portrait
from .registration_policy import SLOTS
from .registration_profile import ApplicantProfileForm, GROUPS, INPUT_FIELDS, PROFILE_KIND, profile_payload
from .pdf_registration_forms import AssociationPDFForm, ASSOCIATION_PDF_KIND
from .intake_validation import NewIntakeValidationMixin


class AssociationIntakeForm(NewIntakeValidationMixin, AssociationPDFForm):
    pass


def add_registration_document_fields(form, slots):
    """Share the Association upload fields between intake and member updates."""
    for slot in slots:
        form.fields[slot] = forms.FileField(label=f'{SLOTS[slot]} (optional pre-upload)', required=False,
            validators=[validate_document] + ([validate_portrait] if slot == 'photo_2x2' else []),
            help_text='Upload does not replace required onsite presentation.',
            widget=forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png' if slot == 'photo_2x2' else '.pdf,.jpg,.jpeg,.png'}))
    if 'civil_document' in slots:
        form.fields['civil_alternative'] = forms.ChoiceField(label='Civil document uploaded', required=False,
            choices=[('', 'No civil document uploaded'), ('birth', 'Birth Certificate'), ('marriage', 'Marriage Certificate')])


class RegistrationForm(StyledForm, forms.Form):
    full_name = forms.CharField(label='Applicant full name', max_length=200)
    birthdate = forms.DateField(label='Date of birth', widget=forms.DateInput(attrs={'type': 'date'}))
    address = forms.CharField(label='Residence address', max_length=1000, widget=forms.Textarea(attrs={'rows': 3}))
    contact_number = forms.CharField(label='Contact number (optional)', max_length=30, required=False,
        help_text='You may leave this blank and follow up onsite. No text or email notification is sent.')
    acknowledgement = forms.BooleanField(label='I confirm that my details are correct, have read the privacy notice, and submit my application for Admin review and decision.')

    def __init__(self, *args, policy, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = policy
        self.profile_form = None
        self.profile_groups = GROUPS
        self.profile_input_fields = INPUT_FIELDS
        if policy.get('applicant_profile') in (PROFILE_KIND, ASSOCIATION_PDF_KIND):
            profile_class = AssociationPDFForm if policy['applicant_profile'] == ASSOCIATION_PDF_KIND else ApplicantProfileForm
            if profile_class is AssociationPDFForm and getattr(self, 'validate_new_intake', False):
                profile_class = AssociationIntakeForm
            self.profile_form = profile_class(self.data if self.is_bound else None, initial=self.initial)
            if issubclass(profile_class, AssociationPDFForm):
                self.profile_groups = self.profile_form.groups
                self.profile_input_fields = tuple(self.profile_form.fields)
            self.fields.pop('full_name')
            self.fields.pop('address')
            for name in self.profile_input_fields:
                self.fields[name] = self.profile_form.fields[name]
        self.fields['birthdate'].widget.attrs.setdefault('max', timezone.localdate().isoformat())
        add_registration_document_fields(self, policy['upload_slots'])
        self.style_fields()

    def clean_birthdate(self):
        value = self.cleaned_data['birthdate']
        if value > timezone.localdate():
            raise ValidationError('Enter a date of birth that is not in the future.')
        return value

    def clean(self):
        values = super().clean()
        transport = {'csrfmiddlewaretoken', 'context_id', 'version', 'reason', 'action'}
        if set(self.data) - set(self.fields) - transport:
            raise ValidationError('The form contains an unsupported field. Reload and try again.')
        if hasattr(self.data, 'getlist') and any(
                len(self.data.getlist(key)) != 1 for key in self.data
                if not (self.profile_form and key == 'disability_types')):
            raise ValidationError('Submit each form field only once.')
        if self.profile_form:
            if not self.profile_form.is_valid():
                for name, errors in self.profile_form.errors.items():
                    for error in errors:
                        self.add_error(name if name in self.fields else None, error)
            if hasattr(self.data, 'getlist'):
                ids = self.data.getlist('disability_types')
                if len(ids) != len(set(ids)):
                    self.add_error('disability_types', 'Select each classification only once.')
        if any(key not in self.policy['upload_slots'] or len(self.files.getlist(key)) != 1 for key in self.files):
            raise ValidationError('Upload only one file for each permitted document.')
        uploads = [upload for key in self.files for upload in self.files.getlist(key)]
        if (len(uploads) > self.policy['file_count_limit']
                or sum(upload.size for upload in uploads) > self.policy['total_max_bytes']
                or any(upload.size > self.policy['file_max_bytes'] for upload in uploads)):
            raise ValidationError('The uploads exceed the approved limits shown on this form.')
        if bool(values.get('civil_document')) != bool(values.get('civil_alternative')):
            self.add_error('civil_alternative', 'Select Birth or Marriage for the civil document you upload.')
        return values

    def submitted_data(self):
        if self.profile_form:
            payload = (self.profile_form.submitted_data() if isinstance(self.profile_form, AssociationPDFForm)
                       else profile_payload(self.profile_form))
            return payload | {'acknowledgement': self.cleaned_data['acknowledgement']}
        return {'full_name': self.cleaned_data['full_name'], 'birthdate': self.cleaned_data['birthdate'].isoformat(),
                'address': self.cleaned_data['address'], 'contact_number': self.cleaned_data['contact_number'],
                'acknowledgement': self.cleaned_data['acknowledgement']}

    @property
    def profile_sections(self):
        if not self.profile_form:
            return []
        groups = [(title, [self[name] for name in names if name in self.fields]) for title, names in self.profile_groups]
        other = [self[name] for name in self.fields if name not in self.profile_input_fields and not self[name].is_hidden]
        if other:
            groups.append(('Supporting documents and acknowledgement', other))
        return groups


class OnlineRegistrationForm(RegistrationForm):
    """Required contact/identity fields for new online Association submissions."""
    validate_new_intake = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.policy.get('applicant_profile') == ASSOCIATION_PDF_KIND:
            examples = {
                'last_name': 'Dela Cruz', 'first_name': 'Juan', 'middle_name': 'Santos',
                'house_street': '123 Mabini Street', 'barangay': 'Santolan', 'city': 'Pasig City',
                'region': 'NCR', 'zip_code': '1610', 'contact_number': '987 876 5610',
                'email': 'juan.delacruz@example.com', 'nationality': 'Filipino',
                'family_members': '4', 'spouse_name': 'Maria Dela Cruz', 'spouse_contact': '918 123 4567',
                'guardian_name': 'Ana Dela Cruz', 'guardian_contact': '919 123 4567',
                'pwd_number': '00-0000-000-0000000', 'voter_certification_number': '123456789',
                'philhealth_number': '00-000000000-0', 'household_monthly_income': '1000',
                'household_members': '4',
            }
            for name, example in examples.items():
                self.fields[name].widget.attrs['placeholder'] = f'e.g. {example}'
            self.initial.setdefault('household_monthly_income', 1000)
            self.fields['email'].required = True
            self.fields['email'].help_text = (
                'Enter an email address you can access. The Association may email you if your application '
                'needs more information, invite you for office verification, and confirm membership after final approval.')
            self.fields['pwd_number'].required = True
            self.fields['pwd_number'].label = 'PWD No.'
            self.fields['pwd_number'].help_text = (
                'Enter the number on your PWD ID using digits and hyphens. '
                'Bring this ID when you visit the office to verify your information.')


class OnsiteRegistrationForm(RegistrationForm):
    """Require a contact email and PWD number for onsite Association intake."""
    validate_new_intake = True
    prpwd_lookup_number = forms.CharField(required=False, max_length=100, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.policy.get('applicant_profile') == ASSOCIATION_PDF_KIND:
            self.fields['email'].required = True
            self.fields['email'].help_text = (
                'Enter an email address the applicant can access. Program eligibility decisions '
                'are sent here unless a different email is provided in the program application.')
            self.fields['pwd_number'].required = True
            self.fields['pwd_number'].label = 'PWD No.'
            self.fields['pwd_number'].help_text = (
                'Enter the PWD ID number shown on the applicant\'s ID. '
                'Use digits and hyphens; leading zeros are retained.')


class ReviewForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[('begin_review', 'Begin review'), ('request_information', 'Request information'),
        ('ready_for_onsite', 'Record readiness for onsite verification'), ('presented_printout', 'Record presented online printout')])
    reason = forms.CharField(max_length=2000, label='Reason / private review note', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class OnsiteForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, label='Private onsite findings', widget=forms.Textarea(attrs={'rows': 3}))
    keys = {'form': 'Membership Application Form', 'photo': 'One 2×2 picture',
            'civil': 'Birth OR Marriage Certificate', 'voter': "Voter's Certificate", 'envelope': 'Physical long envelope'}
    pdf_keys = {'form': 'Completed Membership Application Form',
        'envelope': 'One long brown envelope', 'pwd_id_copies': 'Four photocopies of PWD ID',
        'voter': "Two photocopies of Voter's Certificate", 'civil': 'Two photocopies of Birth OR Marriage Certificate',
        'photo': 'Four 2×2 pictures with white background'}

    def __init__(self, *args, policy, **kwargs):
        super().__init__(*args, **kwargs)
        if policy.get('applicant_profile') == ASSOCIATION_PDF_KIND:
            self.keys = self.pdf_keys
        for key, label in self.keys.items():
            self.fields[f'finding_{key}'] = forms.ChoiceField(label=label, choices=[('not_reviewed', 'Not reviewed'),
                ('sighted', 'Sighted; not an authenticity or approval finding'), ('missing', 'Missing'),
                ('requires_clarification', 'Requires clarification')])
            self.fields[f'method_{key}'] = forms.ChoiceField(label=f'{label}: approved observation method',
                choices=[(method, method) for method in policy['onsite_methods']])
        self.fields['civil_alternative'] = forms.ChoiceField(label='Civil document presented',
            choices=[('', 'Not presented / unresolved'), ('birth', 'Birth Certificate'), ('marriage', 'Marriage Certificate')], required=False)
        self.style_fields()

    def clean(self):
        values = super().clean()
        if values.get('finding_civil') == 'sighted' and not values.get('civil_alternative'):
            self.add_error('civil_alternative', 'Record the civil document actually presented.')
        return values

    def findings(self):
        return {key: {'finding': self.cleaned_data[f'finding_{key}'], 'method': self.cleaned_data[f'method_{key}']}
                for key in self.keys} | {'civil_alternative': self.cleaned_data['civil_alternative']}
