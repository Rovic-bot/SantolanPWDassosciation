"""Versioned equal-value rules for new composite runs; frozen rules for replay."""
from django.core.exceptions import ValidationError

from . import dataset_methods as methods
from .evidence import canonical

FULL_CONSTANTS = 'full_contribution_v1'
FULL_METHOD = 'dataset_composite_ses_full_constants_v1'
CONTRACT = 'shared-composite-constant-rule-v1'
SCOPE = 'new_compatible_composite_calculations'
MARKER = 'calculation_application'
KEY = 'approved_calculation_rules'


def structural(content):
    if MARKER not in content:
        return
    if (not methods.is_composite(content)
            or content[MARKER] != {'version': CONTRACT, 'scope': SCOPE}):
        raise ValidationError('Use the versioned shared composite equal-value calculation rule.')


def policy_snapshot(policy):
    from .revised.contracts import values
    policy.clean()
    structural(policy.content)
    if policy.status != 'APPROVED' or MARKER not in policy.content:
        raise ValidationError('An approved shared equal-value rule is required.')
    rules = values(policy.content)
    return canonical({'contract': CONTRACT, 'id': policy.pk, 'revision': policy.revision,
        'digest': policy.digest, 'method': policy.method, 'approved_at': policy.recorded_at,
        'effective_from': rules['effective_from'], 'effective_until': rules['effective_until'],
        'constant_rule': rules['constant_rule'], 'method_rules': rules['method_rules']})


def current(configuration):
    from .fixed_scoring import is_fixed
    if is_fixed(configuration):
        return None  # Fixed code rules are already frozen in the program audit snapshot.
    if not configuration or not configuration.dataset_policy_id or not methods.is_composite(configuration.policy):
        return None
    from .revised.live_models import SharedDatasetPolicy
    from .revised.live_services import require_policy
    policy = SharedDatasetPolicy.objects.filter(status='APPROVED', method=methods.COMPOSITE,
        content__has_key=MARKER).first()
    if policy is None:
        return None
    require_policy(policy)
    return policy_snapshot(policy)


def capture(configuration):
    selected = current(configuration)
    return {KEY: selected} if selected else {}


def retained(snapshot, configuration):
    """Replay the exact saved approval, never today's current rule."""
    if KEY not in snapshot:
        return None
    from .revised.live_models import SharedDatasetPolicy
    selected = snapshot[KEY]
    if (not configuration.dataset_policy_id or not methods.is_composite(configuration.policy)
            or not isinstance(selected, dict) or type(selected.get('id')) is not int):
        raise ValidationError('The saved shared calculation rule must belong to the composite method.')
    policy = SharedDatasetPolicy.objects.filter(pk=selected['id']).first()
    if policy is None or selected != policy_snapshot(policy):
        raise ValidationError('The saved calculation rule does not match its exact approved version.')
    return selected
