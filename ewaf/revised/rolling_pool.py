"""Versioned rankings during intake, with a frozen observation time per run."""
from copy import copy, deepcopy
from datetime import timezone as datetime_timezone

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import automatic_inputs

RULE = 'current_eligible_v1'
KEY = 'ranking_window'
CONTRACT = 'current-eligible-pool-v1'
SELECTION_RULE = 'current-eligible-selection-v1'
ZERO_CONSTANTS = 'zero_contribution_v1'
ZERO_METHOD = 'dataset_composite_ses_zero_constants_v1'


def enabled(policy):
    value = policy.get('choices', {}).get('pool_rule', {}).get('value', policy.get('pool_rule'))
    return automatic_inputs.enabled(policy) and value == RULE


def assessment_configuration(configuration, at=None):
    """An in-memory input-period view, never an altered persisted binding."""
    at = at or timezone.now()
    if timezone.is_naive(at) or at > timezone.now():
        raise ValidationError('A ranking cannot use a future or unspecified observation time.')
    at = at.astimezone(datetime_timezone.utc)
    if not parse_datetime(configuration.policy['effective_from']) <= at < parse_datetime(configuration.policy['effective_until']):
        raise ValidationError('The ranking observation must fall within the approved policy period.')
    close = parse_datetime(configuration.source['terms']['program']['registration_closes_at'])
    cutoff = min(at, configuration.assessment_cutoff)
    runtime = copy(configuration)
    runtime.assessment_cutoff = cutoff
    window = {'contract': CONTRACT, 'assessed_at': str(at), 'cutoff': str(cutoff),
              'registration_open': at < close}
    return runtime, window


def from_snapshot(snapshot, configuration):
    if not enabled(configuration.policy):
        if KEY in snapshot:
            raise ValidationError('This retained policy does not authorize ranking during registration.')
        return configuration
    window = snapshot.get(KEY)
    if not isinstance(window, dict) or set(window) != {'contract', 'assessed_at', 'cutoff', 'registration_open'}:
        raise ValidationError('Retain the exact observation time and cutoff of this ranking.')
    try:
        at = parse_datetime(window['assessed_at'])
        if at is None:
            raise ValueError
        runtime, expected = assessment_configuration(configuration, at)
    except (ValueError, TypeError):
        raise ValidationError('The saved ranking observation time is invalid.') from None
    if window != expected or type(window['registration_open']) is not bool:
        raise ValidationError('The saved ranking period does not match its approved cutoff.')
    return runtime


def observation(snapshot):
    """Tokens compare source facts, not elapsed microseconds between GET and POST."""
    value = deepcopy(snapshot)
    value.pop(KEY, None)
    return value


def observed_at(snapshot):
    window = snapshot.get(KEY)
    if window is None:
        return None
    try:
        at = parse_datetime(window['assessed_at'])
        if at is None or timezone.is_naive(at):
            raise ValueError
        return at
    except (KeyError, TypeError, ValueError):
        raise ValidationError('The saved ranking observation time is invalid.') from None


def provisional(snapshot):
    return bool(snapshot.get(KEY, {}).get('registration_open'))


def selection_waiting(snapshot, configuration):
    """Current rankings can support selection while registration is still open.

    Once intake closes, keep the complete-pool and final-cutoff requirements.
    Freshness, eligibility, capacity and tie checks remain in the decision service.
    """
    if not enabled(configuration.policy):
        return False
    runtime = from_snapshot(snapshot, configuration)
    close = parse_datetime(configuration.source['terms']['program']['registration_closes_at'])
    if timezone.now() < close:
        return False
    return provisional(snapshot) or runtime.assessment_cutoff < configuration.assessment_cutoff


def same_revision_rules(before, after):
    if not (automatic_inputs.enabled(before) and enabled(after) and not enabled(before)):
        return False
    old, new = deepcopy(before), deepcopy(after)
    for content in (old, new):
        for key in ('pool_rule', 'constant_rule', 'method_rules'):
            content['choices'].pop(key, None)
    # Existing employment meanings stay exact; newly approved categories can be
    # added explicitly, without changing anyone's recorded employment status.
    old_mapping = old['registration_inputs']['employment']
    new_mapping = new['registration_inputs']['employment']
    if any(new_mapping.get(key) != value for key, value in old_mapping.items()):
        return False
    new['registration_inputs']['employment'] = deepcopy(old_mapping)
    return old == new


def permits_revision(program, previous, policy, cutoff):
    if not (previous and previous.dataset_policy_id and
            same_revision_rules(previous.dataset_policy.content, policy.content)):
        return False
    from ewaf.operational_models import OperationalRun
    from .live_models import DatasetInputReview
    if (program.status not in ('draft', 'published') or
            OperationalRun.objects.filter(program=program).exists() or
            DatasetInputReview.objects.filter(program=program, state='ACCEPTED').exists()):
        raise ValidationError('Already calculated programs retain their original ranking rules and history.')
    if cutoff != previous.assessment_cutoff or policy.weight_snapshot != previous.dataset_policy.weight_snapshot:
        raise ValidationError('The ranking-window revision must retain the exact approved weights and cutoff.')
    return True
