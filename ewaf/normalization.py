"""G15 synthetic arithmetic. No Association policy or application access."""
import re
from decimal import (Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
                     Overflow, Underflow, ROUND_HALF_EVEN, localcontext)

CRITERIA = ('SI', 'ES', 'PA', 'ND', 'PR')
ENGINE = 'g15-minmax-wsm-1'
PROFILE = 'synthetic-fixed-bounds-1'
SETTINGS = {'precision': 50, 'rounding': 'ROUND_HALF_EVEN', 'Emin': -999, 'Emax': 999,
            'input_digits': 40, 'output_digits': 50, 'numeric_chars': 120, 'output_chars': 1100,
            'input_exponent': 40, 'output_exponent': 999, 'weight_sum_tolerance': '1e-45',
            'display': 'canonical text; no additional quantization',
            'traps': ['InvalidOperation', 'DivisionByZero', 'Overflow', 'Underflow']}


class NumericIssue(ValueError):
    pass


def arithmetic_context():
    return Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-999, Emax=999,
                   capitals=1, clamp=0, traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def number(value, *, calculated=False):
    """Calculated output has its own resource contract; never truncate G14 weights."""
    if type(value) not in (str, int):
        raise NumericIssue('INVALID_NUMBER')
    if type(value) is int and value.bit_length() > 400:
        raise NumericIssue('NUMERIC_RESOURCE_LIMIT')
    text = str(value)
    if len(text) > SETTINGS['output_chars' if calculated else 'numeric_chars']:
        raise NumericIssue('NUMERIC_RESOURCE_LIMIT')
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', text):
        raise NumericIssue('INVALID_NUMBER')
    value = Decimal(text)
    limit = SETTINGS['output_exponent' if calculated else 'input_exponent']
    digits = SETTINGS['output_digits' if calculated else 'input_digits']
    significant = ''.join(map(str, value.as_tuple().digits)).rstrip('0')
    if len(significant) > digits or abs(value.as_tuple().exponent) > limit or abs(value.adjusted()) > limit:
        raise NumericIssue('NUMERIC_RESOURCE_LIMIT')
    return value


def decimal_text(value):
    # No ambient normalize()/quantize(): remove insignificant zeros textually.
    if value == 0:
        return '0'
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def normalize(value, lower, upper, direction):
    result = {'complete': False, 'value': None, 'lower': None, 'upper': None,
              'direction': direction, 'normalized': None, 'reasons': []}
    if value is None or value == '':
        result['reasons'] = ['VALUE_MISSING']
        return result
    if lower is None or upper is None or lower == '' or upper == '':
        result['reasons'] = ['BOUNDS_PENDING']
        return result
    if direction not in ('benefit', 'inverse'):
        result['reasons'] = ['NORMALIZATION_DIRECTION_PENDING']
        return result
    try:
        with localcontext(arithmetic_context()):
            x, lo, hi = (number(item) for item in (value, lower, upper))
            result.update(value=decimal_text(x), lower=decimal_text(lo), upper=decimal_text(hi))
            if lo == hi:
                raise NumericIssue('ZERO_RANGE')
            if lo > hi:
                raise NumericIssue('BOUNDS_ORDER_INVALID')
            if not lo <= x <= hi:
                raise NumericIssue('VALUE_OUT_OF_BOUNDS')
            # Detect lost information in subtraction, without a business tolerance.
            with localcontext(arithmetic_context()) as exact:
                exact.prec = 200
                exact_range = hi - lo
                exact_offset = (x - lo) if direction == 'benefit' else (hi - x)
            width = hi - lo
            offset = (x - lo) if direction == 'benefit' else (hi - x)
            if width != exact_range or offset != exact_offset:
                raise NumericIssue('NUMERIC_PRECISION_INSUFFICIENT')
            normalized = offset / width
            result.update(complete=True, normalized=decimal_text(normalized))
    except NumericIssue as error:
        result['reasons'].append(str(error))
    except DecimalException:
        result['reasons'].append('ARITHMETIC_FAILURE')
    return result
