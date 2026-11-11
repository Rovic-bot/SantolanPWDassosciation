"""Program defaults and existing release controls behind one explicit POST."""
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from programs.models import Program
from programs.testsupport import close_non_ewaf_program
from . import services, tests as fixtures
from .models import AssistanceLog, AssistanceRelease


class ReceiptButtonTests(TestCase):
    setUp = fixtures.AssistanceTests.setUp
    review = fixtures.AssistanceTests.review
    approve = fixtures.AssistanceTests.approve

    def data(self, **changes):
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        return {'version': self.application.version, 'program_version': self.program.version,
                'claimant_type': 'beneficiary', 'beneficiary_identity_verified': True,
                'receipt_confirmed': True, **changes}

    def record(self, **changes):
        return services.record_actual_receipt(self.application.pk, user=self.admin, data=self.data(**changes))

    def test_one_post_uses_program_values_today_and_retains_selection_audit(self):
        self.approve()
        before = services.case_snapshot(self.application.assistance_case)
        url = reverse('assistance:release', args=[self.application.pk])
        response = self.client.post(url, self.data(amount='99999', benefit='FORGED BENEFIT',
            notes='FORGED NOTES', released_on='2999-01-01', confirm=False), follow=True)
        self.assertContains(response, 'Actual receipt recorded')
        self.assertContains(response, 'Recorded')
        self.assertNotContains(response, 'Review application')
        self.assertNotContains(response, 'Record decision')
        release = AssistanceRelease.objects.get()
        self.assertEqual(release.assistance_type, self.program.assistance_type)
        self.assertEqual(release.benefit, self.program.benefit or f'Assistance for {self.program.name}')
        self.assertEqual(release.amount, self.program.amount)
        self.assertEqual(release.released_on, timezone.localdate())
        self.assertIsNone(release.estimated_value)
        self.assertEqual(release.reference, '')
        self.assertNotIn('FORGED', release.notes)
        self.assertIn(self.program.name, release.notes)
        self.assertEqual(release.approval_snapshot['recording_method'], 'program_receipt_button')
        self.assertEqual(release.recorded_by_id, self.admin.pk)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'COMPLETED')
        self.assertEqual(services.case_snapshot(self.application.assistance_case), before)
        self.assertEqual(services.previous_assistance_count(self.member), 1)
        self.assertEqual(AssistanceLog.objects.filter(action='assistance_released').count(), 1)

    def test_empty_benefit_uses_program_title_and_zero_amount_is_retained(self):
        self.program.benefit = ''
        self.program.amount = Decimal('0.00')
        self.program.save(update_fields=['benefit', 'amount'])
        self.approve()
        release = self.record()
        self.assertEqual(release.benefit, f'Assistance for {self.program.name}')
        self.assertEqual(release.amount, Decimal('0.00'))

    def test_get_head_csrf_and_permissions_cannot_record_receipts(self):
        self.approve()
        url = reverse('assistance:release', args=[self.application.pk])
        for method in (self.client.get, self.client.head):
            self.assertEqual(method(url).status_code, 200)
        self.assertContains(self.client.post(url, {}, follow=True), 'Receipt has not been recorded')
        self.assertFalse(AssistanceRelease.objects.exists())
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(url, self.data()).status_code, 403)
        grant(self.viewer, 'assistance.view_assistancerelease')
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(url, self.data()).status_code, 403)
        table = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(table, 'View only')
        self.assertNotContains(table, 'class="receipt-action-form"')
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_selection_and_active_membership_are_still_required(self):
        with self.assertRaises(ValidationError):
            self.record()
        table = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(table, 'disabled aria-describedby=')
        self.assertNotContains(table, 'class="receipt-action-form"')
        self.approve()
        self.member.is_active = False
        self.member.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            self.record()
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_stale_versions_and_duplicate_clicks_do_not_add_receipts(self):
        self.approve()
        data = self.data()
        for changes in ({'version': data['version'] + 1}, {'program_version': data['program_version'] + 1}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.record(**changes)
        self.record()
        with self.assertRaises(ValidationError):
            services.record_actual_receipt(self.application.pk, user=self.admin, data=data)
        with self.assertRaises(ValidationError):
            self.record()
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertEqual(AssistanceLog.objects.filter(action='assistance_released').count(), 1)

    def test_program_changed_after_defaults_were_read_is_rechecked_under_lock(self):
        self.approve()
        original = services.record_release
        def change_before_lock(*args, **kwargs):
            Program.objects.filter(pk=self.program.pk).update(version=self.program.version + 1)
            return original(*args, **kwargs)
        with patch('assistance.services.record_release', side_effect=change_before_lock):
            with self.assertRaisesMessage(ValidationError, 'This record changed'):
                self.record()
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_audit_failure_rolls_back_receipt_and_application(self):
        self.approve()
        with patch('assistance.services.record_log', side_effect=ValidationError('Synthetic audit failure')):
            with self.assertRaisesMessage(ValidationError, 'Synthetic audit failure'):
                self.record()
        self.assertFalse(AssistanceRelease.objects.exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'SELECTED')
        self.assertEqual(services.previous_assistance_count(self.member), 0)


class ReceiptButtonConcurrencyTests(TransactionTestCase):
    setUp = fixtures.AssistanceConcurrencyTests.setUp
    race = fixtures.AssistanceConcurrencyTests.race

    def test_simultaneous_buttons_record_one_receipt(self):
        close_non_ewaf_program(self.program, self.admin)
        services.decide_assistance(self.application.pk, user=self.admin, data=fixtures.decision_data(self.application))
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.admin)
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        data = {'version': self.application.version, 'program_version': self.program.version,
                'claimant_type': 'beneficiary', 'beneficiary_identity_verified': True, 'receipt_confirmed': True}
        results = self.race([lambda: services.record_actual_receipt(
            self.application.pk, user=self.admin, data=data)] * 2)
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertEqual(AssistanceLog.objects.filter(action='assistance_released').count(), 1)
