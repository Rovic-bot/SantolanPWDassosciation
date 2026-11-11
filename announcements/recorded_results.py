"""Owner-authorized publication of recorded selections, independent of review readiness.

This path publishes existing records only. It never finalizes pending applicants,
changes a selection, recalculates a score, or records assistance delivery.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ewaf.evidence import digest
from programs.models import Program
from programs.terms import terms_lock
from .models import Announcement
from .participation import KIND, ordered_rows


@terms_lock()
@transaction.atomic
def collect_recorded_results(program):
    program = Program.objects.select_for_update().get(pk=program.pk)
    applications = list(program.applications.order_by('pk').values(
        'pk', 'public_reference', 'member__full_name', 'member__version', 'status'))
    decisions = []
    if program.ewaf_applicable:
        from ewaf.operational_services import latest_decisions
        from programs.mandatory_ewaf import retained_selected_ids
        selected_ids = retained_selected_ids(program)
        # Load relationship checks together, but share each potentially large
        # ranking snapshot instead of decoding it again for every decision.
        decisions_to_review = (latest_decisions(program).select_related(None)
            .select_related('application', 'previous').prefetch_related('run'))
        for decision in decisions_to_review.order_by('application_id'):
            # Retain artifact integrity without demanding a fresh ranking,
            # completed eligibility review, or a resolved deferred decision.
            decision.clean()
            decisions.append((str(decision.application_id), decision.digest))
            if decision.outcome == 'SELECTED':
                selected_ids.add(decision.application_id)
    else:
        selected_ids = {row['pk'] for row in applications if row['status'] in ('SELECTED', 'COMPLETED')}
    payload = {
        'schema': 2, 'kind': KIND, 'publication_mode': 'recorded',
        'program_name': program.name, 'description': program.description,
        'program_date': timezone.localtime(program.starts_at).strftime('%B %d, %Y')
            if program.starts_at else 'See program schedule',
        'slots': program.slots,
        'applicants': ordered_rows(applications, 'Applied'), 'applicant_count': len(applications),
        'rows': ordered_rows([row for row in applications if row['pk'] in selected_ids], 'Selected'),
        'applicants_ready': True, 'selection_ready': True,
    }
    identities = [{key: row[key] for key in ('pk', 'public_reference', 'member__full_name')}
                  for row in applications]
    return payload, digest({'applications': identities, 'decisions': decisions, 'payload': payload})


@terms_lock()
@transaction.atomic
def recorded_preview(program_id, *, user):
    from .generation import publisher
    from .results import lock_program
    publisher(user)
    program = lock_program(program_id)
    item = Announcement.objects.select_for_update().filter(program=program).first()
    if item and item.status == 'deleted':
        raise ValidationError('This result announcement was deleted and cannot be republished.')
    payload, source = collect_recorded_results(program)
    version = item.version if item else 0
    selection_reason = item.result_revision.public_payload.get('selection_reason', '') if item and item.result_revision_id else ''
    return {'payload': payload, 'version': version, 'pending': [], 'selection_reason': selection_reason,
            'expected': digest({'source': source, 'version': version})}


@terms_lock()
@transaction.atomic
def publish_recorded_results(program_id, *, user, expected, version, address=None, selection_reason=''):
    from .generation import publisher
    from .results import prepare_results, publish_results
    current = publisher(user)
    from .selection_reason import clean_selection_reason, with_selection_reason
    selection_reason = clean_selection_reason(selection_reason)
    plan = recorded_preview(program_id, user=current)
    if version != plan['version'] or expected != plan['expected']:
        raise ValidationError('The recorded results changed. Review the refreshed list before publishing.')
    item = prepare_results(program_id, user=current, version=version, recorded=True,
        reason='Administrator explicitly authorized publication of the displayed recorded applicants and selections '
               'independently of review readiness. No application decisions, rankings or releases were changed.',
        address=address, selection_reason=selection_reason)
    expected_payload, _ = with_selection_reason(plan['payload'], '', selection_reason)
    if item.result_revision.public_payload != expected_payload:
        raise ValidationError('The recorded results changed during publication. Review the list again.')
    published = publish_results(item.pk, user=publisher(user), version=item.version, address=address)
    from .certificate_delivery import queue_certificates
    queue_certificates(published, user=current)
    return published
