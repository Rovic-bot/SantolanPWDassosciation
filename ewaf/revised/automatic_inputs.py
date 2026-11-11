"""Calculate from current approved Association records, with frozen provenance."""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from ewaf import dataset_methods as methods
from ewaf.evidence import canonical, digest
from .engine import ES
from .math import number, CalculationError

RULE = 'current_member_records_v1'
LABEL = 'Automatically use current approved member records and the Association release ledger'
EMPLOYMENT_RULE = 'explicit-registration-employment-map-v1'


def enabled(policy):
    value = policy.get('choices', {}).get('evidence_rule', {}).get('value', policy.get('evidence_rule'))
    return methods.is_composite(policy) and value == RULE


def validate_mapping(content, *, complete=True):
    rule = content.get('registration_inputs')
    from ewaf.employment_scoring import VERSION, MAPPING
    if isinstance(rule, dict) and rule.get('version') == VERSION:
        if rule != {'version': VERSION, 'employment': MAPPING}:
            raise ValidationError('Retain the confirmed five-category employment mapping and scores.')
        return
    from members.profile import EMPLOYMENT
    if (not isinstance(rule, dict) or set(rule) != {'version', 'employment'}
            or rule['version'] != EMPLOYMENT_RULE or not isinstance(rule['employment'], dict)
            or (complete and not rule['employment']) or not set(rule['employment']) <= {key for key, _ in EMPLOYMENT}
            or any(value not in ES for value in rule['employment'].values())):
        raise ValidationError('Specify the approved mapping from recorded employment statuses to scoring categories.')


def content_for_records(content, employment):
    from .member_record_evidence import content_for_records as base
    result = base(content)
    result['choices'].update({key: {'value': value, 'specified': True} for key, value in {
        'evidence_rule': RULE, 'income_period': 'current_record', 'current_period': 'current_record',
        'four_ps_period': 'current_record', 'pa_history': 'association_ledger'}.items()})
    result['registration_inputs'] = {'version': EMPLOYMENT_RULE, 'employment': deepcopy(employment)}
    for key in ('income_months', 'evidence_max_age_days'):
        result['choices'][key] = {'value': '', 'specified': False}
    validate_mapping(result)
    return result


def member_values(member):
    return canonical({'member': member.pk, 'member_version': member.version,
        'employment_status': member.employment_status, 'household_members': member.household_members,
        'household_monthly_income': member.household_monthly_income,
        'household_four_ps': member.registration_profile.get('four_ps_member')})


def entry(source, configuration):
    """Derive inputs only from the captured record and scoped actual releases."""
    from .live_evidence import periods
    record = source.get('member_record_inputs')
    if (not isinstance(record, dict) or record.get('member') != source['member']
            or record.get('member_version') != source['member_version']):
        raise ValidationError('Reload the current member record before ranking.')
    try:
        income = number(record['household_monthly_income'])
        if income < 0:
            raise CalculationError('negative income')
    except (KeyError, TypeError, ValueError, CalculationError):
        raise ValidationError('Record a valid household monthly income in the member directory.') from None
    household = record.get('household_members')
    if type(household) is not int or not 1 <= household <= 2147483647:
        raise ValidationError('Record the number of household members in the member directory.')
    participation = record.get('household_four_ps')
    if participation not in ('Yes', 'No', 'yes', 'no'):
        raise ValidationError('Record household 4Ps participation as Yes or No in the member directory.')
    validate_mapping(configuration.policy)
    employment = configuration.policy['registration_inputs']['employment'].get(record.get('employment_status'))
    from ewaf.employment_scoring import SCORES, VERSION
    scores = SCORES if configuration.policy['registration_inputs']['version'] == VERSION else ES
    if employment not in scores:
        raise ValidationError('The recorded employment status has no assigned scoring category. Review the member record and employment mapping.')
    period = periods(configuration)
    releases = [row for row in source['pa']['successful']
        if period['history_start'] <= row['released_on'] <= period['history_end']
        and parse_datetime(row['recorded_at']) <= configuration.assessment_cutoff]
    if configuration.policy['pa_scope'] == 'this_program':
        releases = [row for row in releases if row['application_id'] in source['dataset_program_applications']]
    inputs = {
        'ES': {'value': employment, 'source_type': RULE, 'unit': 'category',
               'recorded_value': record['employment_status']},
        'HM': {'value': str(household), 'source_type': RULE, 'unit': 'persons'},
        'SES': {'value': str(income), 'household_four_ps': int(participation.lower() == 'yes'),
                'source_type': RULE, 'unit': 'PHP/month'},
        'PA': {'value': str(len(releases)), 'release_ids': [row['id'] for row in releases],
               'source_type': 'successful_releases', 'unit': 'records'},
    }
    return {'inputs': inputs, 'assessments': {'member_record': {
        'source_type': RULE, 'values': record, 'source_digest': digest(source),
        'configuration_digest': configuration.digest}},
        'pr': {'eligibility_review': source['case'], 'contributes_to_score': False}}


def validate_snapshot(snapshot, configuration):
    sources = {row['application']: row['source'] for row in snapshot.get('manifest', [])}
    for reference, retained in snapshot.get('eligible', {}).items():
        source = sources.get(reference)
        if source is None or retained != entry(source, configuration):
            raise ValidationError('Ranking inputs do not match their retained member-record snapshot.')
