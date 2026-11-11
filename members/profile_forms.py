from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import DisabilityType
from .profile import INCOME, STRUCTURED_FIELDS


class ProfileFormMixin:
    """Shared onsite capture and compatible editing of unsplit legacy records."""
    onsite = False

    def clean_dependents(self):
        raw = self.data.get('dependents', '')
        if isinstance(raw, bool) or not str(raw).isascii() or not str(raw).isdigit():
            raise ValidationError('Enter a non-negative whole number without decimals.')
        return self.cleaned_data['dependents']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structured = self.onsite or bool(self.instance.first_name) or bool(self.data.get('first_name'))
        retained = self.instance.disability_ids if self.instance.pk else []
        self.fields['disability_selection_present'] = forms.BooleanField(
            required=False, initial=True, widget=forms.HiddenInput())
        self.fields['disability_types'].widget = forms.CheckboxSelectMultiple()
        from .disability_catalog import current_types, retained_types
        self.legacy_disability_types = retained_types(retained)
        self.fields['disability_types'].queryset = current_types() if self.structured else DisabilityType.objects.filter(Q(is_active=True) | Q(pk__in=retained))
        self.fields['disability_types'].label = 'Disability type'
        self.fields['disability_types'].required = self.structured and not self.legacy_disability_types.exists()
        self.initial['disability_types'] = retained
        self.fields['disability_type'].required = False
        self.fields['disability_type'].widget = forms.HiddenInput()
        self.fields['income_category_label'].widget = forms.HiddenInput()
        self.fields['no_middle_name'].label = 'No Middle Name (N/A)'
        self.fields['birthdate'].label = 'Birth Date'
        self.fields['email'].label = 'Email Address (Optional)'
        self.fields['dependents'].label = 'Number of Dependents'
        self.fields['income_category'].label = 'Income'
        self.fields['income_category'].help_text = 'At a boundary, choose the next range: ₱5,000 belongs to ₱5,000–₱10,000.'
        self.fields['employment_status'].help_text = ''
        self.fields['disability_types'].help_text = 'Select all that apply.'
        self.fields['dependents'].help_text = ''
        self.fields['disability_information'].required = False
        for name in ('full_name', 'address', 'employment_information', 'monthly_income'):
            if self.structured:
                self.fields[name].required = False
                self.fields[name].widget = forms.HiddenInput()
        if self.structured:
            for name in ('municipality', 'barangay', 'house_number', 'street', 'purok_zone',
                         'first_name', 'last_name', 'sex', 'civil_status', 'disability_cause',
                         'disability_visibility', 'education', 'employment_status', 'income_category'):
                self.fields[name].required = True

    def clean(self):
        values = super().clean()
        selected = values.get('disability_types')
        retained = self.instance.disability_ids if self.instance.pk else []
        if selected is not None and selected.filter(is_active=False).exclude(pk__in=retained).exists():
            self.add_error('disability_types', 'A selected disability type is inactive. Ask an administrator to review the choices.')
        if self.structured and self.instance.pk and 'disability_types' in values:
            # A current form cannot silently reclassify or erase older labels.
            values['disability_types'] = DisabilityType.objects.filter(pk__in=[
                *values['disability_types'].values_list('pk', flat=True),
                *self.legacy_disability_types.values_list('pk', flat=True)])
        # Partial legacy callers cannot erase new data by omitting added fields.
        if self.instance.pk:
            for name in STRUCTURED_FIELDS:
                if name not in self.data and (
                        name != 'no_middle_name' or 'disability_selection_present' not in self.data):
                    values[name] = getattr(self.instance, name)
            if 'disability_types' not in self.data and not self.structured:
                selected = values.get('disability_type')
                selected_id = selected.pk if selected else None
                # Old callers may submit the unchanged historical FK. It must
                # not erase a newer multi-classification selection.
                ids = ([selected_id] if selected_id else []) if (
                    'disability_type' in self.data and selected_id != self.instance.disability_type_id
                ) else self.instance.disability_ids
                if values.get('disability_selection_present'):
                    # Explicitly clearing a legacy profile retains its prior
                    # classification in the original intake and reasoned audit.
                    # Do not revive that old FK as a current classification.
                    ids = []
                    values['disability_type'] = None
                values['disability_types'] = DisabilityType.objects.filter(
                    pk__in=ids)
        if values.get('no_middle_name'):
            values['middle_name'] = ''
        elif self.structured and not values.get('middle_name'):
            self.add_error('middle_name', 'Enter the middle name or select No Middle Name (N/A).')
        if values.get('suffix') == 'other':
            if not values.get('suffix_other'):
                self.add_error('suffix_other', 'Enter the custom suffix.')
        else:
            values['suffix_other'] = ''
        category = values.get('income_category')
        values['income_category_label'] = dict(INCOME).get(category, '')
        if self.structured:
            suffix = values.get('suffix_other') if values.get('suffix') == 'other' else values.get('suffix')
            values['full_name'] = ' '.join(filter(None, [values.get('first_name'), values.get('middle_name'),
                                                       values.get('last_name'), suffix]))
            values['address'] = ', '.join(filter(None, [
                ' '.join(filter(None, [values.get('house_number'), values.get('street')])),
                values.get('purok_zone'), values.get('barangay'), values.get('municipality')]))
            # Never overwrite retained exact amounts or employment descriptions with a bracket/category.
            values['monthly_income'] = self.instance.monthly_income if self.instance.pk else None
            values['employment_information'] = self.instance.employment_information if self.instance.pk else ''
            values['disability_type'] = self.instance.disability_type if self.instance.pk else None
        if len(values.get('full_name', '')) > 200:
            self.add_error('last_name', 'The combined name must be at most 200 characters.')
        return values

    @property
    def sections(self):
        groups = [
            ('Address Information', ['municipality', 'barangay', 'house_number', 'street', 'purok_zone'] +
             ([] if self.structured else ['address'])),
            ('Personal Information', ([] if self.structured else ['full_name']) +
             ['first_name', 'middle_name', 'no_middle_name', 'last_name', 'suffix', 'suffix_other',
              'sex', 'birthdate', 'civil_status', 'email', 'contact_number', 'control_number']),
            ('Disability Information', ['disability_types', 'disability_cause', 'disability_visibility', 'disability_information']),
            ('Additional Information', ['education', 'employment_status', 'income_category', 'dependents'] +
             ([] if self.structured else ['employment_information', 'monthly_income'])),
        ]
        return [(label, [self[name] for name in names]) for label, names in groups]
