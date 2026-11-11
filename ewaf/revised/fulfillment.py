"""Retain reviewed cutoff inputs when later, audited assistance is delivered.

This projection never edits an application, review, decision or receipt. The
live source and excluded receipts are retained in each new calculation. Only
composite-SES pools already calculated from the same accepted review may reuse
it. A later completed-recipient reassessment uses its new audited eligibility
and current inputs; other source differences continue to require review.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from ewaf.evidence import canonical, digest

CONTRACT = 'composite-post-cutoff-fulfillment-v1'
FIELDS = ('id', 'application_id', 'active_application_id', 'released_on',
          'recorded_at', 'recorded_by_id', 'assistance_type', 'voided_at', 'voided_by_id')


def verified_receipt(receipt):
    """Check native delivery audit and its retained approval, never a new approval."""
    from assistance.models import AssistanceLog
    from ewaf.operational_models import OperationalDecision
    approval = receipt.approval_snapshot
    expected = {'release': str(receipt.pk), 'assistance_type': receipt.assistance_type,
        'benefit': receipt.benefit, 'amount': str(receipt.amount) if receipt.amount is not None else None,
        'estimated_value': str(receipt.estimated_value) if receipt.estimated_value is not None else None,
        'released_on': str(receipt.released_on), 'reference': receipt.reference, 'approval': approval}
    log = AssistanceLog.objects.filter(application=receipt.application,
        action='assistance_released').first()
    observed = deepcopy(log.snapshot) if log else {}
    try:
        for key in ('amount', 'estimated_value'):
            for values in (observed, expected):
                if values.get(key) is not None:
                    values[key] = Decimal(values[key])
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('The assistance amount no longer matches its delivery audit.') from None
    if (receipt.voided_at or receipt.active_application_id != receipt.application_id
            or not log or observed != expected or log.actor_id != receipt.recorded_by_id
            or approval.get('decision') != 'approved'):
        raise ValidationError('A confirmed delivery needs review against its original assistance audit.')
    decision = None
    from programs.mandatory_ewaf import retained_receipt
    if approval.get('operational_decision_id') is not None or (
            receipt.application.program.ewaf_applicable and not retained_receipt(receipt)):
        decision = OperationalDecision.objects.filter(application=receipt.application).first()
        if (not decision or decision.outcome != 'SELECTED'
                or approval.get('operational_decision_id') != decision.pk
                or approval.get('operational_decision_digest') != decision.digest
                or approval.get('operational_run_id') != decision.run_id
                or approval.get('operational_run_digest') != decision.run.digest):
            raise ValidationError('A completed receipt no longer matches its retained beneficiary approval.')
        decision.clean()
        decision.run.clean()
    return {'release': str(receipt.pk), 'audit': log.pk, 'approval_digest': digest(approval)}, decision


def _with_expanded_roster(original, current, configuration):
    """Carry new pool membership without treating it as a recipient correction.

    Only the current-eligible workflow permits this append-only change. Keep the
    current roster in the new source so freshness still requires a new run;
    every member, evidence, receipt and eligibility field must still match.
    """
    from . import rolling_pool
    if not original or not rolling_pool.enabled(configuration.policy):
        return original
    before = original.get('dataset_program_applications')
    after = current.get('dataset_program_applications')
    if (not isinstance(before, list) or not isinstance(after, list)
            or not all(isinstance(item, str) for item in [*before, *after])
            or before != sorted(set(before)) or after != sorted(set(after))
            or not set(before) <= set(after)):
        return original
    value = deepcopy(original)
    value['dataset_program_applications'] = deepcopy(after)
    return value


def _fulfills_rolling_selection(receipt, decision, application, configuration, previous, original):
    """Recognize this application's own delivery against its saved ranking.

    A rolling observation can be on the delivery day, or advance past it during
    reranking. That fulfillment must not undo the original eligibility. Other
    programs' receipts still obey the approved history cutoff below.
    """
    from . import rolling_pool
    if (not rolling_pool.enabled(configuration.policy) or not decision
            or receipt.application_id != application.pk or original['status'] != 'ELIGIBLE'):
        return False
    approved_run = decision.run
    if (approved_run.configuration_id != configuration.pk
            or approved_run.program_id != previous.program_id
            or approved_run.revision > previous.revision
            or not approved_run.recorded_at <= decision.recorded_at <= receipt.recorded_at
            or not timezone.localdate(decision.recorded_at) <= receipt.released_on <= timezone.localdate(receipt.recorded_at)):
        return False
    approved_source = next((row['source'] for row in approved_run.snapshot['manifest']
        if row['application'] == str(application.pk)), None)
    return _with_expanded_roster(approved_source, original, configuration) == original


def project(application, configuration, source, previous):
    from assistance.models import AssistanceRelease
    from .live_models import DatasetInputReview
    from . import automatic_inputs
    from . import rolling_pool
    if rolling_pool.enabled(configuration.policy):
        from assistance.reassessment import reviewed_completion
        reassessed = reviewed_completion(application, source)
        if reassessed is not None:
            return reassessed
    if automatic_inputs.enabled(configuration.policy):
        if not previous or previous.configuration_id != configuration.pk:
            return source, []
        original = next((row['source'] for row in previous.snapshot['manifest']
            if row['application'] == str(application.pk)), None)
        if not original or source == original:
            return source, []
        original = _with_expanded_roster(original, source, configuration)
    else:
        review = DatasetInputReview.objects.filter(application=application).first()
        if not review or source == review.source or not previous:
            return source, []
        retained = previous.snapshot['eligible'].get(str(application.pk), {}).get('assessments', {}).get('dataset_review')
        if (review.state != 'ACCEPTED' or review.configuration_id != configuration.pk
                or not retained or retained['id'] != review.pk or retained['digest'] != review.digest):
            return source, []
        review.clean()
        original = review.source
    known = {row['id'] for row in original['pa']['successful']}
    additions = [row['id'] for row in source['pa']['successful'] if row['id'] not in known]
    if not additions:
        return source, []
    receipts = list(AssistanceRelease.objects.filter(pk__in=additions).select_related('application__program').order_by('pk'))
    witnesses = []
    for receipt in receipts:
        witness, decision = verified_receipt(receipt)
        after_cutoff = (receipt.released_on > timezone.localdate(configuration.assessment_cutoff)
                        and receipt.recorded_at > configuration.assessment_cutoff)
        # Only this program's audited fulfillment can cross a rolling cutoff.
        # Late recording of other earlier benefits still needs history review.
        if not after_cutoff and not _fulfills_rolling_selection(
                receipt, decision, application, configuration, previous, original):
            return source, []
        witnesses.append(witness)
    releases = list(AssistanceRelease.objects.filter(application__member_id=application.member_id)
        .exclude(pk__in=additions).order_by('pk').values(*FIELDS))
    projected = deepcopy(source)
    projected['pa'] = {'scope': source['pa']['scope'],
        'successful': canonical([row for row in releases if row['voided_at'] is None]),
        'all_release_state_digest': digest(releases),
        'count': sum(row['voided_at'] is None for row in releases)}
    own = [receipt for receipt in receipts if receipt.application_id == application.pk]
    own_transition = own and original['status'] == 'ELIGIBLE' and application.status == 'COMPLETED'
    if own_transition:
        if len(own) != 1:
            raise ValidationError('The completed application changed beyond its recorded delivery. Review it before recalculating.')
        projected['status'] = original['status']
        projected['application_version'] = application.version - 1
    if projected != original:
        from ewaf.ranking_freshness import eligibility_recheck
        if eligibility_recheck(original, projected):
            projected = deepcopy(original)
    if own_transition and projected['application_version'] != original['application_version']:
        raise ValidationError('The completed application changed beyond its recorded delivery. Review it before recalculating.')
    if projected != original:
        # Never hide a profile, eligibility, document, older receipt or review change.
        return source, []
    return projected, witnesses


def comparison(snapshot):
    """Fulfillment may advance, while the accepted scoring source stays exact."""
    value = deepcopy(snapshot)
    value.pop('evaluation_date', None)
    if value.get('assessment_source_contract') == CONTRACT:
        value.pop('assessment_source_contract')
        for row in value['manifest']:
            row.pop('current_source', None)
            row.pop('post_cutoff_receipts', None)
            row['status'] = row['source']['status']
    return value


def fulfilled_decisions(program):
    from assistance.models import AssistanceRelease
    result = {}
    for receipt in AssistanceRelease.objects.successful().filter(application__program=program).select_related('application__program'):
        _, decision = verified_receipt(receipt)
        if decision:
            result[str(receipt.application_id)] = decision
    return result
