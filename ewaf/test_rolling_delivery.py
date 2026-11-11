"""Same-day fulfillment must not make an open ranking lose its recipients."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceLog, AssistanceRelease
from assistance import services as assistance
from programs.models import ProgramApplication
from programs.tests import program_data
from . import test_rolling_pool as fixtures, operational_services as service
from .operational_models import OperationalDecision


class RollingDeliveryFixture:
    draft = fixtures.RollingPoolTests.draft
    approve = fixtures.RollingPoolTests.approve
    bind = fixtures.RollingPoolTests.bind
    publish = fixtures.RollingPoolTests.publish
    applicant = fixtures.RollingPoolTests.applicant
    generate = fixtures.RollingPoolTests.generate
    pool = fixtures.RollingPoolTests.pool

    def setup_delivery(self, slots=2):
        from django.apps import apps
        # Django retains default callables at import. Make those defaults use
        # the same patched clock as services so approval/receipt dates agree.
        clock = timezone.now
        for model in apps.get_models():
            for field in model._meta.local_fields:
                if isinstance(field, models.DateTimeField) and field.default is clock:
                    default_clock = patch.object(field, '_get_default', lambda: timezone.now())
                    default_clock.start()
                    self.addCleanup(default_clock.stop)
        # Keep same-day receipt tests away from midnight regardless of run time.
        setup_at = timezone.now().replace(hour=1, minute=0, second=0, microsecond=0)
        with patch('django.utils.timezone.now', return_value=setup_at), patch(
                'programs.tests.program_data', side_effect=lambda **values: program_data(**(values | {'slots': slots}))):
            fixtures.RollingPoolTests.setUp(self)

    def selected_pool(self):
        a, b = self.pool()
        run = self.generate()
        for app in (a, b):
            service.record_decision(self.program.pk, user=self.user, run_id=run.pk, application_id=app.pk,
                expected_revision=0, outcome='SELECTED', reason='SYNTHETIC explicit selection before delivery')
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.user)
        return a, b, run

    def receipt_data(self, app):
        app.refresh_from_db()
        self.program.refresh_from_db()
        return {'version': app.version, 'program_version': self.program.version}

    def record(self, app):
        return assistance.record_actual_receipt(app.pk, user=self.user, data=self.receipt_data(app))


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class RollingDeliveryTests(RollingDeliveryFixture, TransactionTestCase):
    setUp = RollingDeliveryFixture.setup_delivery

    def test_two_sequential_same_day_receipt_posts_keep_ranking_and_selection_history(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, run = self.selected_pool()
            retained = deepcopy(run.payload())
            decisions = list(OperationalDecision.objects.filter(program=self.program).values())
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=5)):
            for app in (a, b):
                page = self.client.post(reverse('assistance:release', args=[app.pk]), self.receipt_data(app), follow=True)
                self.assertContains(page, 'Actual receipt recorded')
                self.assertNotContains(page, 'Receipt was not recorded')
                self.assertNotContains(page, 'APPLICATION_NOT_CANDIDATE')
                app.refresh_from_db()
                self.assertEqual(app.status, 'COMPLETED')
                receipt = AssistanceRelease.objects.get(application=app)
                self.assertEqual(receipt.released_on, timezone.localdate(run.recorded_at))
                self.assertGreater(receipt.recorded_at, run.recorded_at)
            self.assertEqual(AssistanceRelease.objects.filter(application__program=self.program).count(), 2)
            self.assertEqual(AssistanceLog.objects.filter(application__program=self.program, action='assistance_released').count(), 2)
            with service.fence(self.program.pk, self.user) as (actor, program, applications):
                service.current_result_run(program, applications, actor, run.pk)
            with self.assertRaises(ValidationError):
                self.record(a)
            run.refresh_from_db(); run.clean()
            self.assertEqual(run.payload(), retained)
            self.assertEqual(list(OperationalDecision.objects.filter(program=self.program).values()), decisions)

    def test_receipts_survive_advancing_rolling_cutoffs_and_final_reranking(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, first = self.selected_pool()
            retained = deepcopy(first.payload())
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=5)):
            receipt = self.record(a)
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=10)):
            second = self.generate()
            for app in (a, b):
                for key in ('score_exact', 'comparison'):
                    self.assertEqual(second.calculations[str(app.pk)][key], first.calculations[str(app.pk)][key])
            self.assertEqual(second.snapshot['eligible'][str(a.pk)]['inputs']['PA']['value'], '0')
            service.record_decision(self.program.pk, user=self.user, run_id=second.pk, application_id=b.pk,
                expected_revision=1, outcome='SELECTED', reason='SYNTHETIC confirm selection on current ranking')
            self.record(b)
            before = list(AssistanceRelease.objects.filter(application__program=self.program).values())
        with patch('django.utils.timezone.now', return_value=self.cutoff + timedelta(hours=1)):
            final = self.generate()
            for app in (a, b):
                for key in ('score_exact', 'comparison'):
                    self.assertEqual(final.calculations[str(app.pk)][key], first.calculations[str(app.pk)][key])
            self.assertEqual(set(final.calculations), {str(a.pk), str(b.pk)})
            manifest = next(row for row in final.snapshot['manifest'] if row['application'] == str(a.pk))
            self.assertEqual(manifest['source']['status'], 'ELIGIBLE')
            self.assertEqual(manifest['current_source']['status'], 'COMPLETED')
            self.assertEqual(manifest['post_cutoff_receipts'][0]['release'], str(receipt.pk))
            self.assertEqual(before, list(AssistanceRelease.objects.filter(application__program=self.program).values()))
            first.refresh_from_db(); first.clean()
            self.assertEqual(first.payload(), retained)

    def test_receipt_or_audit_corruption_cannot_allow_the_next_delivery(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, run = self.selected_pool()
            receipt = self.record(a)
            # Corruption fixtures are restricted to the disposable test database.
            changes = (
                lambda: models.QuerySet.update(AssistanceRelease.objects.filter(pk=receipt.pk), approval_snapshot={}),
                lambda: models.QuerySet.update(AssistanceLog.objects.filter(application=a, action='assistance_released'), actor_id=None),
                lambda: models.QuerySet.update(AssistanceRelease.objects.filter(pk=receipt.pk), released_on=receipt.released_on - timedelta(days=1)),
                lambda: models.QuerySet.update(ProgramApplication.objects.filter(pk=a.pk), version=99),
            )
            for change in changes:
                with self.subTest(change=change), transaction.atomic():
                    change()
                    with self.assertRaises(ValidationError):
                        self.record(b)
                    self.assertEqual(AssistanceRelease.objects.filter(application__program=self.program).count(), 1)
                    transaction.set_rollback(True)

    def test_changed_member_information_and_voids_still_block_delivery(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, run = self.selected_pool()
            receipt = self.record(a)
            with transaction.atomic():
                a.member.household_members += 1
                a.member.save(update_fields=['household_members'])
                with self.assertRaises(ValidationError):
                    self.record(b)
                transaction.set_rollback(True)
            a.refresh_from_db()
            assistance.void_release(a.pk, receipt.pk, user=self.user,
                data={'version': a.version, 'notes': 'SYNTHETIC void requires renewed review', 'confirm': True})
            with self.assertRaises(ValidationError):
                self.record(b)
            self.assertFalse(AssistanceRelease.objects.filter(application=b).exists())

    def test_same_day_other_program_receipt_is_not_own_fulfillment(self):
        from assistance.tests import review_data, decision_data, release_data
        from programs.tests import create_program
        from programs.testsupport import application_fixture
        from .revised import automatic_inputs, live_evidence, rolling_pool, fulfillment
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, run = self.selected_pool()
            other = create_program(registration_opens_at=self.base - timedelta(days=2),
                registration_closes_at=self.base - timedelta(days=1))
            other_app = application_fixture(other, a.member)
            assistance.review_eligibility(other_app.pk, user=self.user, data=review_data(other_app))
            assistance.decide_assistance(other_app.pk, user=self.user, data=decision_data(other_app))
            from announcements.testsupport import publish_selection
            publish_selection(other, self.user)
            assistance.record_release(other_app.pk, user=self.user, data=release_data(other_app))
            config = rolling_pool.from_snapshot(run.snapshot, run.configuration)
            source = live_evidence.context(a)
            source['member_record_inputs'] = automatic_inputs.member_values(a.member)
            projected, witnesses = fulfillment.project(a, config, source, run)
            self.assertEqual(projected, source)
            self.assertEqual(witnesses, [])
            with self.assertRaises(ValidationError):
                self.record(b)
            self.assertFalse(AssistanceRelease.objects.filter(application__program=self.program).exists())
