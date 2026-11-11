"""The guide's five-criterion AHP and min/max method; no operating defaults."""
from decimal import Decimal, InvalidOperation, localcontext
from django.core.exceptions import ValidationError

CRITERIA = ('SI', 'ES', 'PA', 'ND', 'PR')


def number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('EWAF values must be finite numbers.')
    if not result.is_finite():
        raise ValidationError('EWAF values must be finite numbers.')
    return result


def ahp(pairwise):
    if not isinstance(pairwise, list) or len(pairwise) != 5 or any(not isinstance(row, list) or len(row) != 5 for row in pairwise):
        raise ValidationError('Provide a five-by-five pairwise matrix in SI, ES, PA, ND, PR order.')
    with localcontext() as ctx:
        ctx.prec = 40
        matrix = [[number(v) for v in row] for row in pairwise]
        for i in range(5):
            for j in range(5):
                if matrix[i][j] <= 0 or (i == j and matrix[i][j] != 1):
                    raise ValidationError('Pairwise comparisons must be positive with a unit diagonal.')
                if abs(matrix[i][j] * matrix[j][i] - 1) > Decimal('0.00000001'):
                    raise ValidationError('Pairwise comparisons must be reciprocal.')
        totals = [sum(matrix[i][j] for i in range(5)) for j in range(5)]
        weights = [sum(matrix[i][j] / totals[j] for j in range(5)) / 5 for i in range(5)]
        wsv = [sum(matrix[i][j] * weights[j] for j in range(5)) for i in range(5)]
        cv = [wsv[i] / weights[i] for i in range(5)]
        lam = sum(cv) / 5
        ci = (lam - 5) / 4
        cr = ci / Decimal('1.12')
        if cr >= Decimal('0.10'):
            raise ValidationError('Pairwise judgments require review: CR must be strictly below 0.10. Scoring is blocked.')
        return dict(zip(CRITERIA, weights)), {'WSV': list(map(str, wsv)), 'CV': list(map(str, cv)),
            'lambda_max': str(lam), 'CI': str(ci), 'CR': str(cr), 'RI': '1.12'}


def validate_configuration(config):
    weights, consistency = ahp(config.pairwise)
    if config.si_source not in ('monthly_income', 'assessment'):
        raise ValidationError('Choose the approved socioeconomic input source.')
    if not isinstance(config.encodings, dict) or set(config.encodings) != {'ES', 'PR'}:
        raise ValidationError('Provide ES and PR encoding dictionaries using the approved exact category labels.')
    for values in config.encodings.values():
        if not isinstance(values, dict) or not values or any(not key.strip() for key in values):
            raise ValidationError('Each encoding needs at least one named category.')
        for value in values.values():
            number(value)
    if not isinstance(config.bounds, dict) or set(config.bounds) != set(CRITERIA):
        raise ValidationError('Provide bounds for SI, ES, PA, ND and PR.')
    for criterion in CRITERIA:
        item = config.bounds[criterion]
        if not isinstance(item, dict) or set(item) != {'min', 'max', 'direction'}:
            raise ValidationError('Each bound requires min, max and direction (benefit or inverse).')
        if number(item['max']) <= number(item['min']):
            raise ValidationError('Maximum must exceed minimum; equal bounds cannot be used for scoring.')
        expected = {'PA': 'inverse', 'ND': 'benefit', 'PR': 'benefit'}
        if config.si_source == 'monthly_income':
            expected['SI'] = 'inverse'
        if item['direction'] not in ('benefit', 'inverse') or (criterion in expected and item['direction'] != expected[criterion]):
            raise ValidationError(f'{criterion}: use the guide-required normalization direction.')
    if not isinstance(config.thresholds, list) or not config.thresholds:
        raise ValidationError('Provide approved classification thresholds; none are preconfigured.')
    floors = []
    for item in config.thresholds:
        if not isinstance(item, dict) or set(item) != {'minimum', 'label'} or not isinstance(item['label'], str) or not item['label'].strip() or len(item['label']) > 120:
            raise ValidationError('Each threshold requires a minimum percentage and label (up to 120 characters).')
        floor = number(item['minimum'])
        if not 0 <= floor <= 100:
            raise ValidationError('Threshold percentages must be between 0 and 100.')
        floors.append(floor)
    if len(set(floors)) != len(floors) or min(floors) != 0:
        raise ValidationError('Threshold minima must be unique and include zero to cover every score.')
    return weights, consistency


def calculate(config, raw):
    with localcontext() as ctx:
        ctx.prec = 40
        weights, consistency = validate_configuration(config)
        encoded, normalized = {}, {}
        for criterion in CRITERIA:
            value = raw[criterion]
            if criterion in ('ES', 'PR'):
                if value not in config.encodings[criterion]:
                    raise ValidationError(f'{criterion}: the input has no approved encoding. Update the assessment or configuration.')
                value = config.encodings[criterion][value]
            value = number(value)
            bound = config.bounds[criterion]
            lower, upper = number(bound['min']), number(bound['max'])
            if not lower <= value <= upper:
                raise ValidationError(f'{criterion}: input is outside configured bounds. Review it; no clipping is applied.')
            encoded[criterion] = value
            normalized[criterion] = ((upper - value) if bound['direction'] == 'inverse' else (value - lower)) / (upper - lower)
        score = sum(normalized[k] * weights[k] for k in CRITERIA).quantize(Decimal('0.00000000000000000001'))
        bands = sorted(config.thresholds, key=lambda item: number(item['minimum']))
        label = next(item['label'] for item in reversed(bands) if score * 100 >= number(item['minimum']))
        return {'score': score, 'classification': label, 'encoded': {k: str(v) for k, v in encoded.items()},
                'normalized': {k: str(v) for k, v in normalized.items()},
                'weights': {k: str(v) for k, v in weights.items()}, 'consistency': consistency}
