"""Approved weights permit scheduled intake; scoring authorization stays separate."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from programs.terms import snapshot_terms, terms_digest
from .evidence import approval_context, canonical
from .evidence_services import persist, reasoned
from .vault_policy import scoring_pending

CONTRACT = 'approved_weights_intake_v1'


def source(program):
    return canonical({'contract': CONTRACT, 'program_terms_digest': terms_digest(snapshot_terms(program)),
        'policy_authorized_at': program.policy_authorized_at, 'policy_authorized_by': program.policy_authorized_by_id,
        'approval': approval_context(program)})


def validate_weights(configuration):
    """Validate the exact inherited locked record, never whichever vault is latest."""
    configuration.clean()
    if (not scoring_pending(configuration.policy) or not configuration.vault_revision_id
            or configuration.vault_revision.status != 'LOCKED'
            or configuration.status != 'DRAFT'):
        raise ValidationError('Use this program\'s retained approved and locked weight configuration.')


def prepare(program, configuration, *, user):
    """Called inside the existing authorized, atomic publication transaction."""
    from .operational_models import OperationalConfiguration
    from programs.approval_policy import require_binding
    from core.permissions import require_workspace_permissions
    require_workspace_permissions(user, 'programs.view_program', 'programs.publish_program')
    validate_weights(configuration)
    if not program.policy_authorized_at or not program.policy_authorized_by_id:
        raise ValidationError('Authorize the program policy before publishing with its approved weights.')
    require_binding(program, first_publication=program.published_at is None)
    current = source(program)
    if configuration.source == current:
        return configuration
    return persist(OperationalConfiguration(program=program, revision=configuration.revision + 1,
        previous=configuration, status='DRAFT', vault_revision=configuration.vault_revision,
        policy=deepcopy(configuration.policy), judgments=deepcopy(configuration.judgments),
        validation=deepcopy(configuration.validation), source=current,
        **reasoned(user, f'Bound approved Vault version {configuration.vault_revision_id} for publication and scheduled applications. Scoring policy remains pending.', True)))


def require_configuration(program):
    """Use only for intake. Calculations/selection keep latest_configuration()."""
    from .operational_services import latest_configuration
    configuration = latest_configuration(program, require_locked=False)
    if not scoring_pending(configuration.policy):
        return latest_configuration(program)
    validate_weights(configuration)
    if not program.policy_authorized_at or not program.policy_authorized_by_id or configuration.source != source(program):
        raise ValidationError('The approved weights must be bound to the current authorized program terms before applications open.')
    return configuration
