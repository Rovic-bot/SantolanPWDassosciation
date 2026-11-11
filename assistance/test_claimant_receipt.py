from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from . import services
from .models import AssistanceRelease, AssistanceLog
from ewaf.operational_testsupport import OperationalHelpers


class ClaimantReceiptTests(OperationalHelpers, TestCase):
    def setUp(self):
        from programs.tests import create_program
        with patch('ewaf.evidence_testsupport.create_program',
                   side_effect=lambda **values: create_program(slots=2, **values)):
            self.setup_operational()
        self.admin = self.officer
        self.client.force_login(self.admin)

    def approve(self, publish=True):
        self.lock_policy()
        self.run = self.calculate()
        self.choose(self.run)
        if publish:
            from announcements.testsupport import publish_selection
            publish_selection(self.program, self.admin)

    def data(self, **changes):
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        return {'version': self.application.version, 'program_version': self.program.version,
                'claimant_type': 'beneficiary', 'beneficiary_identity_verified': True,
                'receipt_confirmed': True, **changes}

    def record(self, **changes):
        return services.record_actual_receipt(self.application.pk, user=self.admin, data=self.data(**changes))

    def representative(self, **changes):
        return dict(claimant_type='representative', representative_name='Fictional Guardian',
            representative_relationship='Parent', absence_reason='Unable to travel', **changes)

    def test_representative_is_private_and_retained_in_release_and_audit(self):
        self.approve()
        release = self.record(**self.representative())
        snapshot = release.approval_snapshot['claimant']
        self.assertEqual(snapshot['claimant_name'], 'Fictional Guardian')
        self.assertEqual(snapshot['beneficiary_id'], str(self.member.pk))
        self.assertEqual(snapshot['verified_by_label'], self.admin.get_username())
        self.assertEqual(AssistanceLog.objects.get(action='assistance_released').snapshot['approval']['claimant'], snapshot)
        page = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(page, 'Fictional Guardian')
        self.assertEqual(services.previous_assistance_count(self.member), 1)

    def test_missing_representative_details_or_attestations_do_not_release(self):
        self.approve()
        fields = ('representative_name', 'representative_relationship', 'absence_reason',
                  'beneficiary_identity_verified', 'receipt_confirmed')
        for field in fields:
            data = self.representative() | {field: ''}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.record(**data)
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_beneficiary_snapshot_uses_saved_identity_and_discards_representative_details(self):
        self.approve()
        release = self.record(representative_name='FORGED', verified_by_label='FORGED', beneficiary_name='FORGED')
        snapshot = release.approval_snapshot['claimant']
        self.assertEqual(snapshot['claimant_name'], self.member.full_name)
        self.assertEqual(snapshot['representative_name'], '')
        self.assertEqual(snapshot['verified_by_label'], self.admin.get_username())

    def test_invalid_http_submission_keeps_details_for_correction(self):
        self.approve()
        response = self.client.post(reverse('assistance:release', args=[self.application.pk]),
            self.data(**(self.representative() | {'absence_reason': ''})))
        self.assertContains(response, 'Receipt has not been recorded')
        self.assertContains(response, 'Fictional Guardian')
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_failed_audit_rolls_back_claimant_and_receipt(self):
        self.approve()
        with patch('assistance.services.record_log', side_effect=ValidationError('Audit unavailable')):
            with self.assertRaises(ValidationError):
                self.record(**self.representative())
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_http_requires_explicit_actual_receipt_confirmation(self):
        self.approve()
        response = self.client.post(reverse('assistance:release', args=[self.application.pk]),
            self.data(receipt_confirmed=False))
        self.assertContains(response, 'Receipt has not been recorded')
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_get_and_csrf_cannot_record_receipts(self):
        self.approve()
        url = reverse('assistance:release', args=[self.application.pk])
        self.assertContains(self.client.get(url), 'Who received the assistance?')
        self.assertEqual(self.client.head(url).status_code, 200)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(url, self.data()).status_code, 403)
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_stale_versions_and_duplicate_submissions_are_rejected(self):
        self.approve()
        data = self.data()
        for field in ('version', 'program_version'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.record(**{field: data[field] + 1})
        self.record()
        with self.assertRaises(ValidationError):
            services.record_actual_receipt(self.application.pk, user=self.admin, data=data)
        self.assertEqual(AssistanceRelease.objects.count(), 1)

    def test_publication_and_selection_still_required(self):
        with self.assertRaises(ValidationError):
            self.record(**self.representative())
        self.approve(publish=False)
        with self.assertRaises(ValidationError):
            self.record(**self.representative())
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_earlier_selection_is_blocked_before_claimant_entry_and_post(self):
        self.approve()
        self.calculate()
        url = reverse('assistance:release', args=[self.application.pk])
        for response in (self.client.get(url), self.client.post(url, self.data())):
            self.assertContains(response, 'selection belongs to an earlier EWAF calculation')
            self.assertContains(response, 'disabled aria-describedby="receipt-release-blocker"')
            self.assertContains(response, reverse('ewaf:operational_workspace', args=[self.program.pk]))
            self.assertNotContains(response, 'Review the highlighted fields')
            self.assertNotContains(response, 'Selected beneficiary')
        table = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(table, 'Selection needs review')
        self.assertNotContains(table, f'href="{url}"')
        with self.assertRaisesMessage(ValidationError, 'earlier EWAF calculation'):
            self.record()
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_reconfirmed_selection_allows_receipt_again(self):
        self.approve()
        new_run = self.calculate()
        self.choose(new_run, expected_revision=1)
        page = self.client.get(reverse('assistance:release', args=[self.application.pk]))
        self.assertNotContains(page, 'Receipt recording is on hold')
        receipt = self.record(**self.representative())
        self.assertEqual(receipt.approval_snapshot['operational_run_id'], new_run.pk)
        self.assertEqual(receipt.approval_snapshot['claimant']['claimant_type'], 'representative')
