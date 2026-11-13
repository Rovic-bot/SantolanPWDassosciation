"""Audited dataset-policy orchestration beside the preserved fixed-range path."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timezone as datetime_timezone
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from programs.models import Program
from programs.terms import terms_lock, snapshot_terms, terms_digest
from core.permissions import require_workspace_permissions
from ewaf.evidence import digest, canonical
from ewaf.evidence_records import recording
from ewaf.evidence_services import reasoned, persist
from ewaf.operational_models import OperationalConfiguration as Configuration
from ewaf.operational_services import actor, configuration_source, configuration_token
from ewaf.vault_models import VaultRevision
from .live_models import SharedDatasetPolicy as Policy
from . import contracts
from .engine import METHOD


def enabled():
    return getattr(settings, 'EWAF_DATASET_POLICY_ENABLED', False)


def require_scoring_enabled():
    if not enabled() or not getattr(settings, 'EWAF_DATASET_SCORING_ENABLED', False):
        raise ValidationError('Official dataset scoring is not enabled. Retained policy and history remain available.')


def schema_available():
    return Policy._meta.db_table in connection.introspection.table_names()


@contextmanager
def authority(user, permission):
    if not enabled():
        raise ValidationError('The new dataset-policy workflow is not enabled.')
    with terms_lock():
        current = actor(user, permission)
        stamp = (current.pk, current.is_superuser, frozenset(current.get_all_permissions()))
        yield current
        refreshed = actor(user, permission)
        if stamp != (refreshed.pk, refreshed.is_superuser, frozenset(refreshed.get_all_permissions())):
            raise PermissionDenied('Policy authority changed during this action. Reload before continuing.')


def token():
    latest = Policy.objects.first()
    return digest({'latest': latest.digest if latest else None})


def dataset_source(program):
    from ewaf.evidence import approval_context
    terms = snapshot_terms(program)
    return canonical({'contract': 'dataset_program_terms_v1', 'terms': terms,
        'program_terms_digest': terms_digest(terms), 'approval': approval_context(program),
        'policy_authorized_at': program.policy_authorized_at, 'policy_authorized_by': program.policy_authorized_by_id})


def _store(row):
    from django.contrib.admin.models import LogEntry, ADDITION
    from django.contrib.contenttypes.models import ContentType
    row.digest = digest(row.payload())
    row.audit_entry = LogEntry.objects.create(user=row.actor, content_type=ContentType.objects.get_for_model(Policy),
        object_id=row.digest, object_repr=f'Dataset scoring policy {row.revision} {row.status}',
        action_flag=ADDITION, change_message=row.digest)
    with recording():
        row.save()
    return row


def save_draft(*, user, expected, content, weight_id, reason):
    with authority(user, 'ewaf.configure_operational') as current:
        if expected != token():
            raise ValidationError('The shared policy changed. Reload before saving a new draft version.')
        contracts.structural(content)
        content = deepcopy(content)
        content['evidence_catalog'] = contracts.evidence_catalog(content)
        previous = Policy.objects.first()
        weight = VaultRevision.objects.filter(pk=weight_id).first() if weight_id else None
        if weight_id and weight is None:
            raise ValidationError('Select an existing compatible locked weight version.')
        snapshot = contracts.weight_snapshot(weight, content['method']) if weight else {}
        return _store(Policy(revision=previous.revision + 1 if previous else 1, previous=previous,
            status='DRAFT', method=content['method'], content=canonical(content), weight_configuration=weight, weight_snapshot=snapshot,
            **reasoned(current, reason, True)))


def approve(policy_id, *, user, expected, reviewed_groups, reason):
    with authority(user, 'ewaf.authorize_operational') as current:
        latest = Policy.objects.first()
        if not latest or latest.pk != policy_id or latest.status != 'DRAFT' or expected != latest.digest:
            raise ValidationError('Review the current unchanged draft before approval.')
        latest.clean()
        if set(reviewed_groups) != {'A', 'B', 'C'} or len(reviewed_groups) != 3:
            raise ValidationError('Review each of A, B and C explicitly; unresolved choices cannot be approved.')
        problems = contracts.findings(latest.content, latest.weight_snapshot or None)
        if problems:
            raise ValidationError(problems)
        values = contracts.values(latest.content)
        if parse_datetime(values['effective_until']) <= timezone.now():
            raise ValidationError('The proposed policy has already expired.')
        from . import shared_application
        from ewaf.shared_calculation_rules import MARKER
        if shared_application.enabled_for(latest.content) or MARKER in latest.content:
            require_workspace_permissions(current, 'programs.publish_program')
        row = _store(Policy(revision=latest.revision + 1, previous=latest, status='APPROVED', method=latest.method,
            content=deepcopy(latest.content), weight_configuration=latest.weight_configuration,
            weight_snapshot=deepcopy(latest.weight_snapshot), **reasoned(current, reason, True)))
        shared_application.apply_all(row, user=current)
        return row


def require_policy(policy, *, at=None):
    policy.clean()
    if policy.status != 'APPROVED':
        raise ValidationError('An explicitly approved scoring-policy version is required before binding for calculation.')
    problems = contracts.findings(policy.content, policy.weight_snapshot or None)
    if problems:
        raise ValidationError(problems)
    values = contracts.values(policy.content)
    at = at or timezone.now()
    if not parse_datetime(values['effective_from']) <= at < parse_datetime(values['effective_until']):
        raise ValidationError('The bound scoring-policy version is outside its approved effective period.')


def validate_configuration(row):
    policy = row.dataset_policy
    policy.clean()
    if (policy.status != 'APPROVED' or row.status != 'LOCKED' or row.vault_revision_id or row.evidence_policy_id
            or row.policy != contracts.configuration_policy(policy) or row.judgments != {}
            or row.validation != {'weights': policy.weight_snapshot['weights'], 'weight_version': policy.weight_configuration_id,
                                  'weight_digest': policy.weight_snapshot['digest'], 'method': 'retained_locked_vector'}):
        raise ValidationError('The program must retain the exact approved policy, method and weight version.')
    if not row.assessment_cutoff or timezone.is_naive(row.assessment_cutoff):
        raise ValidationError('An explicit timezone-aware program assessment cutoff is required.')
    if (row.previous_id and (row.previous.program_id != row.program_id or row.revision != row.previous.revision + 1)
            or not row.previous_id and row.revision != 1):
        raise ValidationError('The program configuration predecessor is invalid.')


def require_binding(row):
    if not enabled():
        raise ValidationError('The dataset-policy workflow is not enabled.')
    from ewaf.fixed_scoring import is_fixed, require_binding as require_fixed
    if is_fixed(row):
        return require_fixed(row)
    validate_configuration(row)
    require_policy(row.dataset_policy)
    if row.source != configuration_source(row.program):
        raise ValidationError('Program terms changed after policy binding. Review and explicitly bind a new configuration.')
    if (row.assessment_cutoff < row.program.registration_closes_at
            or row.assessment_cutoff >= parse_datetime(row.policy['effective_until'])):
        raise ValidationError('The assessment cutoff must follow application closing and fall inside policy validity.')


def bind(program_id, *, user, expected, policy_id, cutoff, reason):
    with authority(user, 'ewaf.authorize_operational') as current:
        require_workspace_permissions(current, 'programs.publish_program')
        program = Program.objects.select_for_update().get(pk=program_id)
        if expected != configuration_token(program):
            raise ValidationError('The program or its configuration changed. Reload before binding.')
        policy = Policy.objects.filter(pk=policy_id).first()
        if policy is None:
            raise ValidationError('Select an existing approved policy version.')
        previous = binding_preflight(program, policy, cutoff)
        return store_binding(program, previous, policy, cutoff, user=current, reason=reason)


def binding_preflight(program, policy, cutoff):
    """Shared validation for explicit historical and centrally approved binding."""
    previous = Configuration.objects.filter(program=program).first()
    from ewaf.result_weights import publication_locked, locked_weights
    if publication_locked(program) and (not previous or
            policy.weight_configuration_id != locked_weights(program)['id']):
        raise ValidationError('Published program results retain their ranking weight version. Programs without published results can use different Vault weights.')
    from .member_record_evidence import permits_evidence_revision
    from .rolling_pool import permits_revision
    record_revision = (permits_evidence_revision(program, previous, policy, cutoff)
                       or permits_revision(program, previous, policy, cutoff))
    if record_revision:
        require_binding(previous)
    from ewaf.intake_policy import CONTRACT as INTAKE_CONTRACT, require_configuration
    pending_intake = bool(previous and previous.source.get('contract') == INTAKE_CONTRACT
        and previous.policy.get('configuration_scope') == 'weights_and_sources')
    if pending_intake:
        require_configuration(program)
        from ewaf.operational_models import OperationalRun
        if program.status not in ('draft', 'published') or OperationalRun.objects.filter(program=program).exists():
            raise ValidationError('Only an active weights-only intake without calculations can receive its first scoring policy.')
    elif not record_revision and (program.status != 'draft' or program.published_at or program.applications.exists()):
        raise ValidationError('Existing scored or historical programs retain their policy. Only new drafts or approved weights-only intakes can receive this binding.')
    if previous and not previous.dataset_policy_id and previous.policy.get('configuration_scope') != 'weights_and_sources':
        raise ValidationError('Historical fixed-range programs retain their existing method and configuration.')
    if not program.ewaf_applicable or not program.policy_authorized_at or not program.policy_authorized_by_id:
        raise ValidationError('Authorize this program and its EWAF selection method before binding a scoring policy.')
    from programs.approval_policy import require_binding as require_terms
    require_terms(program, first_publication=True)
    require_policy(policy)
    if previous and (previous.vault_revision_id or previous.dataset_policy_id):
        from ewaf.dataset_methods import method_of, compatible_weight_methods
        if method_of(previous.policy) != policy.method:
            new_draft_weight_reuse = (previous.vault_revision_id and not previous.dataset_policy_id
                and program.status == 'draft' and not program.published_at and not program.applications.exists()
                and method_of(previous.policy) in compatible_weight_methods(policy.method)
                and policy.weight_configuration_id == previous.vault_revision_id)
            if not new_draft_weight_reuse:
                raise ValidationError('The policy method must match this program\'s retained weight signature; historical bindings cannot be converted.')
    if pending_intake and policy.weight_configuration_id != previous.vault_revision_id:
        from .shared_application import shares_composite_rules
        if not shares_composite_rules(previous, policy):
            raise ValidationError('The scoring policy must retain the exact weight version already bound for these applications.')
    if not cutoff or timezone.is_naive(cutoff) or cutoff < program.registration_closes_at:
        raise ValidationError('Choose an explicit assessment cutoff at or after the approved application close.')
    if cutoff >= parse_datetime(contracts.values(policy.content)['effective_until']):
        raise ValidationError('The assessment cutoff must fall inside the approved policy validity.')
    return previous


def store_binding(program, previous, policy, cutoff, *, user, reason):
    """Only called inside an authorized terms-lock transaction after preflight."""
    # Django persists aware datetimes in UTC. Sign that same representation so
    # a cutoff entered in Philippine time still validates after a database read.
    cutoff = cutoff.astimezone(datetime_timezone.utc)
    row = persist(Configuration(program=program, previous=previous, revision=previous.revision + 1 if previous else 1,
        status='LOCKED', dataset_policy=policy, assessment_cutoff=cutoff,
        policy=contracts.configuration_policy(policy), judgments={},
        validation={'weights': deepcopy(policy.weight_snapshot['weights']), 'weight_version': policy.weight_configuration_id,
                    'weight_digest': policy.weight_snapshot['digest'], 'method': 'retained_locked_vector'},
        source=dataset_source(program), **reasoned(user, reason, True)))
    require_binding(row)
    return row
