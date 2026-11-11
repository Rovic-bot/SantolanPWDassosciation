"""Reassess current eligibility without undoing an audited assistance receipt."""
from copy import deepcopy

from django.core.exceptions import ValidationError

from ewaf.evidence import canonical, digest


CONTRACT = 'completed-eligibility-reassessment-v1'


def completed_receipt(application):
    """Only the current member-record ranking workflow can reassess a recipient."""
    from ewaf.operational_models import OperationalConfiguration
    from ewaf.revised.rolling_pool import enabled
    from ewaf.revised.fulfillment import verified_receipt

    configuration = OperationalConfiguration.objects.filter(program=application.program).first()
    if (application.status != 'COMPLETED' or not configuration
            or configuration.status != 'LOCKED' or not enabled(configuration.policy)):
        raise ValidationError('This application is not available for a completed-recipient eligibility review.')
    receipt = application.assistance_releases.successful().select_related('application__program').first()
    if receipt is None:
        raise ValidationError('The completed application needs its recorded assistance receipt reviewed first.')
    witness, decision = verified_receipt(receipt)
    if decision is None:
        raise ValidationError('The original EWAF selection must be verified before reassessment.')
    return receipt, witness


def review_witness(application, witness):
    return {'contract': CONTRACT, 'receipt': witness,
            'application_version': application.version,
            'member_version': application.member.version,
            'program_version': application.program.version}


def reviewed_completion(application, source):
    """Project a new human review for ranking; keep the actual status Completed.

    An old review cannot clear a later record edit. Current evidence/eligibility
    checks still run on the projected source. The original selection, receipt,
    and calculations are never rewritten or used as approval for another release.
    """
    from .models import AssistanceLog

    if application.status != 'COMPLETED':
        return None
    log = AssistanceLog.objects.filter(application=application, action='eligibility_reviewed').first()
    if not log or 'completed_reassessment' not in log.snapshot:
        return None
    receipt, witness = completed_receipt(application)
    case = application.assistance_case
    return _reviewed_source(application, source, case, log, receipt, witness)


def _reviewed_source(application, source, case, log, receipt, witness):
    from .models import AssistanceRelease
    from .services import case_snapshot
    from ewaf.revised.fulfillment import FIELDS

    if (log.snapshot['completed_reassessment'] != review_witness(application, witness)
            or log.snapshot.get('after') != case_snapshot(case)
            or not source['case']['log_matches'] or not case.eligibility.is_active
            or case.member_version != application.member.version
            or case.program_version != application.program.version
            or case.decision != 'pending' or not log.actor_id
            or log.actor_id != case.reviewed_by_id or log.notes != case.review_notes
            or not receipt.recorded_at <= case.reviewed_at <= log.occurred_at
            or case.eligibility_id not in ('eligible', 'review', 'ineligible')):
        return None
    projected = deepcopy(source)
    projected['status'] = {'eligible': 'ELIGIBLE', 'review': 'NEEDS_INFORMATION',
                           'ineligible': 'INELIGIBLE'}[case.eligibility_id]
    # This program's own fulfillment remains excluded, as in the original
    # post-delivery ranking. Other actual receipts use the current ledger.
    releases = list(AssistanceRelease.objects.filter(application__member_id=application.member_id)
        .exclude(pk=receipt.pk).order_by('pk').values(*FIELDS))
    projected['pa'] = {'scope': source['pa']['scope'],
        'successful': canonical([row for row in releases if row['voided_at'] is None]),
        'all_release_state_digest': digest(releases),
        'count': sum(row['voided_at'] is None for row in releases)}
    return projected, [{**witness, 'eligibility_reassessment': log.pk,
                        'review_digest': digest(log.snapshot)}]
