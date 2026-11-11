"""Current member editing using the same applicant fields as onsite intake."""
from copy import deepcopy

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Value
from django.db.models.functions import Replace

from documents.validators import validate_upload_total
from membership.registration_forms import add_registration_document_fields
from membership.registration_policy import SLOTS
from membership.pdf_registration_forms import AssociationPDFForm, ASSOCIATION_PDF_KIND
from .models import Member


def member_initial(member):
    source = deepcopy(member.registration_profile)
    current = source if source.get('profile_kind') == ASSOCIATION_PDF_KIND else {}
    for name in ('first_name', 'middle_name', 'last_name', 'birthdate', 'barangay',
                 'contact_number', 'email', 'employment_status',
                 'household_monthly_income', 'household_members'):
        current[name] = getattr(member, name)
    current['pwd_number'] = member.control_number
    current['city'] = member.municipality
    if not current.get('house_street'):
        current['house_street'] = ' '.join(filter(None, (member.house_number, member.street)))
    for target, name in (('gender', 'sex'), ('civil_status', 'civil_status'), ('education', 'education')):
        if not current.get(target) and getattr(member, name):
            current[target] = getattr(member, 'get_' + name + '_display')()
    if not current.get('disability_type'):
        current['disability_type'] = member.disability_information or member.disability_labels
    # Never split an unsplit name/address or derive household/family size from dependents.
    return current


class MemberRegistrationForm(AssociationPDFForm):
    acknowledgement = forms.BooleanField(label='I confirm that the updated details are correct, have read the privacy notice, and request this member record update.')
    member_profile_format = forms.ChoiceField(
        choices=[(ASSOCIATION_PDF_KIND, ASSOCIATION_PDF_KIND)], widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(label='Reason for this update', max_length=2000,
                           widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, data=None, files=None, *, instance):
        self.instance = instance
        initial = member_initial(instance) | {
            'member_profile_format': ASSOCIATION_PDF_KIND, 'version': instance.version,
            'acknowledgement': False}
        super().__init__(data, files, initial=initial)
        self.fields['pwd_number'].required = True
        self.fields['pwd_number'].label = 'PWD No.'
        self.fields['pwd_number'].help_text = (
            "Enter the PWD ID number shown on the applicant's ID. "
            'Use digits and hyphens; leading zeros are retained.')
        # Older stored labels remain selectable without inventing a new classification.
        for name, field in self.fields.items():
            recorded = initial.get(name)
            if isinstance(field, forms.ChoiceField) and recorded and recorded not in dict(field.choices):
                field.choices = [*field.choices, (recorded, recorded)]
        add_registration_document_fields(self, SLOTS)
        for slot in SLOTS:
            self.fields[slot].help_text = 'Leave blank to keep the current file. A new upload keeps the earlier file in history.'
        self.privacy_notice = getattr(settings, 'ASSOCIATION_REGISTRATION_POLICY', {}).get('privacy_notice', '')
        self.style_fields()
        self.retained_information = [
            ('Recorded full name', instance.full_name), ('Recorded full address', instance.address),
            ('Recorded classifications', instance.disability_labels or 'Not recorded'),
            ('Exact individual monthly income', instance.monthly_income),
            ('Recorded number of dependents', instance.dependents),
            ('Recorded employment description', instance.employment_information),
        ]

    def clean_pwd_number(self):
        number = self.cleaned_data['pwd_number']
        duplicates = Member.objects.exclude(pk=self.instance.pk).annotate(
            number_digits=Replace('control_number', Value('-'), Value('')))
        if duplicates.filter(number_digits=number.replace('-', '')).exists():
            raise ValidationError('A member with this PWD number already exists.')
        return number

    def clean(self):
        values = super().clean()
        if set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise ValidationError('The form contains an unsupported field. Reload and try again.')
        if hasattr(self.data, 'getlist') and any(len(self.data.getlist(key)) != 1 for key in self.data):
            raise ValidationError('Submit each form field only once.')
        suffix = self.instance.suffix_other if self.instance.suffix == 'other' else self.instance.suffix
        name = ' '.join(filter(None, [values.get('first_name'), values.get('middle_name'), values.get('last_name'), suffix]))
        if len(name) > 200:
            self.add_error('last_name', 'The combined name must be at most 200 characters.')
        validate_upload_total(self.files)
        if any(name not in SLOTS or len(self.files.getlist(name)) != 1 for name in self.files):
            raise ValidationError('Upload only one file for each permitted document.')
        if bool(values.get('civil_document')) != bool(values.get('civil_alternative')):
            self.add_error('civil_alternative', 'Select Birth or Marriage for the civil document you upload.')
        return values

    @property
    def document_fields(self):
        return [self[slot] for slot in SLOTS]

    @property
    def profile_sections(self):
        return super().profile_sections + [('Supporting documents and acknowledgement',
            [self['acknowledgement'], *self.document_fields, self['civil_alternative']])]

    def apply_to_member(self):
        """Update the current profile; the original application and its revisions stay intact."""
        from membership.registration_decisions import member_values
        fields = set(AssociationPDFForm.base_fields)
        payload = super().submitted_data()
        # Audit metadata and uploads are not applicant declarations.
        payload = {key: value for key, value in payload.items()
                   if key in fields or key in ('age', 'full_name', 'address', 'profile_sections',
                                               'digital_sections', 'profile_kind', 'source_form')}
        changed = fields.intersection(self.changed_data)
        if changed:
            name_changed = bool(changed.intersection(('first_name', 'middle_name', 'last_name')))
            address_changed = bool(changed.intersection(('house_street', 'barangay', 'city', 'region', 'zip_code')))
            suffix = self.instance.suffix_other if self.instance.suffix == 'other' else self.instance.suffix
            payload['full_name'] = (' '.join(filter(None, (payload['full_name'], suffix)))
                                    if name_changed else self.instance.full_name)
            if not address_changed:
                payload['address'] = self.instance.address
            source = deepcopy(self.instance.registration_profile) | payload
            values, classifications = member_values(source, self.cleaned_data['pwd_number'])
            projections = {name: name for name in ('birthdate', 'first_name', 'middle_name', 'last_name',
                'contact_number', 'email', 'barangay', 'employment_status',
                'household_monthly_income', 'household_members')}
            projections.update(city='municipality', pwd_number='control_number')
            for source_name, model_name in projections.items():
                if source_name in changed:
                    setattr(self.instance, model_name, values[model_name])
            self.instance.registration_profile = source
            if name_changed:
                self.instance.full_name = payload['full_name']
            if 'middle_name' in changed:
                self.instance.no_middle_name = not payload['middle_name']
            if address_changed:
                self.instance.address = payload['address']
            for source_name, model_name in (('gender', 'sex'), ('civil_status', 'civil_status'),
                                            ('education', 'education')):
                if source_name in changed:
                    # Only exact approved labels project to older coded columns.
                    labels = {label: key for key, label in self.instance._meta.get_field(model_name).choices}
                    setattr(self.instance, model_name, labels.get(payload.get(source_name), ''))
            if 'disability_type' in changed:
                self.instance.disability_information = payload['disability_type']
                self.instance.disability_type = None
                return classifications
        # A family/contact edit must not erase an existing multi-classification record.
        return list(self.instance.disability_types.all())


def member_edit_form(data=None, files=None, *, instance):
    if data is None or 'member_profile_format' in data:
        return MemberRegistrationForm(data, files, instance=instance)
    # Preserve valid submissions from older already-open forms and existing service callers.
    from .forms import MemberForm
    return MemberForm(data, files, instance=instance)
