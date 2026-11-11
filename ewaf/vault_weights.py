"""Exact, explicitly approved percentages for the document-based dataset method.

Historical AHP revisions keep their original validator. These percentages are
recorded as a separate weighting method, never reconstructed AHP judgments.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from .revised.math import CRITERIA, DEFAULTS, CalculationError, proposal

METHOD = 'approved-percentage-weights-v1'
SOURCE = 'Computation_Updated_HI_SI_ES_PA_HM.docx'


def is_direct(policy):
    origin = policy.get('weight_input') if isinstance(policy, dict) else None
    return isinstance(origin, dict) and origin.get('method') == METHOD


def compile_weights(values):
    try:
        weights = proposal(values)
    except CalculationError as error:
        raise ValidationError(str(error)) from error
    # Basis points are exact integers, so Decimal context cannot round a value.
    units = {code: int(weight * 10000) for code, weight in zip(CRITERIA, weights)}
    decimals = {code: f'{amount // 10000}.{amount % 10000:04d}' for code, amount in units.items()}
    provenance = {'method': METHOD, 'source_document': SOURCE,
        'proposal': {'order': list(CRITERIA), 'weights': units}}
    return {'method': METHOD, 'weights': decimals}, provenance


def replay(provenance, judgments):
    try:
        units = provenance['proposal']['weights']
        if set(units) != set(CRITERIA) or any(type(value) is not int for value in units.values()):
            raise ValueError
        values = {code: f'{units[code] // 100}.{units[code] % 100:02d}' for code in CRITERIA[:4]}
        validation, expected = compile_weights(values)
        if provenance != expected or judgments != {}:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValidationError('The saved percentage weights or their source do not match.') from None
    return validation


def initial_values(configuration=None):
    if configuration and is_direct(configuration.policy):
        units = configuration.policy['weight_input']['proposal']['weights']
        return {code: Decimal(units[code]) / 100 for code in CRITERIA[:4]}
    # An unapproved starting suggestion; never overwrite a retained AHP vector.
    return dict(zip(CRITERIA[:4], DEFAULTS))
