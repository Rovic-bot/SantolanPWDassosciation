"""Owner-authorized masked names and full application references (2026-10-25).

Only program application references are public here, never membership numbers,
access tokens, scores or the private evidence used by EWAF.
"""
import hashlib
import json

from django.core.exceptions import ValidationError
from django.utils import timezone

from programs.models import Program
from programs.terms import terms_lock
from .results import collect_results, mask_identity

KIND = 'program_participation'


def applicants(program):
    return list(program.applications.order_by('pk').values(
        'pk', 'public_reference', 'member__full_name', 'member__version'))


def public_row(application, status):
    # Reuse the established word-initial mask and legacy-reference validation.
    row = mask_identity(application['member__full_name'], application['public_reference'])
    row.update(reference=application['public_reference'], status=status, ambiguous=False)
    return row


def ordered_rows(applications, status):
    return sorted((public_row(row, status) for row in applications),
                  key=lambda row: (row['name'], row['reference']))


@terms_lock()
def collect_program_results(program, *, retained_revision=None):
    """New revision schema; the legacy collector still validates every selection."""
    program = Program.objects.select_for_update().get(pk=program.pk)
    if retained_revision is not None:
        from programs.mandatory_ewaf import publication_source_program
        program = publication_source_program(program, retained_revision)
    selected, source_digest = collect_results(program)
    applications = applicants(program)
    if program.ewaf_applicable:
        from ewaf.operational_models import OperationalRun
        from ewaf.operational_services import latest_decisions
        run = OperationalRun.objects.filter(program=program).first()
        selected_ids = set(latest_decisions(program).filter(run=run, outcome='SELECTED')
                           .values_list('application_id', flat=True))
        # Completed deliveries retain their original approved decision when a
        # newer ranking is generated. The private collector above validates it.
        from ewaf.revised.fulfillment import fulfilled_decisions
        selected_ids.update(decision.application_id for decision in fulfilled_decisions(program).values())
    else:
        selected_ids = set(program.applications.filter(status__in=('SELECTED', 'COMPLETED'))
                           .values_list('pk', flat=True))
    rows = ordered_rows([row for row in applications if row['pk'] in selected_ids], 'Selected')
    if len(rows) != len(selected['rows']):
        raise ValidationError('The current selection needs review before publication.')
    payload = {**selected, 'schema': 2, 'kind': KIND,
        'applicants': ordered_rows(applications, 'Applied'), 'rows': rows,
        'applicant_count': len(applications), 'applicants_ready': True, 'selection_ready': True}
    digest = hashlib.sha256(json.dumps({'selection': source_digest,
        'applications': applications, 'payload': payload}, sort_keys=True, default=str).encode()).hexdigest()
    return payload, digest


@terms_lock()
def public_program_participation(program):
    """Current roster for an already published program announcement only."""
    program = Program.objects.select_for_update().get(pk=program.pk)
    if program.status != 'published' or not program.published_at or program.published_at > timezone.now():
        return None
    try:
        payload, _ = collect_program_results(program)
        return payload
    except ValidationError:
        # Public readers get no private validation failures or provisional scores.
        try:
            rows = ordered_rows(applicants(program), 'Applied')
            applicants_ready = True
        except ValidationError:
            rows, applicants_ready = [], False
        return {'schema': 2, 'kind': KIND, 'program_name': program.name,
            'applicants': rows, 'applicant_count': len(rows), 'rows': [], 'applicants_ready': applicants_ready,
            'applicant_message': 'The applicant list is temporarily unavailable while its references are reviewed.',
            'selection_ready': False,
            'selection_message': 'Selected members will appear after the required calculation and selection review are complete.'
                if program.ewaf_applicable else 'Selected members will appear after application reviews and selection are complete.'}
