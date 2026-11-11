"""G14 diagnostic arithmetic only. No applicant scoring or policy authorization."""
import json
import re
from decimal import (Decimal, Context, localcontext, ROUND_HALF_EVEN, DecimalException,
                     InvalidOperation, DivisionByZero, Overflow, Underflow)
from django.core.exceptions import ValidationError

CRITERIA = ('SI', 'ES', 'PA', 'ND', 'PR')
PAIRS = tuple(f'{a}:{b}' for i, a in enumerate(CRITERIA) for b in CRITERIA[i + 1:])
ENGINE = 'g14-ahp-1'
PROFILE = 'workbook-five-reference-1'
METHOD = 'normalized-column-row-average'
SETTINGS = {'precision': 50, 'rounding': 'ROUND_HALF_EVEN', 'emin': -999, 'emax': 999,
            'reciprocity_tolerance': '0.00000001', 'weight_sum_tolerance': '1e-45',
            'numeric_characters': 96, 'significant_digits': 40, 'maximum_absolute_exponent': 40,
            'display_policy': 'full_precision_text_without_display_rounding',
            'negative_ci_policy': 'report_anomaly_without_clamping',
            'traps': ['InvalidOperation', 'DivisionByZero', 'Overflow', 'Underflow']}


def arithmetic_context():
    return Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-999, Emax=999, capitals=1, clamp=0,
                   traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def safe_payload(value):
    """Bound draft storage before parsing numbers; malformed but safe drafts survive."""
    def visit(item, depth=0):
        if depth > 4:
            raise ValidationError('Judgments exceed the supported nesting limit.')
        if isinstance(item, dict):
            if len(item) > 25 or any(not isinstance(k, str) or len(k) > 96 for k in item):
                raise ValidationError('Judgment keys exceed the storage limit.')
            for child in item.values():
                visit(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 25:
                raise ValidationError('Judgments exceed the storage limit.')
            for child in item:
                visit(child, depth + 1)
        elif item is not None and type(item) not in (str, int, bool, float):
            raise ValidationError('Use bounded JSON judgment values.')
        elif isinstance(item, str) and len(item) > 96:
            raise ValidationError('A judgment may contain at most 96 characters.')
    visit(value)
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True)
    except (ValueError, TypeError, OverflowError):
        raise ValidationError('Judgments must be finite, bounded JSON values.') from None
    if len(encoded) > 8192:
        raise ValidationError('Judgments exceed the 8 KiB storage limit.')
    return json.loads(encoded)


def decimal_text(value):
    result = format(value, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def parse_number(value):
    if type(value) not in (str, int):
        raise ValueError('INVALID_NUMBER')
    text = str(value).strip()
    if len(text) > 96:
        raise ValueError('NUMERIC_RESOURCE_LIMIT')
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text):
        raise ValueError('INVALID_NUMBER')
    number = Decimal(text)
    if (not number.is_finite() or len(number.as_tuple().digits) > 40 or
            abs(number.as_tuple().exponent) > 40 or abs(number.adjusted()) > 40):
        raise ValueError('NUMERIC_RESOURCE_LIMIT')
    return number


def reference_verdict(cr):
    """No display rounding or implicit negative-residual adjustment."""
    if not cr.is_finite() or cr < 0:
        return 'NUMERICAL_ANOMALY'
    return 'PASSED' if cr < Decimal('0.10') else 'FAILED'


def validate_ahp(payload):
    result = {'engine': ENGINE, 'profile': PROFILE, 'method': METHOD, 'criteria': list(CRITERIA),
              'settings': dict(SETTINGS), 'reference': {'RI': '1.12', 'CR_limit': '0.10', 'comparison': '<',
                  'authority': 'workbook_reference_not_Association_authorization'},
              'complete': False, 'structurally_valid': False, 'consistency': 'UNAVAILABLE',
              'reasons': [], 'canonical_input': None, 'matrix': None, 'calculation': None,
              'effective_authorization': False, 'operational_ready': False}
    def fail(code, cell=None):
        result['reasons'].append({'code': code, 'cell': cell})
        return result
    try:
        payload = safe_payload(payload)
    except ValidationError:
        return fail('PAYLOAD_RESOURCE_LIMIT')
    if not isinstance(payload, dict) or set(payload) != {'criteria', 'mode', 'values'}:
        return fail('INVALID_STRUCTURE')
    if payload['criteria'] != list(CRITERIA):
        return fail('CRITERION_ORDER_INVALID')
    mode, values = payload['mode'], payload['values']
    if mode == 'pairs':
        if not isinstance(values, dict) or set(values) - set(PAIRS):
            return fail('INVALID_STRUCTURE')
        cells = [(key, values.get(key)) for key in PAIRS]
    elif mode == 'matrix':
        if not isinstance(values, list) or len(values) != 5 or any(not isinstance(row, list) or len(row) != 5 for row in values):
            return fail('INVALID_STRUCTURE')
        cells = [(f'{i}:{j}', values[i][j]) for i in range(5) for j in range(5)]
    else:
        return fail('INVALID_INPUT_MODE')
    parsed = {}
    with localcontext(arithmetic_context()):
        for key, value in cells:
            if value is None or value == '':
                fail('JUDGMENT_MISSING', key)
                continue
            try:
                parsed[key] = parse_number(value)
            except (ValueError, DecimalException) as error:
                fail(str(error) if isinstance(error, ValueError) else 'INVALID_NUMBER', key)
        result['complete'] = not any(row['code'] == 'JUDGMENT_MISSING' for row in result['reasons'])
        if result['reasons']:
            return result
        result['canonical_input'] = {'criteria': list(CRITERIA), 'mode': mode,
            'values': {key: decimal_text(value) for key, value in parsed.items()} if mode == 'pairs' else
                [[decimal_text(parsed[f'{i}:{j}']) for j in range(5)] for i in range(5)]}
        if any(value <= 0 for value in parsed.values()):
            return fail('JUDGMENT_NOT_POSITIVE')
        try:
            if mode == 'pairs':
                matrix = [[Decimal(1) for _ in range(5)] for _ in range(5)]
                for i, a in enumerate(CRITERIA):
                    for j in range(i + 1, 5):
                        matrix[i][j] = parsed[f'{a}:{CRITERIA[j]}']
                        matrix[j][i] = Decimal(1) / matrix[i][j]
            else:
                matrix = [[parsed[f'{i}:{j}'] for j in range(5)] for i in range(5)]
            result['matrix'] = [[decimal_text(value) for value in row] for row in matrix]
            for i in range(5):
                if matrix[i][i] != 1:
                    return fail('DIAGONAL_NOT_ONE', f'{i}:{i}')
                for j in range(i + 1, 5):
                    if abs(matrix[i][j] * matrix[j][i] - 1) > Decimal(SETTINGS['reciprocity_tolerance']):
                        return fail('RECIPROCITY_FAILED', f'{i}:{j}')
            result['structurally_valid'] = True
            totals = [sum(matrix[i][j] for i in range(5)) for j in range(5)]
            normalized = [[matrix[i][j] / totals[j] for j in range(5)] for i in range(5)]
            weights = [sum(row) / 5 for row in normalized]
            residual = sum(weights) - 1
            if any(not w.is_finite() or w <= 0 for w in weights) or abs(residual) > Decimal(SETTINGS['weight_sum_tolerance']):
                return fail('WEIGHT_VALIDATION_FAILED')
            wsv = [sum(matrix[i][j] * weights[j] for j in range(5)) for i in range(5)]
            cv = [wsv[i] / weights[i] for i in range(5)]
            lam = sum(cv) / 5
            ci = (lam - 5) / 4
            cr = ci / Decimal('1.12')
            result['calculation'] = {'column_totals': list(map(decimal_text, totals)),
                'normalized_matrix': [[decimal_text(v) for v in row] for row in normalized],
                'weights': dict(zip(CRITERIA, map(decimal_text, weights))),
                'weight_sum_residual': decimal_text(residual), 'WSV': list(map(decimal_text, wsv)),
                'CV': list(map(decimal_text, cv)), 'lambda_estimate': decimal_text(lam),
                'CI': decimal_text(ci), 'CR': decimal_text(cr)}
            result['consistency'] = reference_verdict(cr)
            if result['consistency'] != 'PASSED':
                fail('CR_REFERENCE_FAILED' if result['consistency'] == 'FAILED' else 'NUMERICAL_ANOMALY')
        except DecimalException:
            fail('ARITHMETIC_FAILURE')
    return result
