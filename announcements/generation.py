"""Explicit reviewed selection -> final outcomes -> versioned public results.

Generation finalizes only undecided current eligible applicants as not selected.
It never selects anyone, resolves deferred/stale decisions, or records delivery.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.permissions import require_workspace_permissions
from programs.models import Program
from programs.terms import terms_lock
from ewaf.evidence import digest
from .models import Announcement
from .participation import applicants, ordered_rows, collect_program_results, KIND
from .results import RESULT_PERMISSIONS, prepare_results, publish_results

PERMISSIONS = (*RESULT_PERMISSIONS, 'announcements.add_announcement',
               'announcements.change_announcement', 'announcements.publish_announcement')


def review_roster(program):
    """Private, masked lists remain visible even when publication needs review.

    This is never a publication source or an assertion that stale selections
    are ready. Views must enforce the existing result-review permissions.
    """
    source_rows = applicants(program)
    if program.ewaf_applicable:
        from ewaf.operational_services import latest_decisions
        selected_ids = set()
        for decision in latest_decisions(program).filter(outcome='SELECTED'):
            try:
                decision.clean()
            except ValidationError:
                continue
            selected_ids.add(decision.application_id)
    else:
        selected_ids = set(program.applications.filter(status__in=('SELECTED', 'COMPLETED')).values_list('pk', flat=True))
    return {'applicants': ordered_rows(source_rows, 'Applied'), 'applicant_count': len(source_rows),
        'rows': ordered_rows([row for row in source_rows if row['pk'] in selected_ids], 'Selected'),
        'applicants_ready': True, 'selection_ready': False,
        'selection_message': 'Recorded selections are shown below. Resolve the review notice before publishing.'}


def review_messages(messages):
    import re
    from ewaf.presentation import messages_for_officers
    translated = []
    for message in messages:
        if 'APPLICATION_NOT_CANDIDATE' in message or 'APPLICATION_REVIEW_UNRESOLVED' in message:
            message = 'An application still needs eligibility review. Complete its review before publishing results.'
        message = re.sub(r'^[0-9a-fA-F-]{36}:\s*', '', message)
        translated.extend(messages_for_officers([message]))
    return list(dict.fromkeys(translated))


def publisher(user):
    current = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if current is None:
        raise PermissionDenied
    require_workspace_permissions(current, *PERMISSIONS)
    return current


@terms_lock()
@transaction.atomic
def generation_preview(program_id, *, user):
    user = publisher(user)
    program = Program.objects.select_for_update().get(pk=program_id)
    item = Announcement.objects.select_for_update().filter(program=program).first()
    if item and item.status == 'deleted':
        raise ValidationError('This result announcement was deleted and cannot be republished.')
    version = item.version if item else 0
    if not program.ewaf_applicable:
        payload, source = collect_program_results(program)
        return {'payload': payload, 'pending': [], 'version': version,
                'expected': digest({'source': source, 'version': version}), 'run_id': None}

    from ewaf import operational_services as operational
    from ewaf.operational_models import OperationalRun
    latest = OperationalRun.objects.filter(program=program).first()
    if latest is None:
        raise ValidationError('Generate EWAF Ranking and select applicants for assistance first.')
    # As in the existing public collector, revalidate using the retained
    # calculation authority. Publishers receive only the masked projection.
    calculator = operational.actor(latest.actor, 'ewaf.calculate_operational')
    with operational.fence(program.pk, calculator) as (calculator, program, applications):
        if (program.status != 'published' or not program.published_at or program.published_at > timezone.now()
                or program.registration_closes_at > timezone.now() or not program.policy_authorized_at
                or not program.selection_method.strip()):
            raise ValidationError('Close applications and complete program authorization before generating results.')
        run = operational.current_result_run(program, applications, calculator, latest.pk)
        decisions = {str(row.application_id): row for row in operational.latest_decisions(program)}
        from ewaf.revised.fulfillment import fulfilled_decisions
        fulfilled = fulfilled_decisions(program)
        pending, selected_ids = [], set()
        for key, calculation in run.calculations.items():
            decision = decisions.get(key)
            if decision:
                decision.clean()
                if (decision.run_id != run.pk and key not in fulfilled
                        or decision.outcome not in ('SELECTED', 'NOT_SELECTED')):
                    raise ValidationError('Resolve deferred or earlier-ranking decisions in EWAF before generating results.')
                author = operational.actor(decision.actor, 'ewaf.decide_operational')
                require_workspace_permissions(author, 'assistance.decide_assistance')
                if decision.outcome == 'SELECTED':
                    selected_ids.add(key)
                continue
            comparison = calculation['comparison']
            tied = comparison['capacity_boundary_tie'] if run.configuration.uses_dataset_scoring else comparison['equal'] > 1
            if tied:
                raise ValidationError('Resolve the approved tie procedure in EWAF before generating results.')
            pending.append(key)
        if pending and not user.has_perms((*operational.VIEW, 'ewaf.decide_operational', 'assistance.decide_assistance')):
            raise ValidationError('An authorized selection reviewer must finalize the remaining applicants in EWAF before publication.')
        if program.slots is None or len(selected_ids) > program.slots:
            raise ValidationError('Selected applicants exceed approved program slots.')
        source_rows = applicants(program)
        payload = {'schema': 2, 'kind': KIND, 'program_name': program.name,
            'applicants': ordered_rows(source_rows, 'Applied'), 'applicant_count': len(source_rows),
            'rows': ordered_rows([row for row in source_rows if str(row['pk']) in selected_ids], 'Selected'),
            'applicants_ready': True, 'selection_ready': True}
        expected = digest({'version': version, 'program_version': program.version, 'run': run.digest,
            'decisions': sorted((key, row.digest) for key, row in decisions.items()),
            'applications': source_rows, 'preview': payload})
        return {'payload': payload, 'pending': pending, 'version': version,
                'expected': expected, 'run_id': run.pk}


@terms_lock()
@transaction.atomic
def generate_results(program_id, *, user, expected, version, address=None, selection_reason=''):
    """Publish the exact reviewed list; every write rolls back on any failure."""
    current = publisher(user)
    from .selection_reason import clean_selection_reason
    selection_reason = clean_selection_reason(selection_reason)
    plan = generation_preview(program_id, user=current)
    if version != plan['version'] or expected != plan['expected']:
        raise ValidationError('The program, selections or announcement changed. Review the refreshed list before generating results.')
    from ewaf.operational_services import record_decision
    for application_id in plan['pending']:
        record_decision(program_id, user=current, run_id=plan['run_id'], application_id=application_id,
            expected_revision=0, outcome='NOT_SELECTED',
            reason='Administrator finalized the displayed assistance selection when generating program results; this applicant was not selected.')
    item = prepare_results(program_id, user=current, version=version, roster=True,
        reason='Administrator reviewed and generated the displayed applicant and selected-member results.', address=address,
        selection_reason=selection_reason)
    payload = item.result_revision.public_payload
    if any(payload[key] != plan['payload'][key] for key in ('applicants', 'rows')):
        raise ValidationError('The public result changed during generation. Review the list again.')
    # Recheck publication capability immediately before the final write.
    return publish_results(item.pk, user=publisher(user), version=item.version, address=address)
