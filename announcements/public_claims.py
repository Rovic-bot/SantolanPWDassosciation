"""Current receipt status for identities already authorized in public results."""
from assistance.models import AssistanceRelease


def result_with_claim_status(item):
    """Call after the announcement publication gate, never for private previews.

    Keep the immutable revision intact. Only a received/not-recorded flag is
    added to its existing selected rows; private receipt fields stay private.
    """
    payload = item.result_revision.public_payload
    if payload.get('kind') != 'program_participation':
        # Legacy fragments cannot establish an exact application match. Their
        # original published receipt semantics and publication gate still apply.
        return payload
    references = {row['reference'] for row in payload.get('rows', [])
        if row.get('status') == 'Selected' and not row.get('ambiguous')
        and row.get('reference') and '*' not in row['reference']}
    received = set(AssistanceRelease.objects.successful().filter(
        application__program_id=item.program_id,
        application__public_reference__in=references,
    ).order_by().values_list('application__public_reference', flat=True)) if references else set()
    return {**payload, 'claim_status_current': True,
        'rows': [{**row, 'claim_received': row['reference'] in received}
                 for row in payload.get('rows', [])]}
