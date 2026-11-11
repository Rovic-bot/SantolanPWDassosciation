"""Private applicant information from member records and current reviewed inputs."""
from decimal import Decimal, localcontext
from fractions import Fraction

from django.core.exceptions import ValidationError


def money(value):
    if value is None:
        return 'Not recorded'
    number = Fraction(str(value))
    with localcontext() as context:
        context.prec = 50
        return f'PHP {Decimal(number.numerator) / Decimal(number.denominator):,.2f}'


def applicant_information(application, user):
    if not user.has_perm('members.view_member'):
        return {}
    from members.profile import profile_sections
    from assistance.services import VIEW_PERMISSIONS, previous_assistance_count
    from ewaf.operational_services import VIEW, latest_configuration
    from ewaf.revised import live_services, live_evidence
    member = application.member
    employment = member.get_employment_status_display() or member.employment_information or 'Not recorded'
    income, household = member.household_monthly_income, member.household_members
    declared_four_ps = member.registration_profile.get('four_ps_member')
    four_ps = ('Reported Yes - not yet verified' if declared_four_ps is True else
               'Reported No - not yet verified' if declared_four_ps is False else 'Not yet verified')
    reviewed = None
    review_note = 'Registered information; current review pending.'
    if application.program.ewaf_applicable and user.has_perms(VIEW) and live_services.enabled() and live_services.schema_available():
        try:
            # The review page also serves programs whose approved weights allow
            # intake while scoring rules are pending. Keep registered values
            # visible when no current approved scoring configuration is usable.
            configuration = latest_configuration(application.program)
            if configuration and configuration.uses_dataset_scoring:
                live_services.require_binding(configuration)
                reviewed = live_evidence.accepted(application, configuration, live_evidence.context(application))
        except ValidationError:
            review_note = 'Current information needs review.'
    assistance = 'History review pending'
    assistance_note = ''
    if user.has_perms((*VIEW_PERMISSIONS, 'assistance.view_assistancerelease')):
        count = previous_assistance_count(member)
        assistance_note = f'{count} confirmed release records in the system; history coverage has not been confirmed for this application.'
    employment_note = ''
    if reviewed:
        inputs = reviewed.inputs
        income_input = inputs.get('SES', inputs.get('HI'))
        income, household = income_input['value'], inputs['HM']['value']
        if inputs['ES']['value'] != employment:
            employment_note = 'Registered employment: ' + employment
        employment = inputs['ES']['value']
        participation = income_input.get('household_four_ps')
        if type(participation) is int and participation in (0, 1):
            four_ps = 'Verified Yes' if participation == 1 else 'Verified No'
        assistance = inputs['PA']['value']
        dates = live_evidence.periods(reviewed.configuration)
        assistance_note = f"Confirmed releases from {dates['history_start']} to {dates['history_end']}, recorded by the application assessment cutoff."
        review_note = 'Reviewed information for this application.'
    sections = []
    for title, fields in profile_sections(member):
        # These same registration fields appear with their reviewed values below.
        if title == 'Information for assessment (digital only)':
            continue
        sections.append((title, fields))
    return {'profile_sections': sections, 'household_income': money(income),
        'household_members': household if household is not None else 'Not recorded',
        'household_review_note': review_note,
        'household_information': [
            {'label': 'Monthly household income', 'value': money(income), 'note': ''},
            {'label': 'Number of household members', 'value': household if household is not None else 'Not recorded', 'note': ''},
            {'label': 'Employment status', 'value': employment, 'note': employment_note},
            {'label': 'Household 4Ps participation', 'value': four_ps, 'note': ''},
            {'label': 'Previous assistance received', 'value': assistance, 'note': assistance_note},
        ]}
