"""Exact, explicitly published selections that permit assistance receipt recording."""
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.utils import timezone

from .models import Announcement, ProgramResultRevision
from .participation import KIND

MESSAGE = 'Publish this selected member in Announcements before recording actual receipt.'


def published_selection(program, *, lock=False):
    """Read the published snapshot, not a new selection or a draft applicant list.

    A later addition does not erase earlier publication. Current eligibility and
    selection remain independently enforced by the release writer. Legacy masked
    references cannot establish an exact member match and require republication.
    """
    query = Announcement.objects.filter(
        program=program, status='published', published_at__lte=timezone.now())
    if lock:
        query = query.select_for_update().prefetch_related(Prefetch(
            'result_revision', queryset=ProgramResultRevision.objects.select_for_update()))
    else:
        query = query.select_related('result_revision')
    item = query.first()
    if not item or not item.result_revision:
        return set(), None
    revision = item.result_revision
    payload = revision.public_payload
    if (revision.announcement_id != item.pk or payload.get('schema') != 2
            or payload.get('kind') != KIND or not payload.get('selection_ready')):
        return set(), None
    audit = item.events.filter(action='results_published',
        description=f'Authorized publication of reviewed privacy-masked result revision {revision.number}.').first()
    if not audit:
        return set(), None
    references = {row['reference'] for row in payload.get('rows', [])
        if isinstance(row, dict) and row.get('status') == 'Selected' and isinstance(row.get('reference'), str)}
    return references, {'announcement': str(item.pk), 'revision': revision.pk,
        'number': revision.number, 'source_digest': revision.source_digest,
        'published_at': item.published_at.isoformat(), 'audit': audit.pk}


def require_published_selection(application, program):
    references, witness = published_selection(program, lock=True)
    if application.public_reference not in references:
        raise ValidationError(MESSAGE)
    return witness
