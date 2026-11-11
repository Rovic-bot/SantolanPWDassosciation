from django import forms
from uuid import UUID

from .forms import StyledForm
from .pdf_registration_forms import PDAOForm

PRIVACY_VERSION = 'pdao-online-20261109-v3'
ONSITE_PRIVACY_VERSION = 'pdao-onsite-20261109-v2'
PRIVACY_NOTICE = (
    'Your details are saved privately for authorized Association staff to review, print and prepare for forwarding to PDAO. '
    'This does not create an Association member record or issue a PWD ID. '
    'Staff arrange forwarding separately; this website does not send your form automatically. '
    'For online applications, staff email the address you provide with an office-verification invitation or a request for corrected information. '
    'After forwarding, staff may also email your provided address when your PWD ID is ready for collection at the barangay office. '
    'Your original submission and processing history are retained. Ask the Help Desk about corrections, retention and privacy requests. '
    'Read the separate PDAO consent statement and sign the printed form before submission to PDAO. '
    'Save your receipt before finishing and protect downloaded copies on shared devices.'
)


class PDAOOnlineForm(PDAOForm):
    placeholder_examples = {
        'pwd_number': 'e.g. 00-0000-000-0000000',
        'last_name': 'e.g. Dela Cruz', 'first_name': 'e.g. Juan',
        'middle_name': 'e.g. Santos', 'suffix': 'e.g. Jr.',
        'house_street': 'e.g. 123 Mabini Street', 'barangay': 'e.g. Santolan',
        'city': 'e.g. Pasig City', 'province': 'Enter province, if applicable',
        'region': 'e.g. NCR', 'landline': 'e.g. 0281234567',
        'contact_number': 'e.g. 09171234567', 'email': 'e.g. juan.delacruz@example.com',
        'occupation_other': 'e.g. Online seller',
        'organization': 'Enter your organization, if any',
        'organization_contact': 'e.g. Maria Santos',
        'organization_address': 'e.g. 123 Mabini Street, Santolan, Pasig City',
        'organization_phone': 'e.g. 0281234567',
        'sss_number': 'Enter number as shown on your SSS record',
        'gsis_number': 'Enter number as shown on your GSIS record',
        'psn_number': 'Enter your PhilSys Number, if available',
        'philhealth_number': 'Enter number as shown on your PhilHealth record',
        'father_last_name': 'e.g. Dela Cruz', 'father_first_name': 'e.g. Jose',
        'father_middle_name': 'e.g. Reyes',
        'mother_last_name': 'e.g. Santos', 'mother_first_name': 'e.g. Maria',
        'mother_middle_name': 'e.g. Garcia',
        'emergency_name': 'e.g. Ana Dela Cruz', 'emergency_relationship': 'e.g. Sister',
        'emergency_phone': 'e.g. 09181234567',
    }
    email = forms.EmailField(label='Email address', help_text='We will email you about office verification, corrections, and PWD ID collection.')
    submission_token = forms.CharField(widget=forms.HiddenInput, max_length=1000)
    acknowledgement = forms.BooleanField(label=(
        'I confirm that my details are correct, have read the privacy information, '
        'and request staff review and preparation of my form for forwarding to PDAO.'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, example in self.placeholder_examples.items():
            self.fields[name].widget.attrs['placeholder'] = example

    def submitted_data(self):
        data = super().submitted_data()
        data.pop('submission_token', None)
        data['intake_channel'] = 'online'
        return data


class PDAOReviewForm(PDAOForm):
    acknowledgement = None
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[('correct', 'Save reviewed details')], widget=forms.HiddenInput)
    groups = tuple((title, tuple(name for name in names if name != 'acknowledgement'))
                   for title, names in PDAOForm.groups)

    def submitted_data(self):
        data = super().submitted_data()
        data.pop('version', None)
        data.pop('action', None)
        return data


class PDAOOnsiteForm(PDAOOnlineForm):
    placeholder_examples = {}
    email = forms.EmailField(label='Email address', required=False,
        help_text='Optional for onsite registration. Used for PWD ID collection notices after forwarding; onsite review actions do not send email.')
    acknowledgement = forms.BooleanField(label=(
        'I confirm that these details were provided during the onsite visit, '
        'the privacy information was explained, and the applicant requested PDAO form preparation.'))

    def submitted_data(self):
        data = super().submitted_data()
        data['intake_channel'] = 'walk_in'
        return data


class PDAOForwardForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[('ready', 'Mark ready to forward'), ('needs_info', 'Needs information'), ('forwarded', 'Record forwarding')],
                               widget=forms.HiddenInput)
    prpwd_lookup_number = forms.CharField(required=False, max_length=100, widget=forms.HiddenInput)
    reason = forms.CharField(label='Information to correct', required=False, max_length=2000,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Explain what the applicant needs to check or correct.'}))
    confirmed = forms.BooleanField(label='I confirm that the information was verified onsite and the signed form and requirements have been forwarded to PDAO.',
                                  required=False)

    def clean(self):
        values = super().clean()
        if values.get('action') == 'forwarded' and not values.get('confirmed'):
            self.add_error('confirmed', 'Confirm the actual forwarding before recording it.')
        if values.get('action') == 'needs_info' and not values.get('reason'):
            self.add_error('reason', 'Explain what the applicant needs to check or correct.')
        return values

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


MAX_CLAIM_BATCH = 25


class PDAOClaimSelectionField(forms.Field):
    widget = forms.MultipleHiddenInput

    def to_python(self, value):
        if not value:
            return {}
        if not isinstance(value, (list, tuple)) or len(value) > MAX_CLAIM_BATCH:
            raise forms.ValidationError(f'Select at most {MAX_CLAIM_BATCH} applications at a time.')
        selections = {}
        for token in value:
            try:
                key, version = token.split(':')
                key, version = UUID(key), int(version)
                if not 0 <= version <= 2147483647 or (key in selections and selections[key] != version):
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise forms.ValidationError('Refresh the forwarded list and select the applications again.') from None
            selections[key] = version
        return selections


class PDAOClaimNoticeForm(StyledForm, forms.Form):
    applications = PDAOClaimSelectionField(error_messages={'required': 'Select at least one forwarded application.'})
    confirmed = forms.BooleanField(label='I confirm that the selected PWD IDs are ready for collection at the Barangay Santolan office.')
    return_to = forms.ChoiceField(choices=[('inbox', 'Inbox'), ('detail', 'Application')], required=False, widget=forms.HiddenInput)
    query = forms.CharField(max_length=200, required=False, widget=forms.HiddenInput)
    page = forms.IntegerField(min_value=1, max_value=1000000, required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
