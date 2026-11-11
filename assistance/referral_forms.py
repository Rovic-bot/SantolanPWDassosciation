import re

from django import forms
from django.core.exceptions import ValidationError
from documents.validators import validate_document, validate_upload_total
from membership.forms import StyledForm
from .referral_models import ReferralTicket


class ReferralForm(StyledForm, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class VerificationForm(ReferralForm):
    control_number = forms.CharField(max_length=100, label='Association control number')
    full_name = forms.CharField(max_length=200, label='Registered full name')


class ConversationAccessForm(ReferralForm):
    conversation_reference = forms.CharField(max_length=40, label='Conversation reference',
        help_text='Enter the complete ASR- reference from your receipt or email.',
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'spellcheck': 'false'}))


class ConversationReplyForm(ReferralForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    message = forms.CharField(max_length=4000, label='Your message',
        widget=forms.Textarea(attrs={'rows': 1, 'placeholder': 'Type a message…'}))


class TicketForm(ReferralForm):
    email = forms.EmailField(label='Email address',
        help_text='Enter any valid email address you can access for this request. It does not need to match your membership record. Acknowledgments and updates will be sent here.')
    subject = forms.CharField(max_length=200, label='Subject',
        help_text='Give your request a short title, such as Help with medical requirements.')
    assistance_type = forms.ChoiceField(label='Type of assistance needed', choices=[('', 'Choose a type'), *ReferralTicket.Kind.choices])
    concern = forms.CharField(max_length=6000, label='Concern', widget=forms.Textarea(attrs={'rows': 6}))
    evidence_1 = forms.FileField(required=False, label='Supporting evidence', validators=[validate_document])
    acknowledgement = forms.BooleanField(label='I confirm that these details are accurate, I can access the email address above, and I understand the privacy information and that submission does not guarantee assistance, referral approval, or selection.')

    def __init__(self, *args, member, **kwargs):
        kwargs['initial'] = {**kwargs.get('initial', {}), 'email': ''}
        super().__init__(*args, **kwargs)
        self.fields['evidence_1'].widget.attrs['accept'] = '.pdf,.jpg,.jpeg,.png'
        self.fields['evidence_1'].help_text = 'One PDF, JPG or PNG file. You may instead provide evidence later by email or onsite.'

    def clean(self):
        values = super().clean()
        allowed = set(self.fields) | {'csrfmiddlewaretoken'}
        if set(self.data) - allowed or set(self.files) - {'evidence_1'}:
            raise ValidationError('Use only the fields provided in this form.')
        if hasattr(self.data, 'getlist') and any(len(self.data.getlist(key)) != 1 for key in self.data):
            raise ValidationError('Submit one value for each field.')
        if any(len(self.files.getlist(key)) != 1 for key in self.files):
            raise ValidationError('Upload one file per evidence field.')
        validate_upload_total(self.files)
        return values

    def clean_subject(self):
        value = self.cleaned_data['subject']
        if '\r' in value or '\n' in value:
            raise ValidationError('Enter the subject on one line.')
        return value


class NewConcernForm(VerificationForm):
    email = forms.EmailField(label='Email address')
    subject = forms.CharField(max_length=200, label='Subject')
    assistance_type = forms.ChoiceField(label='Type of assistance needed',
        choices=[('', 'Choose a type'), *ReferralTicket.Kind.choices])
    concern = forms.CharField(max_length=6000, label='Concern',
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your concern or the help you need.'}))
    request_key = forms.CharField(widget=forms.HiddenInput)

    def clean_subject(self):
        return TicketForm.clean_subject(self)

    def clean(self):
        values = super().clean()
        if set(self.data) - (set(self.fields) | {'csrfmiddlewaretoken'}) or self.files:
            raise ValidationError('Use only the fields provided in this form.')
        if hasattr(self.data, 'getlist') and any(len(self.data.getlist(key)) != 1 for key in self.data):
            raise ValidationError('Submit one value for each field.')
        return values


class ReviewForm(ReferralForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    sender_version = forms.IntegerField(min_value=0, required=False, widget=forms.HiddenInput)
    channel = forms.ChoiceField(choices=[('email', 'Association email'),
        ('online', 'Online conversation')], label='Send through')
    member_message = forms.CharField(max_length=4000, label='Reply or instructions for the member', widget=forms.Textarea(attrs={'rows': 4}),
        help_text='Choose Email to email your reply, or Online conversation to send it only to this private conversation.')

    def __init__(self, *args, sender_email='', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['channel'].choices = [('email', f'Email — {sender_email}' if sender_email else 'Association email'),
                                         ('online', 'Online conversation')]

    def clean(self):
        values = super().clean()
        if values.get('channel') == 'email' and values.get('sender_version') is None:
            self.add_error('sender_version', 'Reload this ticket to confirm the Association sender.')
        return values


class QuickActionForm(ReferralForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[
        ('begin_review', 'Open ticket'), ('closed', 'Close ticket'),
        ('record_reply', 'Record Gmail reply'),
    ])

    def clean(self):
        values = super().clean()
        if set(self.data) - {'version', 'action', 'csrfmiddlewaretoken'}:
            raise ValidationError('Use only the ticket actions provided on this page.')
        if hasattr(self.data, 'getlist') and any(len(self.data.getlist(key)) != 1 for key in self.data):
            raise ValidationError('Choose one ticket action at a time.')
        return values


class RetryForm(ReferralForm):
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    confirmed = forms.BooleanField(label='I checked the email status and understand that retrying an unconfirmed attempt may send a duplicate.')


class EmailAddressSettingsForm(ReferralForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    sender_email = forms.EmailField(label='Association Email',
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'spellcheck': 'false'}))


class EmailConnectionSettingsForm(EmailAddressSettingsForm):
    gmail_app_password = forms.CharField(required=False, max_length=64, label='Gmail app password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'spellcheck': 'false'}),
        help_text='Use the 16-character app password for this Gmail account, not your normal password. Leave blank to keep the connection for the same address. A different address needs its own app password.')
    def clean_gmail_app_password(self):
        value = ''.join(self.cleaned_data['gmail_app_password'].split())
        if value and not re.fullmatch(r'[A-Za-z0-9]{16}', value):
            raise ValidationError('Enter the 16-character Google app password. Spaces between groups are allowed.')
        return value


class SettingsForm(EmailConnectionSettingsForm):
    reason = forms.CharField(max_length=2000, label='Reason for this change', widget=forms.Textarea(attrs={'rows': 2}))
