"""Follow Vault approval until results publication freezes the ranking weights."""
from django.core.exceptions import ValidationError

from . import dataset_methods as methods
from .revised.contracts import weight_snapshot

CONTRACT = 'approved-vault-weights-per-calculation-v1'
KEY = 'approved_weights'


def publication_locked(program):
    from .result_weights import publication_locked as results_locked
    return results_locked(program)


def current(configuration):
    from .vault_policy import enabled
    if not configuration or not getattr(configuration, 'uses_dataset_scoring', getattr(configuration, 'dataset_policy_id', None)) or not methods.is_composite(configuration.policy) or not enabled():
        return None
    from .result_weights import locked_weights
    locked = locked_weights(configuration.program)
    if locked is not None:
        return locked
    from .vault_services import active
    revision = active(methods.COMPOSITE)
    if revision is None:
        raise ValidationError('Approve the four-criterion AHP weights in the Configuration Vault before generating a ranking.')
    return {'contract': CONTRACT, 'method': methods.COMPOSITE,
            **weight_snapshot(revision, methods.COMPOSITE)}


def capture(configuration):
    selected = current(configuration)
    # The original approved binding already freezes this exact version. Keeping
    # its snapshot shape also preserves freshness of unchanged historical runs.
    if selected and selected['id'] != configuration.validation['weight_version']:
        return {KEY: selected}
    return {}


def retained(snapshot, configuration):
    """Validate the saved approval, never substitute today's Vault on replay."""
    if KEY not in snapshot:
        return None
    from .vault_models import VaultRevision
    selected = snapshot[KEY]
    if (not getattr(configuration, 'uses_dataset_scoring', getattr(configuration, 'dataset_policy_id', None)) or not methods.is_composite(configuration.policy)
            or not isinstance(selected, dict) or selected.get('contract') != CONTRACT
            or selected.get('method') != methods.COMPOSITE or type(selected.get('id')) is not int):
        raise ValidationError('The saved shared weights must belong to the composite four-criterion method.')
    revision = VaultRevision.objects.filter(pk=selected['id']).first()
    if revision is None or methods.method_of(revision.policy) != methods.COMPOSITE:
        raise ValidationError('The saved shared weight approval is missing or belongs to another method.')
    expected = {'contract': CONTRACT, 'method': methods.COMPOSITE,
                **weight_snapshot(revision, methods.COMPOSITE)}
    if selected != expected:
        raise ValidationError('The saved weights do not match their exact approved AHP version.')
    return selected
