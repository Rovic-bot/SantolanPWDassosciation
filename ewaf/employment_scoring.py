"""Owner-confirmed employment scores, frozen per new dataset calculation.

Runs without this marker replay the original four-category document encoding.
The November 10 owner instruction authorizes this rule; it does not rewrite
stored policies, accepted evidence or past calculations.
"""
from copy import copy, deepcopy
from django.core.exceptions import ValidationError
from . import dataset_methods as methods

VERSION = 'member-employment-five-categories-2026-11-10'
KEY = 'employment_scoring'
SCORES = {'Employed': 1, 'Self-Employed': 2, 'Student': 3, 'Retired': 4, 'Unemployed': 5}
MAPPING = dict(zip(('employed', 'self_employed', 'student', 'retired', 'unemployed'), SCORES))


def capture(configuration):
    if configuration and getattr(configuration, 'uses_dataset_scoring', getattr(configuration, 'dataset_policy_id', None)) and methods.is_dataset(configuration.policy):
        return {KEY: {'version': VERSION, 'scores': dict(SCORES)}}
    return {}


def encoding(snapshot):
    from .revised.engine import ES
    if KEY not in snapshot:
        return ES
    if snapshot[KEY] != {'version': VERSION, 'scores': SCORES}:
        raise ValidationError('The saved employment scoring rule does not match its exact version.')
    return SCORES


def runtime(configuration, snapshot=None):
    """Use a temporary input mapping; keep the persisted binding unchanged."""
    if not configuration:
        return configuration
    snapshot = capture(configuration) if snapshot is None else snapshot
    encoding(snapshot)
    from .revised.automatic_inputs import enabled
    if KEY not in snapshot or not enabled(configuration.policy):
        return configuration
    result = copy(configuration)
    result.policy = deepcopy(configuration.policy)
    result.policy['registration_inputs'] = {'version': VERSION, 'employment': dict(MAPPING)}
    return result
