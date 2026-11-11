"""Four-criterion SES AHP with the retained 50-digit decimal arithmetic contract."""
from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from .dataset_methods import SES, SES_CRITERIA
from .four_criterion_development import CONTEXT, SCALE, text
from .household_criteria import pairs_for


def ahp(judgments):
    names, n = SES_CRITERIA, 4
    if (not isinstance(judgments, dict) or set(judgments) != set(pairs_for(names))
            or any(type(value) is not str or value not in SCALE for value in judgments.values())):
        raise ValidationError('Six SES/ES/PA/HM comparisons on the supported Saaty scale are required.')
    with localcontext(CONTEXT):
        matrix = {a: {b: Decimal(1) for b in names} for a in names}
        for pair, value in judgments.items():
            a, b = pair.split(':')
            parts = value.split('/')
            number = Decimal(parts[0]) / Decimal(parts[1]) if len(parts) == 2 else Decimal(value)
            matrix[a][b], matrix[b][a] = number, Decimal(1) / number
        totals = {b: sum(matrix[a][b] for a in names) for b in names}
        normalized = {a: {b: matrix[a][b] / totals[b] for b in names} for a in names}
        weights = {a: sum(normalized[a].values()) / n for a in names}
        wsv = {a: sum(matrix[a][b] * weights[b] for b in names) for a in names}
        cv = {a: wsv[a] / weights[a] for a in names}
        lam = sum(cv.values()) / n
        ci, ri = (lam - n) / (n - 1), Decimal('0.90')
        cr = ci / ri
        return {'version': SES, 'method': 'normalized-column-row-average', 'criteria': list(names),
            'pairs': dict(judgments), 'matrix': [[text(matrix[a][b]) for b in names] for a in names],
            'column_totals': {b: text(totals[b]) for b in names},
            'normalized_matrix': [[text(normalized[a][b]) for b in names] for a in names],
            'weights': {a: text(weights[a]) for a in names}, 'WSV': {a: text(wsv[a]) for a in names},
            'CV': {a: text(cv[a]) for a in names}, 'lambda_estimate': text(lam), 'CI': text(ci), 'RI': '0.90',
            'CR': text(cr), 'reference_consistency': 'PASSED' if 0 <= cr < Decimal('.10') else 'NOT_PASSED',
            'operational_ready': False, 'configuration_confirmation': 'PENDING'}
