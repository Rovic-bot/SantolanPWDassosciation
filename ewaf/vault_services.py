"""Shared weight approvals with immutable policy and calculation history."""
from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from programs.terms import terms_lock
from programs.models import Program
from .evidence import canonical, digest
from .evidence_records import recording
from .evidence_services import persist, reasoned
from .operational_models import OperationalConfiguration as Configuration
from .vault_models import VaultRevision
from . import vault_policy


def token():
    latest = VaultRevision.objects.first()
    return digest({'latest': latest.digest if latest else None})


def latest_for(method):
    from .dataset_methods import method_of
    return next((row for row in VaultRevision.objects.all() if method_of(row.policy) == method), None)


def active(method=None):
    from .dataset_methods import method_of
    now = timezone.now()
    for row in VaultRevision.objects.filter(status='LOCKED'):
        if method is not None and method_of(row.policy) != method:
            continue
        row.clean()
        if vault_policy.scoring_pending(row.policy):
            return row
        if parse_datetime(row.policy['effective_from']) <= now < parse_datetime(row.policy['effective_until']):
            return row
    return None


def approve_percentages(*, user, expected, values, reason):
    from .vault_weights import compile_weights
    _, provenance = compile_weights(values)
    proposed = vault_policy.source_policy()
    proposed['weight_input'] = provenance
    return record(user=user, expected=expected, proposed=proposed, judgments={},
        status='LOCKED', reason=reason, attested=True)


@terms_lock()
def approve(*, user, expected, proposal, reason='Approved the shared EWAF weights and registered data sources.',
            preserve_saved=True):
    """The approval click records its actor/time and retains approved rules."""
    from .operational_services import actor
    from .weight_input import initial_state, project, proposal_criteria
    from .household_criteria import CRITERIA
    actor(user, 'ewaf.authorize_operational')
    if expected != token():
        raise ValidationError('The vault changed. Reload before approving a new version.')
    if proposal_criteria(proposal) != CRITERIA:
        raise ValidationError('Include all five registered household criteria.')
    judgments, _, provenance = project(proposal)
    from .dataset_methods import HOUSEHOLD
    latest = latest_for(HOUSEHOLD)
    starting = initial_state(latest)
    if preserve_saved and latest and starting['startingFromSaved'] and proposal == starting['proposal']:
        judgments = deepcopy(latest.judgments)
        provenance = deepcopy(latest.policy.get('weight_input'))
    previous = active(HOUSEHOLD)
    proposed = deepcopy(previous.policy) if previous else vault_policy.source_policy()
    proposed.pop('weight_input', None)
    if provenance:
        proposed['weight_input'] = provenance
    return record(user=user, expected=expected, proposed=proposed, judgments=judgments,
        status='LOCKED', reason=reason, attested=True)


@terms_lock()
def record_ses_weights(*, user, expected, proposal, reason, status, method=None, projection_method=None):
    from .dataset_methods import SES, SES_CRITERIA, SES_METHODS
    method = SES if method is None else method
    if method not in SES_METHODS:
        raise ValidationError('Select an explicitly supported SES method.')
    from .weight_input import METHOD, CURRENT_METHOD, proposal_criteria, project
    from .dataset_methods import COMPOSITE
    projection_method = projection_method or METHOD
    if projection_method == CURRENT_METHOD and method != COMPOSITE:
        raise ValidationError('The new approval precision is limited to the composite household method.')
    if proposal_criteria(proposal) != SES_CRITERIA:
        raise ValidationError('Select exactly SES, ES, PA and HM; old weight versions cannot be converted.')
    judgments, _, provenance = project(proposal, method=projection_method)
    previous = latest_for(method)
    if status == 'LOCKED' and (not previous or previous.status != 'DRAFT'
            or previous.policy.get('weight_input') != provenance):
        raise ValidationError('Save the current four-criterion proposal as an unapproved weight draft before approving it.')
    policy = vault_policy.source_policy(method)
    policy['weight_input'] = provenance
    return record(user=user, expected=expected, proposed=policy, judgments=judgments,
        status=status, reason=reason, attested=status == 'LOCKED')


@terms_lock()
def approve_current_weights(*, user, expected, proposal, review, reason):
    """Approve a reviewed AHP preview, retaining its draft and approval atomically."""
    from .operational_services import actor
    from .dataset_methods import COMPOSITE
    from .weight_input import accept
    actor(user, 'ewaf.authorize_operational')
    if expected != token():
        raise ValidationError('The vault changed. Reload and calculate the AHP weights again.')
    _, provenance = accept(review, proposal, program='ewaf-vault:' + COMPOSITE, expected=expected)
    previous = latest_for(COMPOSITE)
    if not previous or previous.status != 'DRAFT' or previous.policy.get('weight_input') != provenance:
        record_ses_weights(user=user, expected=expected, proposal=proposal, reason=reason,
            status='DRAFT', method=COMPOSITE, projection_method=provenance['method'])
    return record_ses_weights(user=user, expected=token(), proposal=proposal, reason=reason,
        status='LOCKED', method=COMPOSITE, projection_method=provenance['method'])


def record(*, user, expected, proposed, judgments, status, reason, attested=False):
    from .operational_services import actor
    from django.contrib.admin.models import LogEntry, ADDITION
    from django.contrib.contenttypes.models import ContentType
    if not vault_policy.enabled():
        raise ValidationError('The configuration vault is not enabled.')
    with terms_lock():
        current = actor(user, 'ewaf.authorize_operational' if status == 'LOCKED' else 'ewaf.configure_operational')
        authority = (current.pk, current.is_superuser, frozenset(current.get_all_permissions()))
        if expected != token() or status not in ('DRAFT', 'LOCKED'):
            raise ValidationError('The vault changed. Reload before saving a new version.')
        fields = reasoned(current, reason, attested if status == 'LOCKED' else True)
        if not isinstance(proposed, dict) or len(str(proposed)) > 64000 or len(str(judgments)) > 2000:
            raise ValidationError('The shared configuration is invalid or too large.')
        from .weight_input import validate_provenance
        validate_provenance(proposed.get('weight_input'), judgments)
        validation = {}
        from .vault_weights import is_direct, replay
        if is_direct(proposed):
            validation = replay(proposed['weight_input'], judgments)
        else:
            try:
                from .weight_input import replay_ahp
                validation = replay_ahp(judgments, proposed.get('weight_input'))
            except ValidationError:
                pass
        if status == 'LOCKED':
            vault_policy.validate(proposed, judgments)
        previous = VaultRevision.objects.first()
        row = VaultRevision(revision=previous.revision + 1 if previous else 1, previous=previous,
            status=status, policy=canonical(proposed), judgments=judgments, validation=validation, **fields)
        row.digest = digest(row.payload())
        row.audit_entry = LogEntry.objects.create(user=current, content_type=ContentType.objects.get_for_model(VaultRevision),
            object_id=str(row.revision), object_repr=f'EWAF Configuration Vault version {row.revision}',
            action_flag=ADDITION, change_message=row.digest)
        with recording():
            row.save()
        # Unstarted weights-only drafts follow the shared approval. Every prior
        # revision, opened intake and scoring binding stays immutable.
        activated = active() if status == 'LOCKED' else None
        if activated and activated.pk == row.pk:
            for program in Program.objects.filter(status='draft', ewaf_applicable=True,
                    published_at__isnull=True, applications__isnull=True).order_by('pk'):
                inherit(program, user=current, revision=row)
        # The scoring definition lives in code; approving weights can complete
        # already-published weights-only programs without a second setup screen.
        from .dataset_methods import COMPOSITE, method_of
        if (status == 'LOCKED' and method_of(row.policy) == COMPOSITE
                and current.has_perm('programs.publish_program')):
            from .fixed_scoring import bind as bind_fixed
            for program in Program.objects.filter(status='published', ewaf_applicable=True).order_by('pk'):
                retained = Configuration.objects.filter(program=program).first()
                if retained and retained.policy.get('configuration_scope') == 'weights_and_sources':
                    bind_fixed(program, user=current)
        final = actor(user, 'ewaf.authorize_operational' if status == 'LOCKED' else 'ewaf.configure_operational')
        if (final.pk, final.is_superuser, frozenset(final.get_all_permissions())) != authority:
            raise PermissionDenied('Administrator authority changed. Reload before saving the vault.')
        return row


@terms_lock()
def inherit(program, *, user, revision=None):
    if not vault_policy.enabled() or not program.ewaf_applicable:
        return None
    from .shared_weights import publication_locked
    if publication_locked(program):
        return None
    revision = revision or active()
    if not revision:
        return None
    previous = Configuration.objects.filter(program=program).first()
    if previous:
        from .dataset_methods import method_of
        from .operational_models import OperationalRun
        if (previous.vault_revision_id == revision.pk or previous.status != 'DRAFT'
                or not previous.vault_revision_id or previous.dataset_policy_id
                or method_of(previous.policy) != method_of(revision.policy)
                or not vault_policy.scoring_pending(previous.policy) or not vault_policy.scoring_pending(revision.policy)
                or program.status != 'draft' or program.published_at or program.applications.exists()
                or OperationalRun.objects.filter(program=program).exists()):
            return None
    from .operational_services import configuration_source
    fields = reasoned(user, f'Automatically inherited approved EWAF vault version {revision.pk}.', True)
    return persist(Configuration(program=program, previous=previous, revision=previous.revision + 1 if previous else 1,
        status='DRAFT', vault_revision=revision,
        policy=deepcopy(revision.policy), judgments=deepcopy(revision.judgments), validation=deepcopy(revision.validation),
        source=configuration_source(program), **fields))


@terms_lock()
def prepare_publication(program, *, user):
    if not vault_policy.enabled() or not program.ewaf_applicable:
        return
    from .fixed_scoring import bind as bind_fixed
    fixed = bind_fixed(program, user=user)
    if fixed:
        return fixed
    row = Configuration.objects.filter(program=program).first()
    if not row:
        row = inherit(program, user=user)
    if not row:
        raise ValidationError('Approve and activate the shared rules in the EWAF Configuration Vault before publishing.')
    if row.dataset_policy_id:
        row.clean()
        from .revised.shared_application import apply
        row = apply(program, user=user) or row
        from .revised.live_services import require_binding
        require_binding(row)
        return
    if not row.vault_revision_id:
        return  # Retain the program's previously approved configuration contract.
    row.clean()
    if vault_policy.scoring_pending(row.policy):
        from .intake_policy import prepare
        prepared = prepare(program, row, user=user)
        from .revised.shared_application import apply
        return apply(program, user=user) or prepared
    vault_policy.require_scoring_rules(row.policy)
    if row.status == 'LOCKED':
        return
    if not program.policy_authorized_at or not program.policy_authorized_by_id:
        raise ValidationError('Authorize the program policy before publishing with the inherited vault configuration.')
    from programs.approval_policy import require_binding
    require_binding(program, first_publication=program.published_at is None)
    from .operational_services import configuration_source
    persist(Configuration(program=program, revision=row.revision + 1, previous=row, status='LOCKED',
        vault_revision=row.vault_revision, policy=deepcopy(row.policy), judgments=deepcopy(row.judgments),
        validation=deepcopy(row.validation), source=configuration_source(program),
        **reasoned(user, f'Applied approved EWAF vault version {row.vault_revision_id} to the authorized program.', True)))


def validate_inheritance(configuration):
    revision = configuration.vault_revision
    revision.clean()
    if (revision.status != 'LOCKED' or configuration.policy != revision.policy
            or configuration.judgments != revision.judgments or configuration.validation != revision.validation
            or configuration.evidence_policy_id):
        raise ValidationError('The program must use the exact approved vault version it inherited.')
