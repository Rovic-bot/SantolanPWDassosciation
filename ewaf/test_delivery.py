from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TransactionTestCase
from assistance.services import record_release, reserved_slots
from assistance.tests import release_data
from assistance.models import AssistanceRelease
from programs.models import ProgramApplication
from .operational_testsupport import OperationalHelpers
from .operational_models import OperationalDecision


class OperationalDeliveryTests(OperationalHelpers, TransactionTestCase):
    def choose(self, *args, **kwargs):
        decision = super().choose(*args, **kwargs)
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.officer)
        return decision

    def setUp(self):
        from programs.tests import create_program
        with patch('ewaf.evidence_testsupport.create_program', side_effect=lambda **values: create_program(slots=2, **values)):
            self.setup_operational(additional=1)
        self.lock_policy()
        self.run = self.calculate()

    def test_saved_selection_releases_once_and_preserves_scores(self):
        decision = self.choose(self.run)
        self.assertEqual(reserved_slots(self.program), 1)
        before = self.run.calculations
        receipt = record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.assertEqual(receipt.approval_snapshot['operational_decision_id'], decision.pk)
        self.assertEqual(receipt.approval_snapshot['operational_run_id'], self.run.pk)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'COMPLETED')
        with self.assertRaises(ValidationError):
            record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.run.refresh_from_db()
        self.assertEqual(self.run.calculations, before)
        self.assertEqual(AssistanceRelease.objects.count(), 1)

    def test_each_selected_member_can_receive_from_the_same_ranked_cohort(self):
        self.choose(self.run)
        second = self.helpers[1].application
        self.choose(self.run, application_id=second.pk)
        record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        record_release(second.pk, user=self.officer, data=release_data(second))
        self.assertEqual(AssistanceRelease.objects.successful().count(), 2)
        self.assertEqual(OperationalDecision.objects.count(), 2)

    def test_receipt_button_preserves_ewaf_selection_and_saved_scores(self):
        from django.urls import reverse
        decision = self.choose(self.run)
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        before = self.run.calculations
        self.client.force_login(self.officer)
        response = self.client.post(reverse('assistance:release', args=[self.application.pk]), {
            'version': self.application.version, 'program_version': self.program.version})
        self.assertEqual(response.status_code, 302)
        receipt = AssistanceRelease.objects.get()
        self.assertEqual(receipt.approval_snapshot['operational_decision_id'], decision.pk)
        self.assertEqual(receipt.approval_snapshot['operational_run_id'], self.run.pk)
        self.assertEqual(receipt.approval_snapshot['recording_method'], 'program_receipt_button')
        self.run.refresh_from_db()
        self.assertEqual(self.run.calculations, before)
        self.assertEqual(OperationalDecision.objects.count(), 1)

    def test_unselected_stale_and_audit_failure_cannot_release(self):
        with self.assertRaises(ValidationError):
            record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.choose(self.run)
        with patch('assistance.services.record_log', side_effect=ValidationError('audit failure')):
            with self.assertRaises(ValidationError):
                record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.assertFalse(AssistanceRelease.objects.exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')
        models.QuerySet.update(ProgramApplication.objects.filter(pk=self.helpers[1].application.pk), version=99)
        with self.assertRaises(ValidationError):
            record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_published_selection_survives_delivery_but_not_voiding(self):
        from announcements.generation import generation_preview, generate_results
        from announcements.results import results_current
        from assistance.services import void_release
        self.choose(self.run)
        self.choose(self.run, application_id=self.helpers[1].application.pk)
        plan = generation_preview(self.program.pk, user=self.officer)
        item = generate_results(self.program.pk, user=self.officer, expected=plan['expected'], version=plan['version'])
        original_payload = item.result_revision.public_payload.copy()
        receipt = record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.assertTrue(results_current(item))
        self.assertEqual(item.result_revision.public_payload, original_payload)
        self.application.refresh_from_db()
        void_release(self.application.pk, receipt.pk, user=self.officer,
            data={'version': self.application.version, 'notes': 'Synthetic delivery correction.', 'confirm': True})
        self.assertFalse(results_current(item))

    def test_completed_receipt_binding_and_other_source_changes_still_block_publication(self):
        from announcements.generation import generation_preview
        self.choose(self.run)
        self.choose(self.run, application_id=self.helpers[1].application.pk)
        receipt = record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        original = receipt.approval_snapshot.copy()
        models.QuerySet.update(AssistanceRelease.objects.filter(pk=receipt.pk),
            approval_snapshot={**original, 'operational_run_id': self.run.pk + 100})
        with self.assertRaises(ValidationError):
            generation_preview(self.program.pk, user=self.officer)
        models.QuerySet.update(AssistanceRelease.objects.filter(pk=receipt.pk), approval_snapshot=original)
        models.QuerySet.update(ProgramApplication.objects.filter(pk=self.helpers[1].application.pk), version=99)
        with self.assertRaises(ValidationError):
            generation_preview(self.program.pk, user=self.officer)
