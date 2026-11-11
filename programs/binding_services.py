from ewaf.source_invalidation import source_writer
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from core.permissions import require_workspace_permissions
from .models import Program, ProgramApprovalControl, ProgramTermsRevision, ProgramApprovalBinding, ProgramTermsLock
from .terms import terms_lock, snapshot_terms, terms_digest, FROZEN, SCHEMA_VERSION
from .services import record_log

VIEW = ('programs.view_program', 'programs.view_pdaoapprovalrecord',
        'programs.view_programtermsrevision', 'programs.view_programapprovalbinding')
WRITE = (*VIEW, 'programs.bind_programapprovalbinding')


def check_request(program, control, *, version, program_version, reason, confirmed):
    if version != control.version or program_version != program.version:
        raise ValidationError('The program or approval review changed. Reload before continuing.')
    if confirmed is not True or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Explicit confirmation and a reason of up to 2,000 characters are required.')


@source_writer("pk", action="terms_recorded", control=True)
@terms_lock()
def capture_terms(pk, *, user, version, program_version, digest, reason, confirmed, address=None):
    require_workspace_permissions(user, *WRITE)
    program = Program.objects.select_for_update().get(pk=pk)
    control, _ = ProgramApprovalControl.objects.get_or_create(program=program)
    check_request(program, control, version=version, program_version=program_version, reason=reason, confirmed=confirmed)
    snapshot = snapshot_terms(program)
    actual = terms_digest(snapshot)
    if actual != digest:
        raise ValidationError('The displayed terms changed. Reload and review the complete terms.')
    previous = control.current_revision
    if previous and previous.digest == actual:
        raise ValidationError('These exact terms have already been recorded.')
    # An unbound initial draft may have been configured after a preliminary
    # capture. Capturing it does not authorize it. Published/bound terms cannot
    # receive a revised approval through this preparation workflow.
    if previous and (program.published_at or program.approval_bindings.exists()):
        raise ValidationError(FROZEN)
    latest = program.terms_revisions.order_by('-number').first()
    number = latest.number + 1 if latest else 1
    log = record_log(program, 'terms_recorded', reason.strip(), user=user, address=address,
                     changes={'terms_revision': {'before': previous.number if previous else None, 'after': number}})
    revision = ProgramTermsRevision.objects.create(program=program, number=number, schema_version=SCHEMA_VERSION,
        snapshot=snapshot, digest=actual, actor=user, actor_label=user.get_username(), reason=reason.strip(), audit_entry=log)
    control.current_revision = revision
    control.current_digest = actual
    control.version += 1
    control.save()
    return revision


@source_writer("pk", action="approval_bound", control=True)
@terms_lock()
def bind_approval(pk, *, user, version, program_version, revision_id, approval_id,
                  approval_version, reason, confirmed, address=None):
    require_workspace_permissions(user, *WRITE)
    program = Program.objects.select_for_update().get(pk=pk)
    control = ProgramApprovalControl.objects.filter(program=program).first()
    if not control:
        raise ValidationError('Record and review the program terms first.')
    check_request(program, control, version=version, program_version=program_version, reason=reason, confirmed=confirmed)
    revision = program.terms_revisions.filter(pk=revision_id).first()
    approval = program.pdao_approval_records.filter(pk=approval_id).first()
    latest = program.pdao_approval_records.first()
    if not revision or not approval or not latest or approval_version != latest.version:
        raise ValidationError('Select an approval from this program and reload if its history changed.')
    if (control.current_revision_id != revision.pk or control.current_digest != revision.digest or
            terms_digest(snapshot_terms(program)) != revision.digest):
        raise ValidationError('The selected revision does not match the current program terms.')
    if not approval.manual_confirmation:
        raise ValidationError('The record must explicitly confirm manual approval.')
    approval.full_clean()
    if approval.kind == 'legacy':
        if not program.published_at or program.published_at > timezone.now() or revision.number != 1:
            raise ValidationError('Legacy attestation cannot authorize a new program or later changed terms.')
    if approval.bindings.exclude(revision=revision).exists():
        raise ValidationError('An approval record cannot authorize a different terms revision.')
    if control.active_binding_id:
        previous = control.active_binding
        if previous.revision_id != revision.pk:
            raise ValidationError(FROZEN)
        if previous.approval_record_id == approval.pk:
            raise ValidationError('This approval is already explicitly bound to these terms.')
    log = record_log(program, 'approval_bound', reason.strip(), user=user, address=address, changes={
        'approval_record': {'before': control.active_binding.approval_record_id if control.active_binding_id else None, 'after': approval.pk},
        'terms_revision': {'before': control.current_revision_id, 'after': revision.pk},
        'approval_control_version': {'before': control.version, 'after': control.version + 1}})
    binding = ProgramApprovalBinding.objects.create(program=program, revision=revision, approval_record=approval,
        actor=user, actor_label=user.get_username(), reason=reason.strip(), confirmed=True, audit_entry=log)
    control.active_binding = binding
    control.version += 1
    control.save()
    return binding


def preflight():
    """Read-only check; never sets configuration or manufactures approvals."""
    from .approval_policy import binding_condition
    with transaction.atomic():
        locked = ProgramTermsLock.objects.select_for_update().filter(pk=1).first()
        # All published programs are included: a closed intake window does not
        # establish that assessment, selection or releases have finished.
        operating = Program.objects.filter(status='published')
        unresolved = operating.exclude(binding_condition()).count()
        drift = 0
        for program in operating.filter(binding_condition()).select_related('approval_control').iterator():
            if terms_digest(snapshot_terms(program)) != program.approval_control.current_digest:
                drift += 1
        return {'operating': operating.count(), 'unresolved': unresolved, 'drift': drift,
                'ready': unresolved == 0 and drift == 0 and (locked is not None or not operating.exists())}
