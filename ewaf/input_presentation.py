"""Private ranking inputs: display registered sources without accepting findings.

Registration values are loaded on every read. Accepted calculation inputs still
come exclusively from the inventory's versioned evidence workflow.
"""
from members.profile import EMPLOYMENT
from .household_criteria import NAMES

CARD_LABELS = {'ES': 'Employment Status', 'HM': 'Household Members',
               'PA': 'Previous Assistance', 'SES': 'Socioeconomic Status'}


def configuration_pending(configuration):
    return (not configuration or configuration.status != 'LOCKED'
            or configuration.policy.get('configuration_scope') == 'weights_and_sources')


def registered_values(member):
    income = member.household_monthly_income
    four_ps = member.registration_profile.get('four_ps_member')
    return [
        {'label': 'Household monthly income', 'value': f'PHP {income:,.2f}' if income is not None else 'Not recorded'},
        {'label': '4Ps member', 'value': four_ps if four_ps not in (None, '') else 'Not recorded'},
        {'label': 'Employment status', 'value': dict(EMPLOYMENT).get(member.employment_status,
            member.employment_status or 'Not recorded')},
        {'label': 'Household members', 'value': member.household_members if member.household_members is not None else 'Not recorded'},
    ]


def registered_scoring_values(application, configuration, source):
    """Show the current registration and scoped ledger, not accepted findings.

    One recorded monthly amount is not a verified multi-month average. Likewise,
    counting recorded receipts makes no assertion about history completeness.
    """
    from django.utils.dateparse import parse_datetime
    from .dataset_methods import is_composite
    from .revised.live_evidence import periods
    if not configuration or not getattr(configuration, 'uses_dataset_scoring', getattr(configuration, 'dataset_policy_id', None)) or not is_composite(configuration.policy):
        return []
    member = application.member
    registered = registered_values(member)
    receipt_count = 'Not recorded'
    if source is not None:
        period = periods(configuration)
        receipts = [row for row in source['pa']['successful']
            if period['history_start'] <= row['released_on'] <= period['history_end']
            and parse_datetime(row['recorded_at']) <= configuration.assessment_cutoff]
        if configuration.policy['pa_scope'] == 'this_program':
            ids = set(source['dataset_program_applications'])
            receipts = [row for row in receipts if row['application_id'] in ids]
        receipt_count = len(receipts)
    return [
        {'code': 'ES', 'label': 'Employment Status', 'value': registered[2]['value'], 'unit': 'category'},
        {'code': 'HM', 'label': 'Household Members', 'value': registered[3]['value'],
         'unit': 'person' if registered[3]['value'] == 1 else 'persons'},
        {'code': 'PA', 'label': 'Assistance Received', 'value': receipt_count,
         'unit': 'recorded release' if receipt_count == 1 else 'recorded releases'},
        {'code': 'SES', 'label': 'Monthly Income', 'value': str(member.household_monthly_income) if member.household_monthly_income is not None else 'Not recorded',
         'unit': 'PHP/month', 'detail': 'Registered monthly income; registered household 4Ps: ' + str(registered[1]['value']),
         'supporting_label': 'Registered monthly income', 'four_ps_label': 'Registered 4Ps',
         'four_ps_value': registered[1]['value']},
    ]


def input_details(application, configuration, accepted, *, can_review, source=None):
    from .revised.automatic_inputs import enabled as automatic
    automatic_source = bool(configuration and automatic(configuration.policy))
    result = {'member_id': application.member_id, 'registered_values': registered_values(application.member),
              'input_review_url': '', 'accepted_values': [], 'registered_scoring_values': [],
              'automatic_inputs': automatic_source}
    if accepted:
        from .dataset_methods import is_composite
        items = accepted['inputs'].items()
        if is_composite(configuration.policy):
            order = {'ES': 0, 'HM': 1, 'PA': 2, 'SES': 3}
            items = sorted(items, key=lambda pair: order.get(pair[0], len(order)))
        for code, item in items:
            unit = item.get('unit', '')
            if str(item['value']) == '1':
                unit = {'persons': 'person', 'records': 'record'}.get(unit, unit)
            row = {'code': code, 'label': CARD_LABELS.get(code, NAMES.get(code, code)),
                   'value': item['value'], 'unit': unit}
            if code == 'SES' and is_composite(configuration.policy):
                labels = {0: 'Recorded No', 1: 'Recorded Yes'} if automatic_source else {0: 'Verified No', 1: 'Verified Yes'}
                finding = labels.get(item.get('household_four_ps'), 'Unresolved')
                row['detail'] = 'Household income (PHP/month); household 4Ps: ' + finding
                row.update(supporting_label='Household income (PHP/month)', four_ps_label='4Ps', four_ps_value=finding)
            result['accepted_values'].append(row)
    else:
        result['registered_scoring_values'] = registered_scoring_values(application, configuration, source)
    if application.status in ('INELIGIBLE', 'CLOSED') or (source and source['status'] == 'INELIGIBLE'):
        result['input_status'] = 'This application is not in the eligible pool.'
        result.update(input_state='excluded', input_badge='Pool excluded', input_icon='close')
    elif configuration_pending(configuration):
        result['input_status'] = 'Registration information loaded. Scoring configuration pending.'
        result.update(input_state='pending', input_badge='Setup needed', input_icon='clock')
    elif accepted:
        result['input_status'] = 'Ready for ranking from member records.' if automatic_source else 'Accepted inputs ready for ranking.'
        result.update(input_state='ready', input_badge='Recorded' if automatic_source else 'Verified', input_icon='check')
    elif application.status != 'ELIGIBLE':
        result['input_status'] = 'Complete application eligibility review first.'
        result.update(input_state='pending', input_badge='Review needed', input_icon='clock')
    else:
        result['input_status'] = 'Scoring inputs need attention before ranking.'
        result.update(input_state='pending', input_badge='Review needed', input_icon='clock')
    return result
