from django import forms
from .forms import ApplicationForm


class ConfirmedApplicationForm(ApplicationForm):
    applicant_name = forms.CharField(max_length=200, label='Name')
    applicant_email = forms.EmailField(max_length=254, label='Email address',
        help_text='Eligibility decisions, administrator remarks and your certificate will be sent here. '
                  'If your member record has no email, this address will be added. '
                  'An email already saved in your member record will stay unchanged.')
    confirm_information = forms.BooleanField(label='I confirm that the application details I provided are accurate to the best of my knowledge.')

    def __init__(self, *args, member=None, **kwargs):
        self.member = member
        super().__init__(*args, member=member, require_calendar_photo=False, **kwargs)
        self.order_fields(['version', 'applicant_name', 'applicant_email', 'confirm_information'])

    def confirmation(self):
        values = {key: self.cleaned_data[key] for key in ('applicant_name', 'applicant_email',
            'confirm_information')}
        # The submission service rebuilds this form with the locked member.
        # Never accept or expose a public POST override of the directory contact.
        return {**values, 'applicant_contact': getattr(self.member, 'contact_number', ''),
                'contact_source': 'member_record', 'information_basis': 'member_record'}
