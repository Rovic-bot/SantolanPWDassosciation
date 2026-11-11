from copy import deepcopy
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, override_settings, Client
from django.urls import reverse

from core.email_delivery import EmailDeliveryUnconfirmed
from ewaf.operational_testsupport import OperationalHelpers
from .test_claimant_receipt import ClaimantReceiptTests as Fixture
from .models import AssistanceRelease, AssistanceLog
from .referral_models import ReferralSettings, referral_write
from . import receipt_email as email


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RepresentativeReceiptEmailTests(OperationalHelpers, TestCase):
    approve = Fixture.approve
    data = Fixture.data
    record = Fixture.record
    representative = Fixture.representative

    def setUp(self):
        Fixture.setUp(self)
        self.member.email = 'beneficiary@example.invalid'
        self.member.save(update_fields=['email'])
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []

    def test_saved_receipt_sends_after_commit_once_with_only_collection_details(self):
        self.approve()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            release = self.record(**self.representative())
            self.assertEqual(mail.outbox, [])
            self.assertEqual(email.latest(release).snapshot['state'], 'queued')
        saved = deepcopy(release.approval_snapshot)
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['beneficiary@example.invalid'])
        self.assertIn('authorized representative', message.body)
        self.assertIn('Fictional Guardian', message.body)
        self.assertIn(self.program.name, message.body)
        self.assertNotIn('Unable to travel', message.body)
        self.assertNotIn('authorization_basis', release.approval_snapshot['claimant'])
        self.assertEqual(release.approval_snapshot['claimant']['schema_version'], 3)
        self.assertFalse(email.deliver_receipt_email(release.pk))
        self.assertEqual(len(mail.outbox), 1)
        release.refresh_from_db()
        self.assertEqual(release.approval_snapshot, saved)
        self.assertIn('Test email saved', email.notification_context(release, self.admin)['label'])

    def test_failure_keeps_receipt_and_retry_sends_without_another_release(self):
        self.approve()
        with patch('assistance.receipt_email.send_message', side_effect=OSError('private provider details')):
            with self.captureOnCommitCallbacks(execute=True):
                release = self.record(**self.representative())
        self.assertEqual(email.latest(release).snapshot['state'], 'failed')
        self.assertNotIn('private provider details', str(email.latest(release).snapshot))
        url = reverse('assistance:receipt_email_retry', args=[self.application.pk, release.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url, {'confirm': '1'}).status_code, 302)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(email.latest(release).snapshot['state'], 'sent')
        with self.assertRaises(ValidationError):
            email.retry_receipt_email(release.pk, application_id=self.application.pk, user=self.admin, confirmed=True)

    def test_confirm_receipt_http_flow_sends_after_commit_without_removed_fields(self):
        self.approve()
        url = reverse('assistance:release', args=[self.application.pk])
        data = self.data(**self.representative())
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(url, data)
        release = AssistanceRelease.objects.get(application=self.application)
        receipt_url = reverse('assistance:program_releases', args=[self.program.pk])
        self.assertRedirects(response, receipt_url + f'#receipt-{self.application.pk}',
                             fetch_redirect_response=False)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(email.latest(release).snapshot['state'], 'queued')
        callbacks[0]()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['beneficiary@example.invalid'])
        self.assertIn('collected by your authorized representative', mail.outbox[0].body)
        self.assertContains(self.client.get(receipt_url), 'Test email saved')
        with self.captureOnCommitCallbacks(execute=True) as duplicate_callbacks:
            self.client.post(url, data)
        self.assertEqual(duplicate_callbacks, [])
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_uncertain_delivery_is_visible_and_never_automatically_retried(self):
        self.approve()
        with patch('assistance.receipt_email.send_message', side_effect=EmailDeliveryUnconfirmed()):
            with self.captureOnCommitCallbacks(execute=True):
                release = self.record(**self.representative())
        self.assertEqual(email.latest(release).snapshot['state'], 'uncertain')
        self.assertFalse(email.deliver_receipt_email(release.pk))
        page = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(page, 'Email delivery is unconfirmed.')
        self.assertContains(page, 'retrying could send a duplicate')
        self.assertContains(page, 'Retry email')

    def test_missing_email_is_skipped_without_blocking_receipt(self):
        self.member.email = ''
        self.member.save(update_fields=['email'])
        self.approve()
        with self.captureOnCommitCallbacks(execute=True):
            release = self.record(**self.representative())
        self.assertEqual(email.latest(release).snapshot['skip_reason'], 'missing')
        self.assertEqual(mail.outbox, [])
        self.assertTrue(AssistanceRelease.objects.filter(pk=release.pk).exists())

    def test_failed_queue_or_release_audit_rolls_back_receipt_and_never_sends(self):
        self.approve()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with patch('assistance.receipt_email.event', side_effect=RuntimeError('audit unavailable')):
                with self.assertRaises(RuntimeError):
                    self.record(**self.representative())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertFalse(AssistanceLog.objects.filter(action=email.ACTION).exists())
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_beneficiary_receipt_does_not_send_representative_notification(self):
        self.approve()
        with self.captureOnCommitCallbacks(execute=True):
            release = self.record()
        self.assertIsNone(email.latest(release))
        self.assertEqual(mail.outbox, [])

    def test_removed_controls_and_retry_permission_method_csrf_checks(self):
        self.approve()
        page = self.client.get(reverse('assistance:release', args=[self.application.pk]))
        for name in ('authorization_basis', 'representative_identity_verified', 'authorization_verified', 'verification_notes'):
            self.assertNotContains(page, f'name="{name}"')
        release = self.record(**self.representative())
        url = reverse('assistance:receipt_email_retry', args=[self.application.pk, release.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True); strict.force_login(self.admin)
        self.assertEqual(strict.post(url, {'confirm': '1'}).status_code, 403)
        with self.assertRaises(ValidationError):
            email.retry_receipt_email(release.pk, application_id=self.application.pk, user=self.admin, confirmed=False)
        from django.contrib.auth import get_user_model
        limited = get_user_model().objects.create_user('receipt-mail-viewer', is_staff=True)
        with self.assertRaises(PermissionDenied):
            email.retry_receipt_email(release.pk, application_id=self.application.pk, user=limited, confirmed=True)

    def test_voided_receipt_does_not_send_queued_notification(self):
        self.approve()
        release = self.record(**self.representative())
        # A synthetic void state exercises the mail guard without contacting SMTP.
        from django.utils import timezone
        AssistanceRelease.objects.filter(pk=release.pk).update(voided_at=timezone.now(), active_application=None)
        self.assertFalse(email.deliver_receipt_email(release.pk))
        self.assertEqual(email.latest(release).snapshot['skip_reason'], 'voided')
        self.assertEqual(mail.outbox, [])
