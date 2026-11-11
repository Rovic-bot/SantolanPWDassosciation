"""Owner-confirmed HM baseline for new composite rankings, frozen per run.

The November 11 instruction sets one household member to zero and the largest
household in the eligible program pool to one. Runs without this marker retain
their original pool-minimum and equal-value rules during historical replay.
"""
from fractions import Fraction

from django.core.exceptions import ValidationError

from . import dataset_methods as methods

VERSION = 'household-members-fixed-one-2026-11-11-v1'
KEY = 'household_scoring'


def definition():
    return {'version': VERSION, 'minimum': 1, 'maximum': 'eligible_program_pool',
            'all_one': 'zero'}


def capture(configuration):
    if (configuration and methods.is_composite(configuration.policy)
            and getattr(configuration, 'uses_dataset_scoring',
                        getattr(configuration, 'dataset_policy_id', None))):
        return {KEY: definition()}
    return {}


def retained(snapshot, configuration):
    if KEY not in snapshot:
        return None
    saved = snapshot[KEY]
    if (not methods.is_composite(configuration.policy) or saved != definition()
            or type(saved.get('minimum')) is not int):
        raise ValidationError('The saved Household Members scoring rule does not match its exact version.')
    return saved


def normalize(value, maximum):
    if (value.denominator != 1 or maximum.denominator != 1
            or not 1 <= value <= maximum):
        raise ValidationError('Household Members must be a whole number of at least 1 within the eligible program pool.')
    return Fraction(0) if maximum == 1 else (value - 1) / (maximum - 1)


def require_current(configuration, snapshot):
    if capture(configuration).get(KEY) != snapshot.get(KEY):
        raise ValidationError('Household Members scoring rule changed. Generate a new ranking to use a baseline of 1. This saved ranking keeps its original scores.')
