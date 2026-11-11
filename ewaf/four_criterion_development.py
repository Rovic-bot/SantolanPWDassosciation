"""Separate four-criterion mathematics and a fixed fictional demonstrator.

No historical engine import, stored configuration replacement, applicant lookup,
operational policy, selection mutation or result publication is provided here.
"""
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext

from django.core.exceptions import PermissionDenied, ValidationError

from .four_criterion_reference import REFERENCE_CRITERIA, REFERENCE_PAIRS, calculate_reference

VERSION = 'g18-four-development-1'
PAIRS = tuple(f'{a}:{b}' for a, b, _ in REFERENCE_PAIRS)
SCALE = tuple([f'1/{n}' for n in range(9, 1, -1)] + [str(n) for n in range(1, 10)])
CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-999, Emax=999)
PENDING = (
    'Explicit confirmation of the recalculated four-criterion configuration',
    'Scoring definitions, verified measurements and normalization directions/bounds',
    'Previous-assistance measurement, program scope and lookback period',
    'Missing, disputed, equal-bound and out-of-range evidence rules',
    'Need classifications, exact boundaries and tie-handling rules',
    'Authorized approving role, amendment approval date, effective date and program scope',
    'Program-specific functional-need evidence, consent and accessible assessment alternatives',
)


def text(value):
    value = format(value, 'f')
    return value.rstrip('0').rstrip('.') if '.' in value else value


def ahp(judgments=None):
    """Normalized-column row averages, with exact Decimal reciprocal construction."""
    judgments = judgments if judgments is not None else {f'{a}:{b}': value for a, b, value in REFERENCE_PAIRS}
    if not isinstance(judgments, dict) or set(judgments) != set(PAIRS) or any(
            type(value) is not str or value not in SCALE for value in judgments.values()):
        raise ValidationError('SIX_FOUR_CRITERION_COMPARISONS_REQUIRED')
    names = REFERENCE_CRITERIA
    with localcontext(CONTEXT):
        matrix = {a: {b: Decimal(1) for b in names} for a in names}
        for pair, value in judgments.items():
            a, b = pair.split(':')
            parts = value.split('/')
            number = Decimal(parts[0]) / Decimal(parts[1]) if len(parts) == 2 else Decimal(value)
            matrix[a][b], matrix[b][a] = number, Decimal(1) / number
        totals = {b: sum(matrix[a][b] for a in names) for b in names}
        normalized = {a: {b: matrix[a][b] / totals[b] for b in names} for a in names}
        weights = {a: sum(normalized[a].values()) / 4 for a in names}
        wsv = {a: sum(matrix[a][b] * weights[b] for b in names) for a in names}
        cv = {a: wsv[a] / weights[a] for a in names}
        lam = sum(cv.values()) / 4
        ci, ri = (lam - 4) / 3, Decimal('0.90')
        cr = ci / ri
        result = {'version': VERSION, 'method': 'normalized-column-row-average', 'criteria': list(names),
            'pairs': dict(judgments), 'matrix': [[text(matrix[a][b]) for b in names] for a in names],
            'column_totals': {b: text(totals[b]) for b in names},
            'normalized_matrix': [[text(normalized[a][b]) for b in names] for a in names],
            'weights': {a: text(weights[a]) for a in names}, 'WSV': {a: text(wsv[a]) for a in names},
            'CV': {a: text(cv[a]) for a in names}, 'lambda_estimate': text(lam), 'CI': text(ci), 'RI': '0.90',
            'CR': text(cr), 'reference_consistency': 'PASSED' if 0 <= cr < Decimal('.10') else 'NOT_PASSED',
            'operational_ready': False, 'configuration_confirmation': 'PENDING'}
        if judgments == {f'{a}:{b}': value for a, b, value in REFERENCE_PAIRS}:
            reference = calculate_reference()
            if any(result[key] != reference[key] for key in ('matrix', 'weights', 'lambda_estimate', 'CI', 'RI', 'CR')):
                raise ValidationError('FOUR_CRITERION_REFERENCE_REPLAY_MISMATCH')
        return result


def policy_readiness():
    return {'state': 'BLOCKED_POLICY', 'pending': list(PENDING), 'operational_ready': False,
        'pr_scoring_removal': 'APPROVED_FOR_SPECIFICALLY_AUTHORIZED_PROGRAMS',
        'pr_requirement': 'PROGRAM_SPECIFIC_ELIGIBILITY_BEFORE_SCORING',
        'amendment_approval_date': None, 'effective_date': None, 'authorized_programs': []}


def fictional_demonstration(*, judgments=None, pending=False, selected=None):
    from accounts.authority_services import enlisted
    from .evidence import digest
    if not enlisted():
        raise PermissionDenied('Four-criterion examples require the registered disposable session.')
    if type(pending) is not bool or selected not in (None, '', 'DEMO-A', 'DEMO-B'):
        raise ValidationError('FICTIONAL_DEMONSTRATION_INPUT_INVALID')
    calculation = ahp(judgments)
    inventory = [
        {'id': 'DEMO-A', 'eligibility': 'confirmed_eligible', 'functional_need': 'Documented fictional functional need',
         'inputs': {'SI': '8', 'ES': '6', 'PA': '4', 'ND': '2'}},
        {'id': 'DEMO-B', 'eligibility': 'confirmed_eligible', 'functional_need': 'Documented fictional functional need',
         'inputs': {'SI': '4', 'ES': '8', 'PA': '2', 'ND': '6'}},
        {'id': 'DEMO-C', 'eligibility': 'review_pending' if pending else 'confirmed_ineligible',
         'functional_need': 'Unresolved evidence retained for review' if pending else
             'Fictional review confirms the test-only functional-need requirement is not met', 'inputs': None},
    ]
    blockers = (['ELIGIBILITY_REVIEW_PENDING'] if pending else []) + (
        ['AHP_CONSISTENCY_NOT_PASSED'] if calculation['reference_consistency'] != 'PASSED' else [])
    if selected and blockers:
        raise ValidationError('FICTIONAL_SELECTION_REQUIRES_COMPLETE_DEMONSTRATION')
    results = []
    # These arbitrary 0..10 benefit scales are explicitly fictional, never inferred
    # socioeconomic or PA policy. No classification or tie-break is assigned.
    with localcontext(CONTEXT):
        if not blockers:
            for row in inventory:
                if row['eligibility'] != 'confirmed_eligible':
                    continue
                traces = []
                for criterion in REFERENCE_CRITERIA:
                    normalized = Decimal(row['inputs'][criterion]) / Decimal(10)
                    weight = Decimal(calculation['weights'][criterion])
                    traces.append({'criterion': criterion, 'input': row['inputs'][criterion],
                        'lower': '0', 'upper': '10', 'direction': 'benefit', 'normalized': text(normalized),
                        'weight': text(weight), 'contribution': text(normalized * weight)})
                score = sum(Decimal(trace['contribution']) for trace in traces)
                results.append({'id': row['id'], 'score_0_1': text(score), 'score_0_100': text(score * 100),
                    'traces': traces, 'selected_in_demonstration': row['id'] == selected, 'actually_assisted': False})
            for row in results:
                score = Decimal(row['score_0_1'])
                row['higher'] = sum(Decimal(other['score_0_1']) > score for other in results)
                row['equal'] = sum(Decimal(other['score_0_1']) == score for other in results)
                row['business_rank'] = None
    output = {'version': VERSION, 'purpose': 'FICTIONAL_DISPOSABLE_DEMONSTRATION',
        'policy': policy_readiness(), 'ahp': calculation, 'inventory': inventory, 'retained_count': len(inventory),
        'eligible_count': 2, 'results': results, 'blockers': blockers, 'complete_demonstration': not blockers,
        'selected': selected or None, 'selection_effect': 'NONE', 'operational_ready': False,
        'fictional_measurement_rule': 'Arbitrary 0..10 units; benefit direction for all four example criteria only.'}
    output['digest'] = digest(output)
    return output
