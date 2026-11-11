"""An audited Eligible confirmation must not create a second input-review step."""
from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceLog
from assistance.services import review_eligibility, record_release
from assistance.tests import review_data, release_data
from . import operational_services as operational
from . import test_composite_ses as documents, test_member_record_evidence as records
from .operational_models import OperationalRun, OperationalDecision
from .revised.live_models import DatasetInputReview
from .revised import live_evidence
from .ranking_freshness import eligibility_recheck


class EligibleReadinessChecks:
    def recheck(self, application, **changes):
        review_eligibility(application.pk, user=self.user, direct_review=True,
            data=review_data(application, notes='Synthetic direct Eligible confirmation.', **changes))
        application.refresh_from_db()

    def current(self, run):
        with operational.fence(self.program.pk, self.user) as (actor, program, apps):
            return operational.current_result_run(program, apps, actor, run.pk)

    def test_direct_eligible_is_ready_before_first_ranking_without_another_input_review(self):
        a, _ = self.pool()
        retained = list(DatasetInputReview.objects.order_by('pk').values())
        self.recheck(a)
        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]), {'review': a.pk})
        self.assertTrue(page.context['ready'])
        self.assertFalse(page.context['selected_input']['needs_review'])
        self.assertEqual(page.context['ready_count'], 2)
        self.assertEqual(page.context['pending_count'], 0)
        run = self.generate()
        run.clean()
        self.assertEqual(len(run.calculations), 2)
        self.assertEqual(list(DatasetInputReview.objects.order_by('pk').values()), retained)
        self.assertFalse(OperationalDecision.objects.exists())

    def test_repeated_eligible_keeps_ranking_and_explicit_selection_then_release(self):
        a, _ = self.pool()
        run = self.generate()
        retained = deepcopy(run.payload())
        original_review = DatasetInputReview.objects.filter(application=a).first()
        self.recheck(a)
        self.recheck(a)
        self.assertEqual(self.current(run).pk, run.pk)
        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]), {'review': a.pk})
        self.assertTrue(page.context['result']['active'])
        self.assertFalse(page.context['selected_input']['needs_review'])
        self.assertFalse(any(row['needs_review'] for row in page.context['result']['rows']))
        decision = operational.record_decision(self.program.pk, user=self.user, run_id=run.pk,
            application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic explicit selection.')
        self.assertEqual(len(decision.review['eligibility_rechecks'][0]['reviews']), 2)
        decision.clean()
        record_release(a.pk, user=self.user, data=release_data(a))
        self.assertEqual(self.current(run).pk, run.pk)
        self.assertEqual(DatasetInputReview.objects.filter(application=a).first().pk, original_review.pk)
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)
        self.assertEqual(OperationalRun.objects.count(), 1)

    def test_changed_information_and_broken_audit_are_not_identical_rechecks(self):
        a, _ = self.pool()
        review = DatasetInputReview.objects.filter(application=a).first()
        self.recheck(a)
        current = live_evidence.context(a)
        self.assertTrue(eligibility_recheck(review.source, current))
        for key in ('profile_digest', 'member_version', 'program_version'):
            changed = deepcopy(current)
            changed[key] = 'synthetic-changed-value'
            self.assertIsNone(eligibility_recheck(review.source, changed))
        changed = deepcopy(current)
        changed['case']['checklist'][0]['result'] = 'review'
        self.assertIsNone(eligibility_recheck(review.source, changed))
        log = AssistanceLog.objects.filter(application=a, action='eligibility_reviewed').first()
        broken = deepcopy(log.snapshot)
        broken['before']['review_notes'] = 'Synthetic broken chain'
        with patch.object(AssistanceLog.objects, 'filter', wraps=AssistanceLog.objects.filter):
            AssistanceLog.objects.filter(pk=log.pk).update(snapshot=broken)
        with self.assertRaises(ValidationError):
            live_evidence.accepted(a, self.configuration, live_evidence.context(a))


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DocumentEligibleReadinessTests(EligibleReadinessChecks, TransactionTestCase):
    setUp = documents.CompositeSesWorkflowTests.setUp
    draft = documents.CompositeSesWorkflowTests.draft
    approve = documents.CompositeSesWorkflowTests.approve
    bind = documents.CompositeSesWorkflowTests.bind
    publish = documents.CompositeSesWorkflowTests.publish
    generate = documents.CompositeSesWorkflowTests.generate
    applicant = documents.CompositeSesWorkflowTests.applicant
    accept = documents.CompositeSesWorkflowTests.accept

    def pool(self):
        a, _, b, _ = documents.CompositeSesWorkflowTests.pool(self)
        return a, b


class MemberRecordEligibleReadinessTests(DocumentEligibleReadinessTests):
    setUp = records.MemberRecordEvidenceTests.setUp
    applicant = records.MemberRecordEvidenceTests.applicant
    findings = records.MemberRecordEvidenceTests.findings
    accept = records.MemberRecordEvidenceTests.accept

    def pool(self):
        self.publish()
        a, b = self.applicant('ELIGIBLE-A'), self.applicant('ELIGIBLE-B', prior=True)
        self.accept(a, low=True)
        self.accept(b)
        return a, b
