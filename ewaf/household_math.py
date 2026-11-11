"""Five-criterion arithmetic, separate from retained four-criterion calculations.

Uses the existing normalized-column row-average method with n=5 and RI=1.12.
No weights, category encodings, bounds, or directions are assigned here.
"""
from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from .household_criteria import CRITERIA, PAIRS, ENGINE
from .four_criterion_development import CONTEXT, SCALE, text
from .normalization import normalize
VERSION = ENGINE
PROFILE = ENGINE

def ahp(judgments):
    """Normalized-column row averages, with exact Decimal reciprocal construction."""
    if not isinstance(judgments, dict) or set(judgments) != set(PAIRS) or any(
            type(value) is not str or value not in SCALE for value in judgments.values()):
        raise ValidationError('TEN_HOUSEHOLD_CRITERION_COMPARISONS_REQUIRED')
    names = CRITERIA
    with localcontext(CONTEXT):
        matrix = {a: {b: Decimal(1) for b in names} for a in names}
        for pair, value in judgments.items():
            a, b = pair.split(':')
            parts = value.split('/')
            number = Decimal(parts[0]) / Decimal(parts[1]) if len(parts) == 2 else Decimal(value)
            matrix[a][b], matrix[b][a] = number, Decimal(1) / number
        totals = {b: sum(matrix[a][b] for a in names) for b in names}
        normalized = {a: {b: matrix[a][b] / totals[b] for b in names} for a in names}
        weights = {a: sum(normalized[a].values()) / 5 for a in names}
        wsv = {a: sum(matrix[a][b] * weights[b] for b in names) for a in names}
        cv = {a: wsv[a] / weights[a] for a in names}
        lam = sum(cv.values()) / 5
        ci, ri = (lam - 5) / 4, Decimal('1.12')
        cr = ci / ri
        result = {'version': VERSION, 'method': 'normalized-column-row-average', 'criteria': list(names),
            'pairs': dict(judgments), 'matrix': [[text(matrix[a][b]) for b in names] for a in names],
            'column_totals': {b: text(totals[b]) for b in names},
            'normalized_matrix': [[text(normalized[a][b]) for b in names] for a in names],
            'weights': {a: text(weights[a]) for a in names}, 'WSV': {a: text(wsv[a]) for a in names},
            'CV': {a: text(cv[a]) for a in names}, 'lambda_estimate': text(lam), 'CI': text(ci), 'RI': '1.12',
            'CR': text(cr), 'reference_consistency': 'PASSED' if 0 <= cr < Decimal('.10') else 'NOT_PASSED',
            'operational_ready': False, 'configuration_confirmation': 'PENDING'}
        return result

def calculate(*, inputs, definitions, judgments, validation):
    """Five household traces, independently configured weights; shared scalar normalization only."""
    replay = ahp(judgments)
    if replay != validation or replay['reference_consistency'] != 'PASSED':
        raise ValidationError('HOUSEHOLD_WEIGHT_REPLAY_INVALID')
    if set(inputs) != set(CRITERIA) or set(definitions) != set(CRITERIA):
        raise ValidationError('HOUSEHOLD_INPUT_SET_INVALID')
    traces = []
    with localcontext(CONTEXT):
        total = Decimal(0)
        for code in CRITERIA:
            entry, rule = inputs[code], definitions[code]
            if any(entry[key] != rule[key] for key in ('unit', 'source_type')):
                raise ValidationError('HOUSEHOLD_INPUT_UNIT_INVALID')
            raw = entry['value']
            if rule['encoding'] is not None:
                if type(raw) is not str or raw not in rule['encoding']:
                    raise ValidationError('HOUSEHOLD_ENCODING_UNAVAILABLE')
                raw = rule['encoding'][raw]
            normalized = normalize(raw, rule['bounds']['lower'], rule['bounds']['upper'], rule['direction'])
            if not normalized['complete']:
                raise ValidationError(normalized['reasons'])
            weight = Decimal(replay['weights'][code])
            contribution = Decimal(normalized['normalized']) * weight
            total += contribution
            traces.append({**normalized, 'criterion': code, 'weight': text(weight),
                'contribution': text(contribution), 'source_type': entry['source_type'], 'unit': entry['unit']})
        if not 0 <= total <= 1:
            raise ValidationError('HOUSEHOLD_SCORE_RANGE_INVALID')
        return {'engine': ENGINE, 'profile': PROFILE, 'criteria': list(CRITERIA), 'complete': True,
            'traces': traces, 'score_0_1': text(total), 'score_0_100': text(total * 100),
            'operational_ready': False, 'classification': None, 'business_rank': None}
