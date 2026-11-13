"""Weights of the ranking behind the first audited result publication.

The existing publication audit and append-only ranking/decision history provide
the lock. Preparing or publishing a program notice is not result publication.
Nothing is written on reads, and withdrawing results does not erase this history.
"""
import re

from django.core.exceptions import ValidationError
from django.db.models import Q

from .dataset_methods import COMPOSITE, is_composite, method_of


def publication_locked(program):
    from announcements.models import Announcement
    return bool(program and program.pk and Announcement.objects.filter(program_id=program.pk).filter(
        Q(published_at__isnull=False) | Q(events__action='results_published')).exists())


def first_publication(program):
    from announcements.models import AnnouncementEvent, ProgramResultRevision
    event = AnnouncementEvent.objects.filter(announcement__program_id=program.pk,
        action='results_published').order_by('occurred_at', 'pk').first()
    match = re.fullmatch(r'Authorized publication of reviewed privacy-masked result revision (\d+)\.',
                        event.description) if event else None
    revision = ProgramResultRevision.objects.filter(announcement_id=event.announcement_id,
        number=int(match[1])).first() if match else None
    if not revision:
        raise ValidationError('The published results are missing their original publication audit. Review the retained results history before ranking.')
    return revision, event.occurred_at


def from_run(run):
    from .shared_weights import CONTRACT, retained
    from .revised.contracts import weight_snapshot
    from .vault_models import VaultRevision
    run.clean()
    configuration = run.configuration
    if not configuration.uses_dataset_scoring or not is_composite(configuration.policy):
        raise ValidationError('The published ranking uses a different retained EWAF method.')
    selected = retained(run.snapshot, configuration)
    if selected is not None:
        return selected
    # Older dataset bindings retain the Vault ID in validation, without a
    # direct vault_revision FK. Both formats have already passed run.clean().
    approval = VaultRevision.objects.filter(pk=configuration.validation.get('weight_version')).first()
    if approval is None:
        raise ValidationError('The published ranking is missing its retained approved weight version.')
    return {'contract': CONTRACT, 'method': COMPOSITE, **weight_snapshot(approval, COMPOSITE)}


def publication_weights(program, revision, at):
    """Resolve actual selection rankings at publication, never today's ranking.

    Recorded results can deliberately publish selections from an earlier run even
    after a newer calculation. Their selected decisions determine the weights.
    Strict result publication already validates its current ranking instead.
    """
    from .operational_models import OperationalConfiguration, OperationalDecision, OperationalRun
    payload = revision.public_payload
    runs = OperationalRun.objects.filter(program=program, recorded_at__lte=at).select_related(
        'configuration__vault_revision')
    if payload.get('publication_mode') == 'recorded':
        references = {row['reference'] for row in payload.get('rows', []) if row.get('status') == 'Selected'}
        decisions = OperationalDecision.objects.filter(program=program, recorded_at__lte=at,
            application__public_reference__in=references).select_related('application', 'previous').prefetch_related('run').order_by(
                'application_id', '-revision')
        latest = {}
        for decision in decisions:
            latest.setdefault(decision.application_id, decision)
        run_ids = set()
        for decision in latest.values():
            decision.clean()
            if decision.outcome == 'SELECTED':
                run_ids.add(decision.run_id)
        if run_ids:
            selected = [from_run(run) for run in runs.filter(pk__in=run_ids)]
            if len(selected) != len(run_ids):
                raise ValidationError('A published selection is missing its original ranking history.')
            if any(value != selected[0] for value in selected[1:]):
                raise ValidationError('These selected results use different EWAF weight versions. Review one ranking and confirm its selections before publishing results.')
            return selected[0]
    run = runs.first()
    if run:
        return from_run(run)
    # Recorded applicant lists can be published before any ranking. Retain the
    # approval available then; never substitute a subsequent Vault approval.
    configuration = OperationalConfiguration.objects.filter(program=program, recorded_at__lte=at).first()
    if not configuration or not is_composite(configuration.policy):
        raise ValidationError('The published results have no retained composite EWAF weight basis. Review the program configuration history.')
    from .vault_models import VaultRevision
    from .shared_weights import CONTRACT
    from .revised.contracts import weight_snapshot
    for approval in VaultRevision.objects.filter(status='LOCKED', recorded_at__lte=at):
        if method_of(approval.policy) == COMPOSITE:
            return {'contract': CONTRACT, 'method': COMPOSITE, **weight_snapshot(approval, COMPOSITE)}
    raise ValidationError('The published results have no retained approved weights.')


def locked_weights(program):
    if not publication_locked(program):
        return None
    revision, at = first_publication(program)
    return publication_weights(program, revision, at)


def validate_publication(item, at):
    """Called inside the existing publication transaction and terms lock."""
    from .operational_models import OperationalConfiguration
    configuration = OperationalConfiguration.objects.filter(program_id=item.program_id).first()
    if not item.program.ewaf_applicable or not configuration or not is_composite(configuration.policy):
        return
    selected = publication_weights(item.program, item.result_revision, at)
    locked = locked_weights(item.program)
    if locked is not None and selected != locked:
        raise ValidationError('Results already published for this program retain their original ranking weights. Generate a ranking with those weights and review the selections before republishing.')
