"""Presentation helpers for onsite intake; field contracts stay owned by the forms."""
from copy import copy

from django import template

register = template.Library()

SECTION_COPY = (
    ('personal', 'Personal', 'Personal information', 'Use the applicant’s details as they appear on their documents.'),
    ('address', 'Address', 'Address and contact', 'Current residence and contact information.'),
    ('family', 'Family', 'Family information', 'Household, spouse and guardian details, where applicable.'),
    ('disability', 'Disability', 'Disability and education', 'Record the applicant’s declared disability and education.'),
    ('identification', 'Identification', 'Existing identification', 'Enter the required PWD number and other available identification.'),
    ('assessment', 'Assessment', 'Assessment information', 'Household and employment details for staff review.'),
    ('documents', 'Documents', 'Documents and acknowledgement', 'Check the applicable documents and confirm the applicant’s acknowledgement.'),
)


@register.simple_tag
def onsite_sections(form):
    groups = getattr(form, 'profile_sections', None)
    if groups and (getattr(form, 'policy', {}).get('applicant_profile') == 'association_pdf_v1'
                   or 'member_profile_format' in form.fields):
        return [dict(zip(('key', 'short', 'title', 'description'), SECTION_COPY[index]),
                     fields=fields, required=any(field.field.required for field in fields),
                     has_uploads=any(field.field.widget.input_type == 'file' for field in fields
                                    if hasattr(field.field.widget, 'input_type')))
                for index, (_, fields) in enumerate(groups)]
    # The retained historical intake has a different field contract. Keep every
    # visible field, including configured uploads, without inventing new inputs.
    mapping = (
        ('personal', ['full_name', 'first_name', 'middle_name', 'no_middle_name', 'last_name', 'suffix', 'suffix_other', 'sex', 'birthdate', 'civil_status']),
        ('address', ['address', 'municipality', 'barangay', 'house_number', 'street', 'purok_zone', 'contact_number', 'email']),
        ('disability', ['disability_types', 'disability_cause', 'disability_visibility', 'disability_information', 'education']),
        ('identification', ['control_number']),
        ('assessment', ['employment_status', 'income_category', 'dependents', 'employment_information', 'monthly_income']),
    )
    visible = {field.name: field for field in form.visible_fields()}
    result = []
    for key, names in mapping:
        fields = [visible.pop(name) for name in names if name in visible]
        if fields:
            copy = next(row for row in SECTION_COPY if row[0] == key)
            result.append(dict(zip(('key', 'short', 'title', 'description'), copy), fields=fields,
                               required=any(field.field.required for field in fields)))
    copy = SECTION_COPY[-1]
    fields = list(visible.values())
    result.append(dict(zip(('key', 'short', 'title', 'description'), copy), fields=fields,
                       required=any(field.field.required for field in fields),
                       has_uploads=any(getattr(field.field.widget, 'input_type', None) == 'file'
                                       for field in fields)))
    return result


@register.filter
def onsite_widget(field):
    """Add local rendering hints without changing validation or shared widgets."""
    hints = {
        'first_name': 'Enter first name', 'last_name': 'Enter last name',
        'middle_name': 'Enter middle name', 'house_street': 'House number and street',
        'barangay': 'e.g. Santolan', 'city': 'e.g. Pasig City', 'region': 'e.g. NCR',
        'email': 'name@example.com', 'household_monthly_income': '0.00',
    }
    attrs = {}
    if field.help_text == 'Upload does not replace required onsite presentation.':
        # The onsite template omits this shared public-form hint.
        attrs['aria-describedby'] = ' '.join(
            item for item in (field.field.widget.attrs.get('aria-describedby') or field.aria_describedby or '').split()
            if item != f'{field.auto_id}_helptext')
    if field.name in hints:
        attrs['placeholder'] = hints[field.name]
    widget = field.field.widget
    if field.name in ('contact_number', 'spouse_contact', 'guardian_contact'):
        # Input's template renders its type separately from attrs. Use a local
        # widget copy to avoid duplicate type attributes or changing the form.
        widget = copy(widget)
        widget.attrs = widget.attrs.copy()
        widget.input_type = 'tel'
    return field.as_widget(widget=widget, attrs=attrs)
