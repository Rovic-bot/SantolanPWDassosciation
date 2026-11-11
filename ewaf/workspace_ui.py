"""Private UI projections of saved EWAF inputs. No scoring or decision writes."""
from decimal import Decimal
from fractions import Fraction

from .score_breakdown import display

DECISIONS = (('', 'All decisions'), ('awaiting', 'Awaiting selection'),
             ('selected', 'Selected'), ('not_selected', 'Not selected'),
             ('deferred', 'Deferred for review'), ('received', 'Assistance received'))

LABELS = {'SES': ('Income / SES', 'Income-based SES', 'income'),
          'ES': ('Employment', 'Employment status', 'work'),
          'PA': ('Previous assistance', 'Previous assistance', 'history'),
          'HM': ('Household size', 'Household members', 'home')}


def input_display(code, captured):
    value, unit = str(captured.get('value', '')), captured.get('unit', '')
    if not value:
        return 'Not recorded'
    if unit == 'PHP/month':
        amount = Decimal(display(Fraction(value)))
        formatted = f'{amount:,.0f}' if amount == amount.to_integral_value() else f'{amount:,.2f}'
        return f'₱{formatted} / month'
    if code == 'PA' and captured.get('source_type') == 'successful_releases':
        return value + (' record' if Fraction(value) == 1 else ' records')
    if code == 'HM' and unit == 'persons':
        return value + (' person' if Fraction(value) == 1 else ' people')
    return value


def accepted_information(run, application_id):
    inputs = run.snapshot['eligible'][application_id]['inputs']
    rows = []
    for code, captured in inputs.items():
        if code == 'SES' and captured.get('unit') == 'PHP/month':
            label = 'Household income'
        else:
            label = {'HI': 'Household income', 'ES': 'Employment', 'PA': 'Previous assistance',
                     'HM': 'Household size', 'ND': 'Dependents', 'SI': 'Socioeconomic indicator'}.get(code, code)
        rows.append({'code': code, 'label': label, 'value': input_display(code, captured)})
        if code == 'SES' and 'household_four_ps' in captured:
            rows.append({'code': '4Ps', 'label': 'Household 4Ps',
                         'value': {0: 'Verified No', 1: 'Verified Yes'}.get(captured['household_four_ps'], 'Unresolved')})
    order = {code: index for index, code in enumerate(('SES', '4Ps', 'HI', 'SI', 'ES', 'PA', 'HM', 'ND'))}
    return sorted(rows, key=lambda row: order.get(row['code'], 99))


def decision_state(row, run):
    if row['received']:
        return 'received', 'Assistance received', 'check'
    decision = row['decision']
    awaiting = ('Eligible · Awaiting selection' if row.get('application_status') == 'ELIGIBLE'
                else 'Awaiting selection')
    if not decision or decision.run_id != run.pk:
        return 'awaiting', awaiting, 'clock'
    if decision.outcome == 'DEFERRED' and decision.review.get('selection_action') == 'unselected':
        return 'awaiting', awaiting, 'clock'
    return {'SELECTED': ('selected', 'Selected for assistance', 'check'),
            'NOT_SELECTED': ('not_selected', 'Not selected', 'close'),
            'DEFERRED': ('deferred', 'Deferred for review', 'clock')}[decision.outcome]


def decorate_breakdown(run, rows, member_numbers):
    for row in rows:
        row['member_number'] = member_numbers.get(row['application'], '')
        inputs = run.snapshot['eligible'][row['application']]['inputs']
        for trace in row['display_traces'] + row['legacy_traces']:
            code = trace['code']
            short, label, icon = LABELS.get(code, (trace['name'], trace['name'], 'chart'))
            trace.update(short_name=short, ui_label=label, icon=icon)
            if trace['included']:
                trace['ui_input'] = input_display(code, inputs[code])
                if inputs[code].get('unit') != 'PHP/month' and code not in ('PA', 'HM'):
                    trace['ui_input'] = trace['input_label']
