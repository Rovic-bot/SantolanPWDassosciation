"""Exact arithmetic for revised dataset Min–Max v1, independent of Django/legacy engines.

All calculations, classifications and comparisons use Fraction, with zero tolerance.
Finite decimal/rational inputs are exact. Binary floats are refused. Decimal strings
at 50 significant digits are explanations only; two-place display uses exact half-even
rounding. Neither display representation is fed back into calculations.
"""
from decimal import Context, Decimal, DivisionByZero, InvalidOperation, Overflow, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import re

METHOD = 'ewaf-hi-si-es-pa-hm-dataset-v1'
CRITERIA = ('HI', 'SI', 'ES', 'PA', 'HM')
NAMES = ('Household Monthly Income', 'Socioeconomic Indicator', 'Employment Status',
         'Previous Assistance Received', 'Number of Household Members')
DEFAULTS = ('34.21', '23.60', '17.74', '12.23')
LIMITS = (('26.40', '62.55'), ('19.48', '34.21'), ('14.07', '23.60'), ('12.23', '17.74'))
PRECISION = 'Exact rational arithmetic; zero comparison tolerance; half-even display at 2 decimals; explanatory decimals at 50 significant digits.'
RANKING = 'competition-v1: 1 + count of strictly greater exact scores; tied presentation order gives no priority'
DISPLAY_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN,
                          traps=[DivisionByZero, InvalidOperation, Overflow])


class CalculationError(ValueError):
    """A failed prerequisite never supplies an assumed value."""


def number(value):
    if type(value) not in (int, str, Decimal, Fraction):
        raise CalculationError('Use an exact finite decimal or rational number, never a binary float or boolean.')
    if isinstance(value, Decimal) and (not value.is_finite() or abs(value.as_tuple().exponent) > 120):
        raise CalculationError('Use a finite decimal within the arithmetic input precision limit.')
    if isinstance(value, str) and not re.fullmatch(r'[+-]?\d+(?:\.\d+|/\d+)?', value):
        raise CalculationError('Use a plain finite decimal or exact numerator/denominator.')
    if len(str(value)) > 160:
        raise CalculationError('Numeric representation is too long.')
    try:
        result = Fraction(value)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as error:
        raise CalculationError('A required numeric value is missing or invalid.') from error
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > 512:
        raise CalculationError('Numeric representation exceeds the arithmetic input limit.')
    return result


def display(value, places=2):
    value = Fraction(value)
    sign = '-' if value < 0 else ''
    whole, remainder = divmod(abs(value.numerator) * 10 ** places, value.denominator)
    if remainder * 2 > value.denominator or remainder * 2 == value.denominator and whole % 2:
        whole += 1
    integer, fraction = divmod(whole, 10 ** places)
    return f'{sign}{integer}.{fraction:0{places}d}' if places else f'{sign}{integer}'


def packed(value):
    value = Fraction(value)
    with localcontext(DISPLAY_CONTEXT):
        decimal = str(Decimal(value.numerator) / Decimal(value.denominator))
    return {'exact': str(value), 'decimal': decimal}


def consistent(cr):
    cr = number(cr)
    return 0 <= cr < Fraction(1, 10)


def ahp(matrix):
    """Column normalization / row average, not the principal-eigenvector method."""
    if not isinstance(matrix, (tuple, list)) or len(matrix) != 5 or any(
            not isinstance(row, (tuple, list)) or len(row) != 5 for row in matrix):
        raise CalculationError('AHP requires a five-by-five matrix in HI/SI/ES/PA/HM order.')
    a = tuple(tuple(number(value) for value in row) for row in matrix)
    for i in range(5):
        for j in range(5):
            if a[i][j] <= 0 or i == j and a[i][j] != 1 or a[i][j] * a[j][i] != 1:
                raise CalculationError('AHP entries must be positive, diagonal ones and exactly reciprocal.')
    sums = tuple(sum(a[i][j] for i in range(5)) for j in range(5))
    normalized = tuple(tuple(a[i][j] / sums[j] for j in range(5)) for i in range(5))
    weights = tuple(sum(row) / 5 for row in normalized)
    validate_weights(weights, positive=True)
    wsv = tuple(sum(a[i][j] * weights[j] for j in range(5)) for i in range(5))
    cv = tuple(wsv[i] / weights[i] for i in range(5))
    eigenvalue = sum(cv) / 5
    ci = (eigenvalue - 5) / 4
    cr = ci / Fraction(28, 25)
    return {'matrix': a, 'column_sums': sums, 'normalized_matrix': normalized,
            'weights': weights, 'wsv': wsv, 'cv': cv, 'lambda_max_estimate': eigenvalue,
            'ci': ci, 'ri': Fraction(28, 25), 'cr': cr, 'consistent': consistent(cr)}


def require_consistency(result):
    if not consistent(result['cr']):
        raise CalculationError('AHP consistency requires 0 <= CR < 0.10; this matrix fails.')


def validate_weights(weights, *, positive):
    if len(weights) != 5 or sum(weights) != 1 or any(
            value <= 0 if positive else value < 0 for value in weights):
        raise CalculationError('Weights must total exactly 100% and be positive for AHP (nonnegative for draft sensitivity only).')


def proposal(values):
    """Independent four-control proposal. No redistribution and no ratio matrix."""
    if not isinstance(values, dict) or set(values) != set(CRITERIA[:4]):
        raise CalculationError('Propose exactly HI, SI, ES and PA; HM is calculated automatically.')
    percentages = tuple(number(values[code]) for code in CRITERIA[:4])
    for code, value, (lower, upper) in zip(CRITERIA, percentages, LIMITS):
        if not number(lower) <= value <= number(upper) or (value * 100).denominator != 1:
            raise CalculationError(f'{code}: use {lower}–{upper}% in 0.01% steps.')
    hm = 100 - sum(percentages)
    if hm < 0:
        raise CalculationError(f'Invalid combination: HM would be {display(hm)}%. Reduce one of the four proposed weights.')
    weights = tuple(value / 100 for value in (*percentages, hm))
    validate_weights(weights, positive=False)
    return weights


def classification(score):
    if type(score) not in (int, Fraction):
        score = number(score)
    score = Fraction(score)
    if not 0 <= score <= 100:
        raise CalculationError('Classification needs an unrounded score on the 0–100 scale.')
    for lower, label in ((80, 'High'), (60, 'Moderate'), (40, 'Low'), (0, 'Minimal')):
        if score >= lower:
            return label + ' Assistance Need'


def ranks(scores, capacity=None):
    """Competition ranks. Stable tie ordering is presentation only, never selection."""
    if capacity is not None and (type(capacity) is not int or capacity < 0):
        raise CalculationError('Capacity must be a nonnegative integer, or absent.')
    scores = [Fraction(value) if type(value) in (int, Fraction) else number(value) for value in scores]
    ordered = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    result = {}
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        size = end - position
        for index, _ in ordered[position:end]:
            result[index] = {'rank': position + 1, 'tie_size': size,
                'tie_group': f'tie-{position + 1}' if size > 1 else '',
                'capacity_boundary_tie': capacity is not None and position < capacity < end}
        position = end
    return result
