"""Saved rankings remain usable across audited, non-scoring changes."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceLog
from assistance.services import record_release, review_eligibility
from assistance.tests import release_data, review_data
from programs.models import ProgramLog
from programs.services import record_log
from . import operational_services as operational, test_automatic_member_inputs as fixtures
from .operational_models import OperationalDecision, OperationalRun


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RankingFreshnessTests(TransactionTestCase):
    setUp = fixtures.AutomaticMemberInputsTests.setUp
    draft = fixtures.AutomaticMemberInputsTests.draft
    approve = fixtures.AutomaticMemberInputsTests.approve
    bind = fixtures.AutomaticMemberInputsTests.bind
    publish = fixtures.AutomaticMemberInputsTests.publish
    generate = fixtures.AutomaticMemberInputsTests.generate
    applicant = fixtures.AutomaticMemberInputsTests.applicant
    pool = fixtures.AutomaticMemberInputsTests.pool

    def current(self, run):
        with operational.fence(self.program.pk, self.user) as (actor, program, applications):
            return operational.current_result_run(program, applications, actor, run.pk)

    def recheck(self, application, **changes):
        review_eligibility(application.pk, user=self.user,
            data=review_data(application, notes='SYNTHETIC unchanged eligibility review.', **changes))

    def select(self, run, application):
        return operational.record_decision(self.program.pk, user=self.user,
            run_id=run.pk, application_id=application.pk, expected_revision=0,
            outcome='SELECTED', reason='SYNTHETIC explicit beneficiary selection.')

    def test_program_artwork_does_not_expire_ranking_but_other_events_still_do(self):
        self.pool()
        first = record_log(self.program, 'picture_updated', 'SYNTHETIC initial picture', user=self.user)
        run = self.generate()
        retained = deepcopy(run.payload())
        second = record_log(self.program, 'picture_updated', 'SYNTHETIC replacement picture', user=self.user)
        self.assertEqual(self.current(run).pk, run.pk)
        self.assertEqual(ProgramLog.objects.filter(pk__in=[first.pk, second.pk]).count(), 2)
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)
        record_log(self.program, 'updated', 'SYNTHETIC other program change', user=self.user)
        with self.assertRaises(ValidationError):
            self.current(run)

    def test_repeated_eligible_review_keeps_selection_enabled_without_a_new_ranking(self):
        a, _ = self.pool()
        run = self.generate()
        retained = deepcopy(run.payload())
        before = OperationalRun.objects.count()
        self.recheck(a)
        self.recheck(a)
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        page = self.client.get(url, {'run': run.pk, 'review': a.pk})
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['result']['active'])
        self.assertTrue(page.context['result']['can_decide'])
        self.assertFalse(page.context['result']['selection_waiting'])
        self.assertNotContains(page, 'Generate a current ranking before making a selection.')
        response = self.client.post(url, {'action': 'SELECT_ASSISTANCE',
            'decision-run_id': run.pk, 'decision-application_id': a.pk,
            'decision-expected_revision': 0, 'decision-tie_reason': ''})
        self.assertEqual(response.status_code, 302)
        decision = OperationalDecision.objects.get(application=a)
        self.assertEqual(decision.run_id, run.pk)
        self.assertEqual(len(decision.review['eligibility_rechecks'][0]['reviews']), 2)
        decision.clean()
        self.assertEqual(OperationalRun.objects.count(), before)
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)

    def test_rechecked_selection_can_be_released_without_recalculating_scores(self):
        a, _ = self.pool()
        run = self.generate()
        retained = deepcopy(run.payload())
        self.recheck(a)
        self.select(run, a)
        record_release(a.pk, user=self.user, data=release_data(a))
        self.assertEqual(self.current(run).pk, run.pk)
        self.assertEqual(OperationalRun.objects.filter(program=self.program).count(), 1)
        again = self.generate()
        self.assertEqual(run.calculations[str(a.pk)]['score_exact'], again.calculations[str(a.pk)]['score_exact'])
        self.assertEqual(again.snapshot['eligible'][str(a.pk)]['inputs']['PA']['value'], '0')
        run.refresh_from_db()
        run.clean()
        self.assertEqual(run.payload(), retained)

    def test_actual_input_change_still_blocks_selection_after_eligible_recheck(self):
        a, _ = self.pool()
        run = self.generate()
        self.recheck(a)
        a.member.household_monthly_income = Decimal('12500')
        a.member.save(update_fields=['household_monthly_income'])
        with self.assertRaises(ValidationError):
            self.select(run, a)
        self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())

    def test_reversed_eligibility_decision_cannot_be_treated_as_unchanged_review(self):
        a, _ = self.pool()
        run = self.generate()
        self.recheck(a, eligibility='review', other_requirements='review')
        self.recheck(a)
        with self.assertRaises(ValidationError):
            self.select(run, a)
        self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())

    def test_unexplained_application_version_change_still_blocks_selection(self):
        a, _ = self.pool()
        run = self.generate()
        a.version += 1
        a.save(update_fields=['version'])
        self.recheck(a)
        with self.assertRaises(ValidationError):
            self.select(run, a)

    def test_broken_eligibility_audit_chain_cannot_unlock_selection(self):
        a, _ = self.pool()
        run = self.generate()
        self.recheck(a)
        log = AssistanceLog.objects.filter(application=a, action='eligibility_reviewed').first()
        broken = deepcopy(log.snapshot)
        broken['before']['review_notes'] = 'SYNTHETIC unexplained preceding review'
        AssistanceLog.objects.filter(pk=log.pk).update(snapshot=broken)
        with self.assertRaises(ValidationError):
            self.select(run, a)

    def test_failed_selection_audit_rolls_back_the_decision_after_recheck(self):
        a, _ = self.pool()
        run = self.generate()
        self.recheck(a)
        before = OperationalDecision.objects.count(), ProgramLog.objects.count()
        with patch('programs.models.ProgramLog.objects.create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.select(run, a)
        self.assertEqual(before, (OperationalDecision.objects.count(), ProgramLog.objects.count()))
        self.assertEqual(self.current(run).pk, run.pk)
