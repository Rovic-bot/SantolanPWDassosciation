"""Read-only projection of the original registration onto the supplied paper form."""
from django.utils import timezone

from membership.pdf_registration_forms import ASSOCIATION_PDF_KIND, AssociationPDFForm


def registration_print_data(application):
    source = application.registration_profile
    fields = [name for title, names in AssociationPDFForm.print_groups for name in names]
    if source.get('profile_kind') == ASSOCIATION_PDF_KIND:
        # Do not expose assessment-only fields or replace the retained age with today's age.
        return {name: source.get(name, '') for name in fields} | {'age': source.get('age', '')}

    # Older onsite records have fewer paper-form fields. Preserve their labels;
    # never infer family size from dependents, ID numbers, or a graduation level.
    data = {name: '' for name in fields}
    for name in ('last_name', 'first_name', 'middle_name', 'barangay', 'contact_number', 'email'):
        data[name] = getattr(application, name)
    data.update(
        house_street=' '.join(filter(None, (application.house_number, application.street))),
        city=application.municipality,
        birthdate=application.birthdate.isoformat(),
        gender=application.get_sex_display(),
        civil_status=application.get_civil_status_display(),
        education=application.get_education_display(),
        disability_type=application.disability_labels or application.disability_information,
    )
    prepared = timezone.localtime(application.submitted_at).date()
    born = application.birthdate
    data['age'] = prepared.year - born.year - ((prepared.month, prepared.day) < (born.month, born.day))
    structured_name = ' '.join(filter(None, (data['first_name'], data['middle_name'], data['last_name'])))
    if application.full_name != structured_name:
        data['name_as_recorded'] = application.full_name
    structured_address = ', '.join(filter(None, (data['house_street'], data['barangay'], data['city'])))
    if application.address != structured_address:
        data['address_as_recorded'] = application.address
    for name in ('civil_status', 'education', 'disability_type'):
        if data[name] and data[name] not in dict(AssociationPDFForm.base_fields[name].choices):
            data[name + '_as_recorded'] = data[name]
            data[name] = ''
    return data
