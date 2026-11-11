"""New approval precision; historical AHP implementations remain replayable."""
from decimal import Decimal, ROUND_FLOOR, localcontext
from fractions import Fraction

from django.core.exceptions import ValidationError

from .dataset_methods import SES_CRITERIA
from .four_criterion_development import CONTEXT, SCALE, text
from .household_criteria import pairs_for

PRECISION = 'exact-ahp-50-digit-downward-weights-v1'


def ahp(judgments):
    """Exact column normalization/row means; store each weight once at 50 digits.

    Downward decimal serialization keeps the stored sum within the existing
    one-sided precision contract, without rescaling or changing any old vector.
    Consistency is evaluated on the exact rational matrix and row averages.
    """
    names, n = SES_CRITERIA, len(SES_CRITERIA)
    if (not isinstance(judgments, dict) or set(judgments) != set(pairs_for(names))
            or any(type(value) is not str or value not in SCALE for value in judgments.values())):
        raise ValidationError('Six SES/ES/PA/HM comparisons on the supported Saaty scale are required.')
    matrix = {a: {b: Fraction(1) for b in names} for a in names}
    for pair, value in judgments.items():
        a, b = pair.split(':')
        matrix[a][b] = Fraction(value)
        matrix[b][a] = 1 / matrix[a][b]
    totals = {b: sum(matrix[a][b] for a in names) for b in names}
    normalized = {a: {b: matrix[a][b] / totals[b] for b in names} for a in names}
    weights = {a: sum(normalized[a].values()) / n for a in names}
    wsv = {a: sum(matrix[a][b] * weights[b] for b in names) for a in names}
    cv = {a: wsv[a] / weights[a] for a in names}
    lam = sum(cv.values()) / n
    ci, ri = (lam - n) / (n - 1), Fraction(9, 10)
    cr = ci / ri

    def decimal(value, *, weight=False):
        with localcontext(CONTEXT) as context:
            if weight:
                context.rounding = ROUND_FLOOR
            return text(Decimal(value.numerator) / Decimal(value.denominator))

    return {'version': PRECISION, 'method': 'normalized-column-row-average', 'criteria': list(names),
        'pairs': dict(judgments), 'matrix': [[decimal(matrix[a][b]) for b in names] for a in names],
        'column_totals': {b: decimal(totals[b]) for b in names},
        'normalized_matrix': [[decimal(normalized[a][b]) for b in names] for a in names],
        'weights': {a: decimal(weights[a], weight=True) for a in names},
        'WSV': {a: decimal(wsv[a]) for a in names}, 'CV': {a: decimal(cv[a]) for a in names},
        'lambda_estimate': decimal(lam), 'CI': decimal(ci), 'RI': '0.90', 'CR': decimal(cr),
        'reference_consistency': 'PASSED' if 0 <= cr < Fraction(1, 10) else 'NOT_PASSED',
        'operational_ready': False, 'configuration_confirmation': 'PENDING'}
