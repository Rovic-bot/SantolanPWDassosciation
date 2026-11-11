"""Pending is retained; only an explicit, audited administrator message is sent."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import smtplib
import uuid

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.referral_connection import EmailConnectionRequired
from assistance.referral_models import ReferralSettings, referral_write
from members.models import Member
from .models import MembershipApplication
from .pending_email import send_pending_email, deliver_pending_email, retry_pending_email
from .pending_email_models import MembershipPendingEmail as Email, MembershipPendingEmailAttempt as Attempt
from .test_registration_decisions import DecisionHelpers
from .test_registration_intake import staff


class PendingHelpers(DecisionHelpers):
    invited_by_default = False
    def setup_pending(self):
        self.setup_decisions()
        self.intake = self.make()
        self.client.force_login(self.actor)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []
        self.values = {'version': self.intake.version, 'request_key': uuid.uuid4(),
            'reason': 'Please bring a clear copy of your PWD ID.\nVisit the Help Desk for assistance.'}

    def send(self, **changes):
        return send_pending_email(self.intake.reference, user=self.actor, **(self.values | changes))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PendingEmailTests(PendingHelpers, TestCase):
    def setUp(self):
        self.setup_pending()

    def test_commit_delivery_and_repeat_request_keep_pending_without_changing_submission(self):
        before = self.intake.revisions.get().data
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            job = self.send()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(self.send().pk, job.pk)
        self.assertFalse(deliver_pending_email(job.pk))
        self.intake.refresh_from_db()
        self.assertIsNone(self.intake.membership_application_id)
        self.assertEqual(self.intake.state, 'received')
        self.assertEqual(self.intake.current_revision, 1)
        self.assertEqual(self.intake.revisions.get().data, before)
        self.assertFalse(Member.objects.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [before['email']])
        self.assertIn(self.values['reason'], mail.outbox[0].body)
        self.assertIn('still pending', mail.outbox[0].body)
        for private in (before['pwd_number'], before['birthdate'], before['household_monthly_income']):
            self.assertNotIn(private, mail.outbox[0].body)
        self.assertEqual(Attempt.objects.count(), 1)
        action = self.intake.actions.get(action='pending_email_requested')
        self.assertEqual(action.reason, self.values['reason'])
        self.assertEqual(action.version_after, action.version_before + 1)

    def test_permissions_stale_version_final_decision_invalid_and_missing_recipient_block(self):
        viewer = staff('synthetic_pending_viewer')
        with self.assertRaises(PermissionDenied):
            send_pending_email(self.intake.reference, user=viewer, **self.values)
        for changes in ({'version': 900}, {'reason': ' '}, {'reason': 'x' * 2001}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.send(**changes)
        with patch('membership.pending_email.validate_email', side_effect=ValidationError('Missing')):
            with self.assertRaisesMessage(ValidationError, 'valid saved email'):
                self.send()
        self.decide(self.intake, self.data(self.intake, action='decline_registration'))
        with self.assertRaisesMessage(ValidationError, 'final decision'):
            self.send()
        self.assertFalse(Email.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_audit_failure_rolls_back_outbox_version_and_callback(self):
        with self.captureOnCommitCallbacks(execute=True), patch('membership.pending_email.registration.record_action', side_effect=ValidationError('Audit failure')):
            with self.assertRaises(ValidationError):
                self.send()
        self.intake.refresh_from_db()
        self.assertEqual(self.intake.version, self.values['version'])
        self.assertFalse(Email.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_known_failure_can_retry_same_message_without_changing_pending(self):
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            job = self.send()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        body, recipient = job.body, job.recipient
        with self.captureOnCommitCallbacks(execute=True):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        job.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 2))
        self.assertEqual((job.body, job.recipient), (body, recipient))
        self.assertEqual(len(mail.outbox), 1)
        with self.assertRaises(ValidationError):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        self.assertFalse(Member.objects.exists())

    def test_uncertain_send_cannot_be_retried(self):
        with patch('membership.approval_email.EmailMessage.send', side_effect=TimeoutError('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            job = self.send()
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        with self.assertRaisesMessage(ValidationError, 'unconfirmed'):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        self.assertFalse(deliver_pending_email(job.pk))
        self.assertEqual(Attempt.objects.count(), 1)

    def test_connection_failure_reason_is_visible_and_quit_does_not_undo_retry(self):
        with patch('django.core.mail.backends.locmem.EmailBackend.open',
                   side_effect=smtplib.SMTPServerDisconnected('private diagnostic')), \
                self.captureOnCommitCallbacks(execute=True):
            job = self.send()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        page = self.client.get(reverse('membership:registration_detail', args=[self.intake.reference]))
        self.assertContains(page, 'mail server connection failed')
        self.assertNotContains(page, 'private diagnostic')
        with patch('django.core.mail.backends.locmem.EmailBackend.close',
                   side_effect=smtplib.SMTPServerDisconnected('Synthetic QUIT')), \
                self.captureOnCommitCallbacks(execute=True):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        job.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 2))
        self.assertFalse(deliver_pending_email(job.pk))

    def test_queued_message_is_cancelled_if_application_was_declined(self):
        job = self.send()
        self.intake.refresh_from_db()
        self.decide(self.intake, self.data(self.intake, action='decline_registration'))
        self.assertFalse(deliver_pending_email(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.state, 'cancelled')
        self.assertEqual(mail.outbox, [])

    def test_post_sends_only_saved_address_and_invalid_message_reopens_dialog(self):
        url = reverse('membership:registration_detail', args=[self.intake.reference])
        response = self.client.post(url, self.values | {'action': 'send_pending_email', 'reason': ''})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'data-open-on-load', status_code=400)
        self.assertFalse(Email.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, self.values | {'action': 'send_pending_email', 'email': 'tampered@example.invalid'})
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(Email.objects.get().recipient, 'tampered@example.invalid')
        response = self.client.get(url)
        self.assertContains(response, 'Pending review')
        self.assertContains(response, self.values['reason'].splitlines()[0])
        self.assertFalse(Member.objects.exists())

    def test_private_iframe_preview_requires_permission_and_records_access(self):
        url = reverse('membership:registration_form', args=[self.intake.reference, 1]) + '?preview=1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTemplateUsed(response, 'membership/registration/preview_base.html')
        self.assertContains(response, 'association-print-form')
        self.assertTrue(self.intake.actions.filter(action='staff_completed_form_viewed').exists())
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b'association-print-form', response.content)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PendingEmailConcurrencyTests(PendingHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_pending()

    def test_concurrent_identical_send_requests_send_once(self):
        barrier = Barrier(2)
        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.send().pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            jobs = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(jobs[0], jobs[1])
        self.assertEqual(Email.objects.count(), 1)
        self.assertEqual(Attempt.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(MembershipApplication.objects.exists())
