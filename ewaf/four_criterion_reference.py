"""Fixed G18 amendment reference replay, never an operational configuration engine.

No applicant input, persistence, settings, legacy engine imports or activation.
The President-approved removal of PR does not approve these recalculated values.
"""
from decimal import (Context, Decimal, DivisionByZero, InvalidOperation, Overflow,
                     ROUND_HALF_EVEN, Underflow, localcontext)

REFERENCE_VERSION = 'g18-four-ahp-reference-1'
REFERENCE_CRITERIA = ('SI', 'ES', 'PA', 'ND')
# The six retained judgments from Computation.docx table 2, keyed by name.
REFERENCE_PAIRS = (
    ('SI', 'ES', '2'), ('SI', 'PA', '3'), ('SI', 'ND', '5'),
    ('ES', 'PA', '2'), ('ES', 'ND', '4'), ('PA', 'ND', '3'),
)


def _text(value):
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def calculate_reference():
    """Replay only the fixed proposed four-criterion matrix, with fresh output."""
    context = Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-999, Emax=999,
                      capitals=1, clamp=0,
                      traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])
    with localcontext(context):
        names = REFERENCE_CRITERIA
        matrix = {a: {b: Decimal(1) for b in names} for a in names}
        for a, b, judgment in REFERENCE_PAIRS:
            matrix[a][b] = Decimal(judgment)
            matrix[b][a] = Decimal(1) / Decimal(judgment)
        totals = {b: sum(matrix[a][b] for a in names) for b in names}
        normalized = {a: {b: matrix[a][b] / totals[b] for b in names} for a in names}
        weights = {a: sum(normalized[a].values()) / 4 for a in names}
        wsv = {a: sum(matrix[a][b] * weights[b] for b in names) for a in names}
        cv = {a: wsv[a] / weights[a] for a in names}
        lam = sum(cv.values()) / 4
        ci = (lam - 4) / 3
        ri = Decimal('0.90')
        cr = ci / ri
        return {
            'version': REFERENCE_VERSION, 'purpose': 'PROPOSED_CONFIGURATION_REFERENCE',
            'method': 'normalized-column-row-average', 'criteria': list(names), 'n': 4,
            'settings': {'precision': 50, 'rounding': 'ROUND_HALF_EVEN', 'Emin': -999, 'Emax': 999,
                         'display': 'full_decimal_text_no_additional_quantization'},
            'pairs': {f'{a}:{b}': value for a, b, value in REFERENCE_PAIRS},
            'matrix': [[_text(matrix[a][b]) for b in names] for a in names],
            'column_totals': {b: _text(totals[b]) for b in names},
            'normalized_matrix': [[_text(normalized[a][b]) for b in names] for a in names],
            'weights': {a: _text(weights[a]) for a in names},
            'weight_sum_residual': _text(sum(weights.values()) - 1),
            'WSV': {a: _text(wsv[a]) for a in names}, 'CV': {a: _text(cv[a]) for a in names},
            'lambda_estimate': _text(lam), 'CI': _text(ci), 'RI': '0.90', 'CR': _text(cr),
            'reference_consistency': 'PASSED' if 0 <= cr < Decimal('0.10') else 'NOT_PASSED',
            'configuration_confirmation': 'PENDING',
            'amendment_approval_date': None, 'effective_date': None, 'authorized_program_ids': [],
            'effective_authorization': False, 'operational_ready': False,
        }
