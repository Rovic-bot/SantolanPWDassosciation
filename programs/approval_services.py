from ewaf.source_invalidation import source_writer
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.permissions import require_workspace_permissions
from .approval_forms import PDAOApprovalForm
from .models import PDAOApprovalRecord, Program
from .services import record_log
from .terms import terms_lock


@source_writer("program_id", action="pdao_recorded")
@terms_lock()
@transaction.atomic
def record_pdao_approval(program_id, *, user, data, address=None):
    require_workspace_permissions(user, 'programs.view_program', 'programs.view_pdaoapprovalrecord',
                                  'programs.record_pdaoapprovalrecord')
    program = Program.objects.select_for_update().get(pk=program_id)
    form = PDAOApprovalForm(data)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    # Publication time is retained on withdrawal/archive. It is a prerequisite
    # for a legacy attestation, never evidence of manual PDAO approval itself.
    if form.cleaned_data['kind'] == PDAOApprovalRecord.Kind.LEGACY and (
            program.published_at is None or program.published_at > timezone.now()):
        raise ValidationError('Legacy attestations require a previously published program. '
                              'For a new program, record official approval from the physical letter.')
    latest = program.pdao_approval_records.order_by('-version').first()
    previous_version = latest.version if latest else 0
    if (form.cleaned_data['expected_version'] != previous_version
            or form.cleaned_data['expected_program_version'] != program.version):
        raise ValidationError('The program or approval history changed. Reload and review before recording again.')
    entry = form.save(commit=False)
    entry.program = program
    entry.version = previous_version + 1
    entry.program_version_at_recording = program.version
    entry.recorded_by = user
    entry.recorded_by_label = user.get_username()
    entry.audit_entry = record_log(program, 'pdao_recorded', 'Manual PDAO approval history entry recorded.',
        user=user, address=address, changes={
            'pdao_record_version': {'before': previous_version, 'after': entry.version},
            'pdao_record_type': {'before': latest.kind if latest else None, 'after': entry.kind},
        })
    try:
        entry.full_clean()
    except ValidationError as error:
        raise ValidationError(error.messages) from error
    entry.save()
    # Recording is deliberately independent of Program.version, availability,
    # internal policy authorization, eligibility and result publication.
    return entry
