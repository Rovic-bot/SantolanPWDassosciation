"""New eligible applicants must not invalidate audited, completed recipients."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceLog, AssistanceRelease
from members.models import Member
from . import operational_services as service
from .operational_models import OperationalDecision
from .test_rolling_delivery import RollingDeliveryFixture


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class RecipientRerankingTests(RollingDeliveryFixture, TransactionTestCase):
    def setUp(self):
        self.setup_delivery(slots=4)

    def delivered_pool(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, run = self.selected_pool()
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=5)):
            self.record(a)
            self.record(b)
        return a, b, run

    def test_new_applicants_rerank_with_recipients_but_cannot_select_recipients_again(self):
        a, b, first = self.delivered_pool()
        retained = deepcopy(first.payload())
        receipts = list(AssistanceRelease.objects.filter(application__program=self.program).values())
        decisions = list(OperationalDecision.objects.filter(program=self.program).values())
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=10)):
            newcomer = self.applicant('ROLL-NEW-ELIGIBLE')
            response = self.client.get(url)
            self.assertTrue(response.context['ready'])
            self.assertNotContains(response, 'APPLICATION_REVIEW_UNRESOLVED')
            self.assertTrue(all(not row['needs_review'] for row in response.context['result']['rows']))
            with service.fence(self.program.pk, self.user) as (actor, program, applications):
                with self.assertRaises(ValidationError):
                    service.current_result_run(program, applications, actor, first.pk)
            second = self.generate()
            self.assertEqual(set(second.calculations), {str(app.pk) for app in (a, b, newcomer)})
            for app in (a, b):
                source = next(row for row in second.snapshot['manifest'] if row['application'] == str(app.pk))
                self.assertEqual(source['source']['status'], 'ELIGIBLE')
                self.assertEqual(source['current_source']['status'], 'COMPLETED')
                self.assertEqual(len(source['source']['dataset_program_applications']), 3)
                self.assertEqual(second.snapshot['eligible'][str(app.pk)]['inputs']['PA']['value'], '0')
                with self.assertRaisesMessage(ValidationError, 'already recorded'):
                    service.record_decision(self.program.pk, user=self.user, run_id=second.pk,
                        application_id=app.pk, expected_revision=1, outcome='SELECTED', reason='SYNTHETIC duplicate')
                with self.assertRaises(ValidationError):
                    self.record(app)
            response = self.client.get(url)
            self.assertTrue(all(not row['needs_review'] for row in response.context['result']['rows']))
            self.assertContains(response, 'Assistance received')
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=15)):
            fourth = self.applicant('ROLL-FOURTH-ELIGIBLE')
            third = self.generate()
            self.assertEqual(set(third.calculations), {str(app.pk) for app in (a, b, newcomer, fourth)})
            service.record_decision(self.program.pk, user=self.user, run_id=third.pk,
                application_id=newcomer.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC new selection')
            self.assertEqual(list(AssistanceRelease.objects.filter(application__program=self.program).values()), receipts)
            self.assertEqual(list(OperationalDecision.objects.filter(pk__in=[row['id'] for row in decisions]).values()), decisions)
            first.refresh_from_db(); first.clean()
            self.assertEqual(first.payload(), retained)

    def test_roster_growth_does_not_hide_profile_changes_invalid_audits_or_roster_removal(self):
        from .revised import automatic_inputs, fulfillment, live_evidence, rolling_pool
        a, b, run = self.delivered_pool()
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=10)):
            self.applicant('ROLL-NEW-WITH-REVIEW')
            for change in (
                lambda: models.QuerySet.update(Member.objects.filter(pk=a.member_id), household_members=99),
                lambda: models.QuerySet.update(AssistanceLog.objects.filter(application=a, action='assistance_released'), actor_id=None),
                lambda: models.QuerySet.update(AssistanceRelease.objects.filter(application=a),
                    voided_at=self.open_at, active_application=None),
            ):
                with self.subTest(change=change), transaction.atomic():
                    change()
                    with self.assertRaises(ValidationError):
                        service.context(self.program.pk, user=self.user)
                    transaction.set_rollback(True)
            a.refresh_from_db()
            source = live_evidence.context(a)
            source['member_record_inputs'] = automatic_inputs.member_values(a.member)
            source['dataset_program_applications'].remove(str(b.pk))
            config, _ = rolling_pool.assessment_configuration(run.configuration)
            projected, witnesses = fulfillment.project(a, config, source, run)
            self.assertEqual(projected, source)
            self.assertEqual(witnesses, [])
