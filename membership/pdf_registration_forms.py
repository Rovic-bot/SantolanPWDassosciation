"""Applicant fields transcribed from the owner-supplied source forms.

PDAO fields also match Pasig_PDAO_PWD_ID_Application_Editable_Google_Docs.docx
(confirmed November 5, 2026). Its section 19 uses the recorded intake channel;
the applicant's online channel remains automatic, as previously authorized.

These are declarations, not verified member attributes or EWAF inputs. Keep
the Association payload versioned so earlier submitted forms remain intact.
"""
from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .forms import StyledForm
from .number_fields import NumberStringField, number_field

ASSOCIATION_PDF_KIND = 'association_pdf_v1'
ASSOCIATION_PDF = 'Santolan_PWD_Membership_Form_A4_Fixed.pdf'
PDAO_PDF = 'PWD ID Application Form (2024-2025) (New And Renewal).pdf'
SOURCE_LINKS = {
    'association': 'https://acrobat.adobe.com/id/urn:aaid:sc:AP:f461d946-18e8-49e6-a301-242e8914d7a3',
    'pdao': 'https://acrobat.adobe.com/id/urn:aaid:sc:AP:04f77e78-5b37-46ca-ac2b-9d9f95215f31',
}


def text_field(label, *, required=False, length=150, help_text=''):
    return forms.CharField(label=label, required=required, max_length=length, help_text=help_text)


def choice_field(label, labels, *, required=False, multiple=False):
    choices = [(label, label) for label in labels]
    if multiple:
        return forms.MultipleChoiceField(label=label, required=required, choices=choices,
                                         widget=forms.CheckboxSelectMultiple())
    return forms.ChoiceField(label=label, required=required, choices=[('', 'Select if applicable')] + choices)


def date_field(label, *, required=False):
    return forms.DateField(label=label, required=required, widget=forms.DateInput(attrs={'type': 'date'}))


def stored_name_suffix(source):
    from members.profile import SUFFIXES
    suffix = source.get('suffix', '')
    if suffix in dict(SUFFIXES) and suffix != 'other':
        return {'suffix': suffix, 'suffix_other': ''}
    return {'suffix': 'other' if suffix else '', 'suffix_other': suffix}


class SourceForm(StyledForm, forms.Form):
    groups = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, NumberStringField):
                field.preserve_recorded_value(self.initial.get(name))
        for name in ('birthdate', 'date_issued', 'date_applied'):
            if name in self.fields:
                self.fields[name].widget.attrs['max'] = timezone.localdate().isoformat()
        self.style_fields()

    @property
    def profile_sections(self):
        return [(title, [self[name] for name in names]) for title, names in self.groups]

    def clean(self):
        values = super().clean()
        for name in ('birthdate', 'date_issued', 'date_applied'):
            if values.get(name) and values[name] > timezone.localdate():
                self.add_error(name, 'Enter a date that is not in the future.')
        combined = ' '.join(values.get(name, '') for name in ('first_name', 'middle_name', 'last_name', 'suffix')).strip()
        if len(combined) > 200:
            self.add_error('last_name', 'The combined name must be at most 200 characters.')
        return values

    def submitted_data(self):
        values = self.cleaned_data
        payload = {name: value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, Decimal) else value
                   for name, value in values.items()}
        today = timezone.localdate()
        born = values.get('birthdate')
        payload['age'] = (today.year - born.year - ((today.month, today.day) < (born.month, born.day))) if born else ''
        payload['full_name'] = ' '.join(filter(None, (values.get(name, '') for name in
                                                    ('first_name', 'middle_name', 'last_name', 'suffix'))))
        payload['address'] = ', '.join(filter(None, (values.get(name, '') for name in
                                                    ('house_street', 'barangay', 'city', 'province', 'region', 'zip_code'))))
        sections = []
        for title, names in self.groups:
            rows = []
            for name in names:
                if name == 'acknowledgement':
                    continue
                value = payload.get(name)
                if isinstance(value, list):
                    value = ', '.join(value)
                rows.append([self.fields[name].label, str(value) if value not in ('', None) else 'Not provided'])
                if name == 'birthdate':
                    rows.append(['Age on preparation date', str(payload['age'])])
            if rows:
                sections.append([title, rows])
        payload['profile_sections'] = sections
        return payload


class AssociationPDFForm(SourceForm):
    last_name = text_field('Last name', required=True, length=100)
    first_name = text_field('First name', required=True, length=100)
    middle_name = text_field('Middle name (if any)', length=100)
    suffix = text_field('Name suffix (if any)', length=20)
    house_street = text_field('House no. and street', required=True, length=255)
    barangay = text_field('Barangay', required=True, length=100)
    city = text_field('City', required=True, length=100)
    region = text_field('Region', length=100)
    zip_code = number_field('ZIP code', length=12)
    contact_number = number_field('Mobile nos.', length=30)
    email = forms.EmailField(label='Email', required=False)
    birthdate = date_field('Date of birth', required=True)
    civil_status = choice_field('Civil status', ['Single', 'Married', 'Widower', 'Separated', 'Co-habitation'])
    nationality = text_field('Nationality', length=100)
    gender = choice_field('Gender', ['Male', 'Female'])
    family_members = forms.IntegerField(label='No. of family members', required=False, min_value=0)
    household_monthly_income = forms.DecimalField(label='Household monthly income (PHP)',
        max_digits=12, decimal_places=2, min_value=0,
        help_text='Enter the household’s total monthly income. Enter 0 if there is no income. Used for staff assessment; excluded from the printed membership form.')
    household_members = forms.IntegerField(label='Number of Household members', min_value=1, max_value=32767,
        help_text='Count everyone in your household, including yourself. Used for staff assessment; excluded from the printed membership form.')
    employment_status = forms.ChoiceField(label='Employment Status',
        choices=[('', 'Select employment status'), ('employed', 'Employed'), ('unemployed', 'Unemployed'),
                 ('self_employed', 'Self-employed'), ('student', 'Student'), ('retired', 'Retired')],
        help_text='Used for staff assessment; excluded from the printed membership form.')
    spouse_name = text_field('Spouse name')
    spouse_contact = number_field('Spouse contact no.', length=30)
    four_ps_member = choice_field("4P’s member", ['Yes', 'No'], required=True)
    guardian_name = text_field('Parent / guardian')
    guardian_contact = number_field('Parent / guardian contact no.', length=30)
    disability_type = choice_field('Type of disability (choose one)', [
        'Physical / Orthopedic', 'Learning and Behavioral', 'Speech', 'Hearing',
        'Psychosocial', 'Intellectual', 'Cancer (R.A. 11215)', 'Mental Disability',
        'Visual Disability', 'Rare Disease (R.A. 10747)'], required=True)
    pwd_number = number_field('Issued PWD ID no. (if already issued)', hyphenated=True,
        help_text='Leave blank if not issued and ask the Help Desk about completing the PWD ID photocopy requirement. An entered number is not verification.')
    voter_certification_number = number_field("VRR / Voter’s Certification no.", hyphenated=True)
    date_issued = date_field('PWD ID date issued (if known)')
    philhealth_number = number_field('PhilHealth ID no. (if any)', hyphenated=True)
    education = choice_field('Educational attainment', [
        'Elementary', 'High School', 'College Graduate', 'College Undergraduate', 'Vocational'])
    print_groups = (
        ('Personal information', ('last_name', 'first_name', 'middle_name', 'suffix', 'birthdate', 'civil_status', 'nationality', 'gender')),
        ('Address and contact information', ('house_street', 'barangay', 'city', 'region', 'zip_code', 'contact_number', 'email')),
        ('Family information', ('family_members', 'spouse_name', 'spouse_contact', 'four_ps_member', 'guardian_name', 'guardian_contact')),
        ('Disability and education', ('disability_type', 'education')),
        ('Existing identification, if applicable', ('pwd_number', 'voter_certification_number', 'date_issued', 'philhealth_number')),
    )
    digital_groups = (('Information for assessment (digital only)',
        ('household_monthly_income', 'household_members', 'employment_status')),)
    groups = print_groups + digital_groups

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('four_ps_member', 'disability_type'):
            self.fields[name].choices = [('', 'Select an answer'), *self.fields[name].choices[1:]]
        # Staff may reopen submissions made when this was a free-text field.
        # Retain that original value without accepting new arbitrary choices.
        recorded_gender = self.initial.get('gender')
        if recorded_gender and recorded_gender not in dict(self.fields['gender'].choices):
            self.fields['gender'].choices = [*self.fields['gender'].choices,
                                            (recorded_gender, recorded_gender)]
        self.fields['household_monthly_income'].widget.attrs.update({
            'step': 'any', 'data-income-step': '500', 'data-income-start': '1000'})

    def submitted_data(self):
        payload = super().submitted_data() | {'profile_kind': ASSOCIATION_PDF_KIND, 'source_form': ASSOCIATION_PDF}
        payload['digital_sections'] = payload['profile_sections'][len(self.print_groups):]
        payload['profile_sections'] = payload['profile_sections'][:len(self.print_groups)]
        return payload


class PDAOForm(SourceForm):
    application_type = choice_field('Application type', ['New applicant', 'Renewal'], required=True)
    date_applied = date_field('Date applied', required=True)
    pwd_number = number_field('PWD number (RR-PPMM-BBB-NNNNNNN), if already issued', hyphenated=True)
    last_name = text_field('Last name', required=True, length=100)
    first_name = text_field('First name', required=True, length=100)
    middle_name = text_field('Middle name (if any)', length=100)
    suffix = text_field('Suffix', length=20)
    disability_types = choice_field('Type of disability (check all that apply)', [
        'Deaf / Hard of Hearing', 'Intellectual Disability', 'Learning Disability', 'Mental Disability',
        'Physical Disability', 'Psychosocial Disability', 'Speech / Language Impairment',
        'Visual Disability', 'Cancer (RA 11215)', 'Rare Disease (RA 10747)'], multiple=True)
    disability_cause = choice_field('Cause of disability', ['Congenital / Inborn', 'Acquired'])
    disability_cause_details = choice_field('Cause details (if applicable)', [
        'Autism', 'ADHD', 'Down Syndrome', 'Chronic Illness', 'Cerebral Palsy', 'Injury'], multiple=True)
    house_street = text_field('House no. and street name', required=True, length=255)
    barangay = text_field('Barangay', required=True, length=100)
    city = text_field('City / municipality', required=True, length=100)
    province = text_field('Province', length=100)
    region = text_field('Region', length=100)
    landline = number_field('Landline', length=30)
    contact_number = number_field('Mobile number', length=30)
    email = forms.EmailField(label='Email address', required=False)
    birthdate = date_field('Date of birth', required=True)
    sex = choice_field('Sex', ['Male', 'Female'])
    civil_status = choice_field('Civil status', ['Single', 'Married', 'Separated', 'Widow/er', 'Cohabitation (Live-in)'])
    education = choice_field('Educational attainment', ['None', 'Kindergarten', 'Elementary',
        'Junior High School', 'Senior High School', 'College', 'Vocational', 'Post Graduate'])
    employment_status = choice_field('Employment status', ['Employed', 'Unemployed', 'Self employed'])
    employment_category = choice_field('Category of employment', ['Government', 'Private'])
    employment_nature = choice_field('Nature of employment', ['Permanent / Regular', 'Casual', 'Seasonal', 'Emergency'])
    occupation = choice_field('Occupation', ['Manager', 'Professional', 'Technician and Associate Professionals',
        'Clerical Support Workers', 'Service and Sales Workers', 'Skilled Agricultural, Forestry and Fishery Workers',
        'Craft and Related Trade Workers', 'Plant and Machine Operators and Assemblers',
        'Elementary Occupations', 'Armed Forces Occupations', 'Other'])
    occupation_other = text_field('Other occupation (specify)')
    blood_type = choice_field('Blood type', ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'])
    organization = text_field('Organization affiliated')
    organization_contact = text_field('Organization contact person')
    organization_address = text_field('Organization office address', length=255)
    organization_phone = number_field('Organization tel. no.', length=30)
    sss_number = number_field('SSS no. (if any)', hyphenated=True)
    gsis_number = number_field('GSIS no. (if any)', hyphenated=True)
    psn_number = number_field('PSN no. (if any)', hyphenated=True)
    philhealth_number = number_field('PhilHealth no. (if any)', hyphenated=True)
    philhealth_membership = choice_field('PhilHealth membership', ['Member', 'Member-dependent'])
    father_last_name = text_field("Father’s family name", length=100)
    father_first_name = text_field("Father’s given name", length=100)
    father_middle_name = text_field("Father’s middle name", length=100)
    mother_last_name = text_field("Mother’s family name", length=100)
    mother_first_name = text_field("Mother’s given name", length=100)
    mother_middle_name = text_field("Mother’s middle name", length=100)
    accomplished_by = choice_field('Accomplished by', ['Applicant', 'Guardian', 'Representative'], required=True)
    emergency_name = text_field('Emergency contact name')
    emergency_relationship = text_field('Emergency contact relationship', length=100)
    emergency_phone = number_field('Emergency contact number', length=30)
    acknowledgement = forms.BooleanField(label='I have read the privacy information and understand that this only prepares a form for printing.')
    groups = (
        ('Application and personal information', ('application_type', 'date_applied', 'pwd_number', 'last_name',
            'first_name', 'middle_name', 'suffix', 'birthdate', 'sex', 'civil_status')),
        ('Disability information', ('disability_types', 'disability_cause', 'disability_cause_details')),
        ('Address and contact information', ('house_street', 'barangay', 'city', 'province', 'region', 'landline', 'contact_number', 'email')),
        ('Education and employment', ('education', 'employment_status', 'employment_category', 'employment_nature', 'occupation', 'occupation_other')),
        ('Blood type and organization', ('blood_type', 'organization', 'organization_contact', 'organization_address', 'organization_phone')),
        ('Existing identification, if applicable', ('sss_number', 'gsis_number', 'psn_number', 'philhealth_number', 'philhealth_membership')),
        ('Family background', ('father_last_name', 'father_first_name', 'father_middle_name', 'mother_last_name', 'mother_first_name', 'mother_middle_name')),
        ('Preparation and emergency contact', ('accomplished_by', 'emergency_name', 'emergency_relationship', 'emergency_phone', 'acknowledgement')),
    )

    def clean(self):
        values = super().clean()
        if self.files or set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise ValidationError('Submit only the listed form fields. No document upload is needed for printing.')
        if hasattr(self.data, 'getlist'):
            for name in self.data:
                items = self.data.getlist(name)
                if isinstance(self.fields.get(name), forms.MultipleChoiceField):
                    if len(items) != len(set(items)):
                        self.add_error(name, 'Select each option only once.')
                elif len(items) != 1:
                    raise ValidationError('Submit each form field only once.')
        if values.get('occupation') == 'Other' and not values.get('occupation_other'):
            self.add_error('occupation_other', 'Specify the other occupation.')
        return values
