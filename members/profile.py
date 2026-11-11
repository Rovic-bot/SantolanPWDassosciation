"""Onsite capture vocabulary. These identifiers are not EWAF scores."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

SEX = [('male', 'Male'), ('female', 'Female')]
CIVIL_STATUS = [(value, value.title()) for value in ('single', 'married', 'widowed', 'separated', 'divorced')]
SUFFIXES = [('', 'None')] + [(value, value) for value in ('Jr.', 'Sr.', 'II', 'III', 'IV', 'V', 'VI')] + [('other', 'Other')]
EDUCATION = [(value, label) for value, label in (
    ('none', 'No Formal Education'), ('elementary', 'Elementary'), ('high_school', 'High School'),
    ('senior_high', 'Senior High School'), ('vocational', 'Vocational'), ('college', 'College'),
    ('postgraduate', 'Postgraduate'))]
EMPLOYMENT = [('employed', 'Employed'), ('unemployed', 'Unemployed'), ('self_employed', 'Self-employed'), ('student', 'Student'), ('retired', 'Retired')]
INCOME = [('income_0_5000', '₱0 – ₱5,000'), ('income_5000_10000', '₱5,000 – ₱10,000'),
          ('income_10000_15000', '₱10,000 – ₱15,000'), ('income_15000_20000', '₱15,000 – ₱20,000'),
          ('income_20000_25000', '₱20,000 – ₱25,000'), ('income_25000_plus', '₱25,000+')]
CAUSE = [('congenital', 'Congenital / Inborn'), ('acquired', 'Acquired')]
VISIBILITY = [('apparent', 'Apparent'), ('non_apparent', 'Non-apparent')]
STRUCTURED_FIELDS = ('municipality', 'barangay', 'house_number', 'street', 'purok_zone',
    'first_name', 'middle_name', 'no_middle_name', 'last_name', 'suffix', 'suffix_other',
    'sex', 'civil_status', 'disability_cause', 'disability_visibility', 'education',
    'employment_status', 'income_category', 'income_category_label')


def income_category_for(amount):
    """Lower inclusive, upper exclusive; 25,000 belongs only to the final range."""
    try:
        amount = Decimal(str(amount))
    except InvalidOperation:
        raise ValidationError('Use a finite nonnegative income amount.') from None
    if not amount.is_finite() or amount < 0:
        raise ValidationError('Use a finite nonnegative income amount.')
    return INCOME[5 if amount >= 25000 else int(amount // 5000)][0]


def profile_snapshot(record):
    from membership.forms import STORED_PROFILE_FIELDS
    result = {name: str(getattr(record, name)) for name in STORED_PROFILE_FIELDS}
    result['disability_types'] = str(record.disability_ids)
    if hasattr(record, 'application_id'):
        result['supporting_documents'] = str(sorted(str(pk) for pk in record.application.documents.values_list('pk', flat=True)))
        result['member_documents'] = str(sorted(str(pk) for pk in record.document_uploads.values_list('pk', flat=True)))
    return result


def profile_sections(record):
    if record.registration_profile.get('profile_kind') == 'association_pdf_v1':
        source = record.registration_profile
        return [(title, [(label, value) for label, value in rows if value != 'Not provided'])
                for title, rows in source.get('profile_sections', []) + source.get('digital_sections', [])] + [
                    ('Association record', [('Assigned control number', record.control_number)])]
    def rows(*names):
        return [(record._meta.get_field(name).verbose_name.capitalize(),
                 getattr(record, 'get_' + name + '_display', lambda: getattr(record, name))() or 'Not recorded')
                for name in names]
    return [
        ('Address Information', rows('municipality', 'barangay', 'house_number', 'street', 'purok_zone') +
         [('Recorded full address', record.address)]),
        ('Personal Information', rows('first_name') +
         [('Middle name', 'N/A — no middle name' if record.no_middle_name else record.middle_name or 'Not recorded')] +
         rows('last_name') + [('Suffix', record.suffix_other if record.suffix == 'other' else record.suffix or 'None')] +
         rows('sex', 'birthdate', 'civil_status', 'email', 'contact_number', 'control_number')),
        ('Disability Information', [('Disability types', record.disability_labels or 'Needs verification')] +
         rows('disability_cause', 'disability_visibility', 'disability_information')),
        ('Additional Information', rows('education', 'employment_status') +
         [('Recorded employment description', record.employment_information or 'Not recorded'),
          ('Income category', record.income_category_label or 'Not recorded'),
          ('Exact monthly income (separate source)', record.monthly_income if record.monthly_income is not None else 'Not recorded'),
          ('Number of dependents', record.dependents)]),
    ]
