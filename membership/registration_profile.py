"""Applicant-declared onsite-form vocabulary, retained only in pending JSON.

No save(), membership writer, accepted evidence or government verification path.
The extended field contract must be explicitly configured before collection.
"""
from django import forms

from members.profile_forms import ProfileFormMixin
from .forms import PROFILE_FIELDS, StyledForm
from .models import MembershipApplication

PROFILE_KIND = 'onsite_applicant_v1'
GROUPS = (
    ('Address information', ('municipality', 'barangay', 'house_number', 'street', 'purok_zone')),
    ('Personal information', ('first_name', 'middle_name', 'no_middle_name', 'last_name', 'suffix',
        'suffix_other', 'sex', 'birthdate', 'civil_status', 'email', 'contact_number')),
    ('Disability information — applicant declaration', ('disability_types', 'disability_cause',
        'disability_visibility', 'disability_information')),
    ('Additional information — applicant declaration', ('education', 'employment_status', 'income_category', 'dependents')),
)
INPUT_FIELDS = tuple(name for title, names in GROUPS for name in names)


class ApplicantProfileForm(ProfileFormMixin, StyledForm, forms.ModelForm):
    onsite = True

    class Meta:
        model = MembershipApplication
        # The legacy mixin needs its derived hidden fields for validation. They
        # are never accepted from the applicant or written to a domain record.
        fields = tuple(name for name in PROFILE_FIELDS if name != 'control_number') + ('disability_types',)
        widgets = {'birthdate': forms.DateInput(attrs={'type': 'date'}),
                   'disability_information': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact_number'].required = False
        self.fields['contact_number'].label = 'Contact number (optional)'
        self.fields['contact_number'].help_text = 'You may follow up onsite. No text or email notification is sent.'
        self.fields['income_category'].help_text += ' This is your declared income category, not household income or a verified assessment.'
        self.style_fields()

    def save(self, *args, **kwargs):
        raise TypeError('Pending profile validation cannot create a MembershipApplication or Member.')


def profile_payload(form):
    values = form.cleaned_data
    payload = {}
    for name in INPUT_FIELDS:
        value = values[name]
        if name == 'disability_types':
            payload[name] = sorted(str(item.pk) for item in value)
        elif name == 'birthdate':
            payload[name] = value.isoformat()
        else:
            payload[name] = value
    payload.update(full_name=values['full_name'], address=values['address'],
                   profile_kind=PROFILE_KIND)
    # Freeze public form labels and applicant-selected labels for historical
    # receipts/review, even if the controlled catalog later changes.
    payload['disability_choices'] = [[str(item.pk), item.name] for item in values['disability_types']]
    sections = []
    for title, names in GROUPS:
        rows = []
        for name in names:
            field, value = form.fields[name], payload[name]
            if name == 'disability_types':
                display = ', '.join(label for key, label in payload['disability_choices'])
            elif name == 'no_middle_name':
                display = 'Yes' if value else 'No'
            elif hasattr(field, 'choices'):
                display = dict(field.choices).get(value, value)
            else:
                display = value
            rows.append([field.label or name.replace('_', ' ').capitalize(),
                         str(display) if display not in ('', None) else 'Not provided'])
        sections.append([title, rows])
    payload['profile_sections'] = sections
    return payload


def readonly_submission(data, policy):
    from .registration_forms import RegistrationForm
    form = RegistrationForm(initial=data, policy=policy, prefix='submitted')
    for name in list(form.fields):
        if isinstance(form.fields[name], forms.FileField) or name == 'civil_alternative':
            del form.fields[name]
    if data.get('profile_kind') == PROFILE_KIND:
        form.fields['disability_types'] = forms.MultipleChoiceField(
            label='Declared disability type', required=False, choices=data['disability_choices'],
            widget=forms.CheckboxSelectMultiple())
    for field in form.fields.values():
        field.disabled = True
    form.style_fields()
    return form
