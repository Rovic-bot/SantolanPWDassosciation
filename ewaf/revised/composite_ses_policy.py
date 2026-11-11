"""Composite SES policy content, separate from every retained income-only policy."""
from copy import deepcopy
from ewaf.dataset_methods import COMPOSITE, COMPOSITE_DESCRIPTION
from . import ses_policy
from .composite_ses import FORMULA


def specifications(base):
    result = ses_policy.specifications(base)
    from . import rolling_pool
    from ewaf.shared_calculation_rules import FULL_CONSTANTS, FULL_METHOD
    group, label, options = result['pool_rule']
    result['pool_rule'] = (group, label, {**options, rolling_pool.RULE:
        'During registration, rank the currently eligible applicants from current member records and allow separate Admin selection within available slots. '
        'Freeze observations at calculation time; recalculate as applications change. '
        'After closing, resolve all applications before final calculation and selection.'})
    group, label, options = result['constant_rule']
    result['constant_rule'] = (group, label, {**options, rolling_pool.ZERO_CONSTANTS:
        'Equal-value criteria contribute zero for every applicant. Keep the approved weights; '
        'do not redistribute them. A single-person pool has zero contributions.',
        FULL_CONSTANTS: 'Equal-value criteria receive normalized value 1 for every applicant. '
        'Keep the approved weights and apply the existing SES household 4Ps multiplier. '
        'Use each program\'s saved applicant ranges for varying criteria.'})
    from .member_record_evidence import RULE, LABEL
    from . import automatic_inputs
    group, label, options = result['evidence_rule']
    result['evidence_rule'] = (group, label, {**options, RULE: LABEL, automatic_inputs.RULE: automatic_inputs.LABEL})
    result['ses_measure'] = ('B', 'Income-based SES with a verified 4Ps adjustment',
        {FORMULA['version']: COMPOSITE_DESCRIPTION})
    result['ses_adjustment'] = ('B', 'Internal SES coefficients (separate from editable main weights)',
        {'90_10': 'Fixed candidate: SES = I × (9/10 + (1/10) × P). Verified Yes: I; Verified No: 0.90 × I. No additive bonus or second normalization.'})
    result['four_ps_procedure'] = ('B', 'Approved review of current household 4Ps participation and applicant-household relationship', None)
    result['four_ps_evidence_procedure'] = ('B', 'Permitted evidence/alternatives for Verified Yes, Verified No, unresolved findings and corrections', None)
    result['four_ps_period'] = ('C', 'Household 4Ps observation date', {'cutoff': 'Reviewed current household participation at the bound assessment cutoff; unresolved, expired or disputed findings block acceptance.'})
    result['method_rules'] = ('C', 'Four-criterion composite-SES rules', {'dataset_composite_ses_v1':
        'I=(max_income-H)/(max_income-min_income); SES=I*(0.90+0.10*P). '
        'PA is inverse; ES/HM increasing. Sum exactly four main-weight contributions times 100. '
        'Do not normalize P, composite SES or final scores again. Constant P is valid; constant income stops.',
        rolling_pool.ZERO_METHOD:
        'Use the same four-criterion composite-SES formulas. When a criterion has equal minimum and maximum, '
        'its normalized value and contribution are zero for everyone, including SES for constant income. '
        'Retain exact approved weights without redistribution; use normal formulas for varying criteria.',
        FULL_METHOD: 'Use the same four-criterion composite-SES formulas and each program\'s applicant ranges. '
        'When minimum equals maximum, use normalized value 1 for everyone before the existing SES 4Ps '
        'multiplier. Retain exact approved weights without redistribution.'})
    result['input_domain'] = ('C', 'Accepted numerical domains', {'composite_ses_values':
        'Accepted nonnegative finite average household PHP income and explicit reviewed household 4Ps Yes/No. '
        'Unresolved participation is not No. ES uses the four supported categories; PA is an actual-release count; HM is a positive whole-person count.'})
    result['evidence_SES'] = ('C', 'SES: permitted supporting income and household 4Ps evidence/assessment alternatives', 'documents')
    for key, text in (
            ('income_period', 'Current household monthly income in the approved member record at generation'),
            ('current_period', 'Current approved member record at generation'),
            ('four_ps_period', 'Current household 4Ps Yes/No in the approved member record at generation')):
        group, label, options = result[key]
        result[key] = (group, label, {**options, 'current_record': text})
    group, label, options = result['pa_history']
    result['pa_history'] = (group, label, {**options, 'association_ledger':
        'Count the Association ledger under the bound period and scope, including a recorded count of zero'})
    return result


def initial_content(base):
    result = ses_policy.initial_content(base)
    specs = specifications(base)
    result.update(method=COMPOSITE, ses_definition=COMPOSITE_DESCRIPTION)
    result['choices'] = {key: {'value': '', 'specified': False} for key in specs}
    for key, value in {'ses_measure': FORMULA['version'], 'ses_adjustment': '90_10',
                       'method_rules': 'dataset_composite_ses_v1', 'input_domain': 'composite_ses_values',
                       'constant_rule': 'block'}.items():
        result['choices'][key] = {'value': value, 'specified': True}
    result['proposals'] = {key: next(iter(options.values())) if isinstance(options, dict) else 'Unspecified'
        for key, (_, _, options) in specs.items()}
    for key in ('income_months', 'pa_months', 'income_sources'):
        result['proposals'][key] = ses_policy.initial_content(base)['proposals'][key]
    result['proposals'].update(
        ses_review_procedure='Review dates, circumstances and contradictions. Accepted PHP 100,000 remains PHP 100,000. Unresolved conflicts block acceptance; no automatic fraud finding or income substitution.',
        four_ps_procedure='Specify how authorized reviewers establish current household participation and the applicant’s relationship to that household. No DSWD database access is assumed.',
        four_ps_evidence_procedure='Specify approved evidence and accessible alternatives for both Yes and No. Missing evidence is unresolved; do not invent a certificate of non-membership. The same permitted assessment may substantiate income and participation where authorized.')
    result['decision_groups'] = deepcopy(result['decision_groups'])
    result['decision_groups']['B'] = ('COMPOSITE_SES_FORMULA_AUTHORITY', 'HOUSEHOLD_4PS_REVIEW_AUTHORITY')
    return result
