import hashlib
import json
import uuid

from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from documents.models import MembershipDocumentRequirement
from documents.validators import validate_document, validate_upload_total
from .models import MembershipApplication
from members.profile import STRUCTURED_FIELDS
from members.profile_forms import ProfileFormMixin


PROFILE_FIELDS = ('full_name', 'birthdate', 'address', 'contact_number', 'email',
                  'control_number', 'disability_information', 'disability_type', 'employment_information',
                  'monthly_income', 'dependents') + STRUCTURED_FIELDS

REGISTRATION_FIELDS = ('household_monthly_income', 'household_members', 'registration_profile')
STORED_PROFILE_FIELDS = PROFILE_FIELDS + REGISTRATION_FIELDS


def requirements_snapshot():
    return [{'id': item.pk, 'label': item.document_type.name, 'required': item.is_active and item.is_required,
             'instructions': item.instructions, **({'capture_key': item.capture_key} if item.capture_key else {})}
            for item in MembershipDocumentRequirement.objects.filter(
                Q(is_active=True) | Q(capture_key__isnull=False)).select_related('document_type')]


def fingerprint(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


class StyledForm:
    def style_fields(self):
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                    else 'profile-checkboxes' if isinstance(field.widget, forms.CheckboxSelectMultiple)
                    else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')


class ApplicationForm(ProfileFormMixin, StyledForm, forms.ModelForm):
    onsite = True
    submission_token = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = MembershipApplication
        fields = PROFILE_FIELDS + ('disability_types',)
        widgets = {'birthdate': forms.DateInput(attrs={'type': 'date'}),
                   'address': forms.Textarea(attrs={'rows': 3}),
                   'disability_information': forms.Textarea(attrs={'rows': 3})}
        labels = {'control_number': 'PWD control number', 'monthly_income': 'Monthly income (PHP)',
                  'dependents': 'Number of dependents'}
        help_texts = {'employment_information': 'Describe your current employment situation. No scoring is applied.',
                      'contact_number': 'Include an area or country code when needed.',
                      'control_number': 'Enter the control number shown on your PWD identification.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot = requirements_snapshot()
        self.initial['submission_token'] = signing.dumps(
            {'key': str(uuid.uuid4()), 'requirements': fingerprint(self.snapshot)}, salt='membership.submit')
        for item in self.snapshot:
            self.fields[f'document_{item["id"]}'] = forms.FileField(
                label=item['label'], required=item['required'], validators=[validate_document],
                help_text=item['instructions'] or 'PDF, JPG, JPEG, or PNG.',
                widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'}))
            if item.get('capture_key') == 'photo_1x1':
                self.fields[f'document_{item["id"]}'].validators.append(validate_portrait)
                self.fields[f'document_{item["id"]}'].widget.attrs['accept'] = '.jpg,.jpeg,.png'
        self.style_fields()
        from members.models import DisabilityType
        self.fields['disability_type'].queryset = DisabilityType.objects.filter(is_active=True)
        self.fields['disability_type'].required = False
        self.fields['disability_type'].help_text = 'Select the verified classification; configure approved disability types first.'
        self.fields['birthdate'].widget.attrs['max'] = timezone.localdate().isoformat()

    def clean_submission_token(self):
        try:
            payload = signing.loads(self.cleaned_data['submission_token'], salt='membership.submit', max_age=86400)
            key = uuid.UUID(payload['key'])
            if payload['requirements'] != fingerprint(self.snapshot):
                raise ValidationError('Document requirements changed. Reload this page before submitting.')
            return key
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise ValidationError('This form expired. Reload the page before submitting.')

    def clean_birthdate(self):
        value = self.cleaned_data['birthdate']
        if value > timezone.localdate():
            raise ValidationError('Birthdate cannot be in the future.')
        return value

    def clean_control_number(self):
        return self.cleaned_data['control_number'].strip().upper()

    def clean(self):
        cleaned = super().clean()
        self.clean_uploads()
        return cleaned

    def clean_uploads(self):
        validate_upload_total(self.files)
        expected = {f'document_{item["id"]}' for item in self.snapshot}
        if any(name not in expected or len(self.files.getlist(name)) != 1 for name in self.files):
            raise ValidationError('Upload only one file per listed document requirement.')

    @property
    def personal_fields(self):
        return [self[name] for name in PROFILE_FIELDS]

    @property
    def document_fields(self):
        return [self[f'document_{item["id"]}'] for item in self.snapshot]


def validate_portrait(upload):
    from PIL import Image, UnidentifiedImageError
    if upload.content_type not in ('image/jpeg', 'image/png'):
        raise ValidationError('Use a JPG or PNG photograph.')
    try:
        image = Image.open(upload)
        if image.width * image.height > 25000000:
            raise ValidationError('The photograph is too large. Use at most 25 million pixels.')
        image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError('Upload a readable JPG or PNG photograph.') from None
    finally:
        upload.seek(0)


class VerificationForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    verified = forms.TypedChoiceField(label='PRPWD verification result',
        choices=[('', 'Select a result'), ('yes', 'Yes — verified'), ('no', 'No — not verified')],
        coerce=lambda value: value == 'yes')
    notes = forms.CharField(max_length=2000, label='Verification notes', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class QuickApprovalForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    verified = forms.BooleanField(label='I checked PRPWD and confirmed this applicant’s information.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['verified'].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        values = super().clean()
        allowed = {'csrfmiddlewaretoken', 'action', 'version', 'verified'}
        if set(self.data) - allowed or (hasattr(self.data, 'getlist') and
                any(len(self.data.getlist(key)) != 1 for key in self.data)):
            raise ValidationError('Submit only the PRPWD confirmation and current application version.')
        return values


class DecisionForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    decision = forms.ChoiceField(choices=[('', 'Select a decision'), ('approved', 'Approve membership'),
                                         ('rejected', 'Reject application')])
    notes = forms.CharField(max_length=2000, label='Decision notes', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
