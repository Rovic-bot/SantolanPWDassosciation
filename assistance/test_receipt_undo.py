from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from ewaf.operational_testsupport import OperationalHelpers
from .test_claimant_receipt import ClaimantReceiptTests as Fixture
from .models import AssistanceRelease, AssistanceLog
from .services import previous_assistance_count


class ReceiptUndoTests(OperationalHelpers, TestCase):
    setUp = Fixture.setUp
    approve = Fixture.approve
    data = Fixture.data
    record = Fixture.record

    def prepare(self):
        self.approve()
        self.release = self.record()
        self.application.refresh_from_db()
        self.url = reverse('assistance:undo_receipt', args=[self.application.pk, self.release.pk])
        self.payload = {'version': self.application.version, 'confirm': '1'}

    def test_undo_keeps_history_excludes_count_and_does_not_repeat(self):
        self.prepare()
        snapshot = self.release.approval_snapshot
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 302)
        self.release.refresh_from_db()
        self.assertIsNotNone(self.release.voided_at)
        self.assertEqual(self.release.voided_by, self.admin)
        self.assertEqual(self.release.approval_snapshot, snapshot)
        self.assertIsNone(self.release.active_application_id)
        self.assertEqual(previous_assistance_count(self.member), 0)
        self.assertEqual(AssistanceLog.objects.filter(action='release_voided').count(), 1)
        self.client.post(self.url, self.payload)
        self.assertEqual(AssistanceLog.objects.filter(action='release_voided').count(), 1)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        page = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(page, 'Not recorded')
        self.assertContains(page, 'Voided')
        self.assertNotContains(page, 'data-receipt-undo>')

    def test_undo_requires_permission_post_csrf_confirmation_current_version_and_scope(self):
        self.prepare()
        self.assertEqual(self.client.get(self.url).status_code, 405)
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.admin)
        self.assertEqual(strict.post(self.url, self.payload).status_code, 403)
        for payload in ({}, {**self.payload, 'confirm': ''}, {**self.payload, 'version': self.application.version + 1}):
            self.client.post(self.url, payload)
            self.release.refresh_from_db()
            self.assertIsNone(self.release.voided_at)
        from uuid import uuid4
        wrong = reverse('assistance:undo_receipt', args=[uuid4(), self.release.pk])
        self.assertEqual(self.client.post(wrong, self.payload).status_code, 404)
        from django.contrib.auth import get_user_model
        viewer = get_user_model().objects.create_user('undo-viewer', is_staff=True)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 403)

    def test_failed_audit_rolls_back_undo(self):
        self.prepare()
        with patch('assistance.services.record_log', side_effect=ValidationError('Audit unavailable')):
            self.client.post(self.url, self.payload)
        self.release.refresh_from_db()
        self.assertIsNone(self.release.voided_at)
        self.assertEqual(previous_assistance_count(self.member), 1)
