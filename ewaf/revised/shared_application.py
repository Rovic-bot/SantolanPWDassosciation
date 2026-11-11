"""Apply a centrally approved policy without repeating program EWAF setup.

No GET writes and no conversion of an existing scoring binding. The optional
versioned content is absent from historical policies, which keep their contract.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from programs.models import Program
from ewaf.operational_models import OperationalConfiguration as Configuration, OperationalRun
from .live_models import SharedDatasetPolicy as Policy

VERSION = 'shared-program-application-v1'
SCOPE = 'all_compatible_unbound_programs'
CUTOFFS = {
    'application_close': 'Each program\'s approved application closing time',
    'fixed': 'One explicit assessment cutoff for programs covered by this version',
}


def structural(content):
    rule = content.get('program_application')
    if 'program_application' not in content:
        return
    if (not isinstance(rule, dict) or set(rule) != {'version', 'scope', 'cutoff_rule', 'cutoff_at'}
            or rule['version'] != VERSION or rule['scope'] != SCOPE
            or rule['cutoff_rule'] not in ('', *CUTOFFS) or not isinstance(rule['cutoff_at'], str)):
        raise ValidationError('Use the versioned shared program-application rule.')


def findings(content):
    rule = content.get('program_application')
    if rule is None:
        return []  # Retained explicit-binding policies are not converted.
    if not rule['cutoff_rule']:
        return ['C: choose the shared assessment cutoff rule once in the Configuration Vault.']
    if rule['cutoff_rule'] == 'application_close':
        return ['C: a closing-time rule cannot also specify a fixed cutoff.'] if rule['cutoff_at'] else []
    try:
        cutoff = parse_datetime(rule['cutoff_at'])
    except (ValueError, TypeError):
        cutoff = None
    if not cutoff or timezone.is_naive(cutoff):
        return ['C: specify a timezone-aware assessment cutoff for the shared fixed-date rule.']
    return []


def enabled_for(content):
    return bool(content.get('program_application'))


def shares_composite_rules(configuration, policy):
    """Current main weights do not require reapproval of unchanged input rules."""
    from ewaf.dataset_methods import COMPOSITE, is_composite
    from ewaf.vault_policy import enabled
    return bool(enabled() and configuration and configuration.vault_revision_id
        and not configuration.dataset_policy_id and is_composite(configuration.policy)
        and policy.method == COMPOSITE and enabled_for(policy.content))


def can_inherit(program, configuration):
    if not program.ewaf_applicable or program.status not in ('draft', 'published'):
        return False
    if configuration and (configuration.dataset_policy_id or not configuration.vault_revision_id
            or configuration.policy.get('configuration_scope') != 'weights_and_sources'):
        return False
    return not OperationalRun.objects.filter(program=program).exists()


def candidate(program, configuration):
    if not can_inherit(program, configuration):
        return None
    rows = Policy.objects.filter(status='APPROVED')
    if configuration:
        from ewaf.dataset_methods import method_of, is_composite
        rows = rows.filter(method=method_of(configuration.policy))
        if not is_composite(configuration.policy):
            rows = rows.filter(weight_configuration_id=configuration.vault_revision_id)
    for row in rows:
        if enabled_for(row.content):
            return row
    return None


def preflight(program, configuration, policy=None):
    """Read-only readiness. Never swallow persistence/audit failures."""
    from . import live_services as service
    from ewaf.vault_policy import enabled as vault_enabled
    if not can_inherit(program, configuration):
        return None, None, []
    if not service.enabled() or not vault_enabled() or not service.schema_available():
        return None, None, ['Shared calculation-rule application is unavailable until its workflow and schema are enabled.']
    policy = policy or candidate(program, configuration)
    if policy is None:
        return None, None, ['Complete and approve the shared calculation rules in the Configuration Vault. No program weight entry is needed.']
    if not enabled_for(policy.content):
        return None, None, ['This retained policy requires its original explicit binding procedure.']
    if (configuration and configuration.vault_revision_id != policy.weight_configuration_id
            and not shares_composite_rules(configuration, policy)):
        return None, None, ['The shared policy must use this intake\'s retained approved weight version.']
    try:
        service.require_policy(policy)
        rule = policy.content['program_application']
        cutoff = program.registration_closes_at if rule['cutoff_rule'] == 'application_close' else parse_datetime(rule['cutoff_at'])
        service.binding_preflight(program, policy, cutoff)
    except ValidationError as error:
        return None, None, error.messages
    return policy, cutoff, []


def status(program, configuration):
    if not can_inherit(program, configuration):
        return {}
    policy, cutoff, problems = preflight(program, configuration)
    return {'policy': policy, 'cutoff': cutoff, 'problems': problems,
        'ready': bool(policy), 'pending': not policy}


def _apply(program, *, user, policy=None):
    from . import live_services as service
    previous = Configuration.objects.filter(program=program).first()
    if previous and previous.dataset_policy_id:
        # A program still being prepared can receive approved term corrections.
        # Append the same shared policy against those terms; never switch its
        # weights/method, refresh an opened intake, or rewrite a saved record.
        retained = previous.dataset_policy
        if (not enabled_for(retained.content) or policy is not None and policy.pk != retained.pk
                or program.status != 'draft' or program.published_at or program.applications.exists()
                or OperationalRun.objects.filter(program=program).exists()
                or previous.source == service.dataset_source(program)):
            return None
        try:
            previous.clean()
            rule = retained.content['program_application']
            cutoff = program.registration_closes_at if rule['cutoff_rule'] == 'application_close' else parse_datetime(rule['cutoff_at'])
            service.binding_preflight(program, retained, cutoff)
        except ValidationError:
            return None
        return service.store_binding(program, previous, retained, cutoff, user=user,
            reason=f'Reapplied the same shared policy {retained.pk} to approved program terms before intake. Prior binding retained.')
    if policy is not None:
        latest = candidate(program, previous)
        if latest is None or latest.pk != policy.pk:
            return None
    selected, cutoff, problems = preflight(program, previous, policy)
    if selected is None:
        return None
    return service.store_binding(program, previous, selected, cutoff, user=user,
        reason=f'Automatically applied centrally approved shared policy {selected.pk}, '
               f'Vault weights {selected.weight_configuration_id} and its approved cutoff rule.')


def apply(program, *, user):
    from . import live_services as service
    from ewaf.vault_policy import enabled as vault_enabled
    if not service.enabled() or not vault_enabled() or not program.ewaf_applicable or not service.schema_available():
        return None
    # Central EWAF approval has already been recorded. A publisher applying it
    # does not need to approve the same EWAF settings again.
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied
    from core.permissions import require_workspace_permissions
    from programs.terms import terms_lock
    with terms_lock():
        current = get_user_model().objects.get(pk=user.pk)
        require_workspace_permissions(current, 'programs.view_program', 'programs.publish_program')
        stamp = (current.is_superuser, frozenset(current.get_all_permissions()))
        program = Program.objects.select_for_update().get(pk=program.pk)
        row = _apply(program, user=current)
        refreshed = get_user_model().objects.get(pk=user.pk)
        require_workspace_permissions(refreshed, 'programs.view_program', 'programs.publish_program')
        if stamp != (refreshed.is_superuser, frozenset(refreshed.get_all_permissions())):
            raise PermissionDenied('Program publication authority changed during shared configuration application.')
        return row


def apply_all(policy, *, user):
    from . import live_services as service
    from ewaf.vault_policy import enabled as vault_enabled
    if not enabled_for(policy.content) or not vault_enabled():
        return 0
    with service.authority(user, 'ewaf.authorize_operational') as current:
        from core.permissions import require_workspace_permissions
        require_workspace_permissions(current, 'programs.publish_program')
        count = 0
        for program in Program.objects.select_for_update().filter(ewaf_applicable=True,
                status__in=('draft', 'published'), policy_authorized_at__isnull=False).order_by('pk'):
            count += _apply(program, user=current, policy=policy) is not None
        return count
