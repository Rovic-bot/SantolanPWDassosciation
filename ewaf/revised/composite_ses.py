"""Versioned income-dependent adjustment. No dataset or coefficient rescaling."""
from fractions import Fraction
from django.core.exceptions import ValidationError

FORMULA = {'version': 'income-4ps-multiplier-90-10-v1', 'base': '9/10', 'participation': '1/10',
           'normalization': 'income_need_once_then_multiplier'}


def calculate(income_need, participation):
    if type(participation) is not int or participation not in (0, 1):
        raise ValidationError('SES requires explicit reviewed household 4Ps participation: Verified Yes or Verified No; missing is unresolved.')
    if not 0 <= income_need <= 1:
        raise ValidationError('Income need must use the complete accepted pool bounds without clipping.')
    multiplier = Fraction(9, 10) + Fraction(1, 10) * participation
    return income_need * multiplier, multiplier
