"""Online intake requirements and private post-commit Gmail approval notices."""
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import smtplib

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.referral_connection import EmailConnectionRequired
from assistance.referral_models import ReferralSettings, referral_write
from members.models import Member
from .approval_email import deliver_approval_email, retry_approval_email
from .approval_email_models import MembershipApprovalEmail, MembershipApprovalEmailAttempt, approval_email_write
from .registration_forms import OnlineRegistrationForm, RegistrationForm
from .registration_models import RegistrationIntake
from .test_pdf_registration import association_data, pdf_policy
from .test_registration_decisions import DecisionHelpers
from .test_registration_intake import staff
from .tests import grant
from . import registration_services as registration


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MembershipApprovalEmailTests(DecisionHelpers, TestCase):
    def setUp(self):
        self.setup_decisions()
        self.client.force_login(self.actor)
        with referral_write():
            self.sender = ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []

    def approve(self, intake=None, **changes):
        intake = intake or self.make()
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(intake, self.data(intake, **changes))
        return intake, MembershipApprovalEmail.objects.get(intake=intake)

    def test_online_requires_email_and_pwd_in_html_view_and_service(self):
        url = reverse('membership:registration_apply')
        page = self.client.get(url)
        for name in ('email', 'pwd_number'):
            self.assertTrue(page.context['form'].fields[name].required)
            for value in ('', 'invalid'):
                data = association_data() | {name: value, 'context_id': page.context['context_id']}
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(name, response.context['form'].errors)
                with self.assertRaises(ValidationError):
                    self.make(data={name: value})
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertFalse(MembershipApprovalEmail.objects.exists())
        self.assertEqual(mail.outbox, [])
        form = OnlineRegistrationForm(association_data(), policy=pdf_policy())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.submitted_data()['pwd_number'], association_data()['pwd_number'])
        # Retained snapshots and staff correction forms keep their old contract.
        legacy = RegistrationForm(association_data() | {'email': '', 'pwd_number': ''}, policy=pdf_policy())
        self.assertTrue(legacy.is_valid(), legacy.errors)

    def test_email_waits_for_commit_and_repeated_approval_or_callback_sends_once(self):
        intake = self.make()
        self.assertFalse(MembershipApprovalEmail.objects.exists())
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.decide(intake)
        job = MembershipApprovalEmail.objects.get()
        self.assertEqual(job.state, 'queued')
        self.assertEqual(mail.outbox, [])
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.decide(intake)
        self.assertFalse(deliver_approval_email(job.pk))
        job.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(MembershipApprovalEmail.objects.count(), 1)
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipApprovalEmailAttempt.objects.count(), 1)

    def test_reviewed_details_and_final_membership_confirmation_are_sent(self):
        intake = self.make()
        original = intake.revisions.get().data
        _, job = self.approve(intake, first_name='Reviewed')
        message = mail.outbox[0]
        self.assertEqual(message.to, [original['email']])
        self.assertEqual(message.reply_to, [self.sender.sender_email])
        self.assertIn(self.sender.sender_email, message.from_email)
        for text in ('membership application has been approved', 'You are now a member', 'Reviewed', intake.reference):
            self.assertIn(text, message.body)
        for private in ('1990-01-02', 'Visual Disability', '14500.50', original['pwd_number']):
            self.assertNotIn(private, message.body)
        self.assertEqual(intake.revisions.get(number=1).data, original)
        self.assertEqual(job.revision.data['email'], original['email'])
        with self.assertRaises(PermissionDenied), approval_email_write():
            job.body = 'altered'
            job.save(update_fields=['body'])

    def test_rollback_cancels_email_and_member_creation(self):
        intake = self.make()
        from .approval_email import queue_approval_email
        def fail_after_queue(*args, **kwargs):
            queue_approval_email(*args, **kwargs)
            raise RuntimeError('Synthetic rollback')
        with self.captureOnCommitCallbacks(execute=True), patch('membership.approval_email.queue_approval_email', side_effect=fail_after_queue):
            with self.assertRaises(RuntimeError):
                self.decide(intake)
        self.assertFalse(MembershipApprovalEmail.objects.exists())
        self.assertFalse(Member.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_failed_connection_preserves_approval_and_retry_records_history(self):
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')):
            intake, job = self.approve()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(mail.outbox, [])
        with self.captureOnCommitCallbacks(execute=True):
            retry_approval_email(job.pk, reference=intake.reference, user=self.actor, confirmed=True)
        job.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 2))
        self.assertEqual(list(job.attempts.values_list('outcome', flat=True)), ['failed', 'accepted'])
        self.assertEqual(intake.actions.filter(action='approval_email_retry').count(), 1)
        with self.assertRaises(ValidationError):
            retry_approval_email(job.pk, reference=intake.reference, user=self.actor, confirmed=True)
        self.assertEqual(len(mail.outbox), 1)

    def test_ambiguous_smtp_send_is_unconfirmed_and_not_automatically_retried(self):
        with patch('membership.approval_email.EmailMessage.send', side_effect=smtplib.SMTPServerDisconnected('Synthetic')):
            intake, job = self.approve()
        self.assertEqual(job.state, 'uncertain')
        self.assertFalse(deliver_approval_email(job.pk))
        page = self.client.get(reverse('membership:registration_detail', args=[intake.reference]))
        self.assertContains(page, 'another attempt could send a duplicate')

    def test_changed_sender_is_not_substituted_and_failed_quit_does_not_resend(self):
        intake = self.make()
        with self.captureOnCommitCallbacks(execute=False):
            self.decide(intake)
        job = MembershipApprovalEmail.objects.get()
        with referral_write():
            self.sender.sender_email = 'different@example.invalid'
            self.sender.save(update_fields=['sender_email'])
        self.assertFalse(deliver_approval_email(job.pk))
        self.assertEqual(mail.outbox, [])
        with referral_write():
            self.sender.sender_email = job.sender
            self.sender.save(update_fields=['sender_email'])
        with patch('django.core.mail.backends.locmem.EmailBackend.close', side_effect=OSError('Synthetic QUIT')), self.captureOnCommitCallbacks(execute=True):
            retry_approval_email(job.pk, reference=intake.reference, user=self.actor, confirmed=True)
        job.refresh_from_db()
        self.assertEqual(job.state, 'sent')
        self.assertFalse(deliver_approval_email(job.pk))
        self.assertEqual(len(mail.outbox), 1)

    def test_retry_requires_permission_confirmation_post_and_correct_intake(self):
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')):
            intake, job = self.approve()
        viewer = staff('synthetic_email_viewer')
        with self.assertRaises(PermissionDenied):
            retry_approval_email(job.pk, reference=intake.reference, user=viewer, confirmed=True)
        with self.assertRaises(ValidationError):
            retry_approval_email(job.pk, reference=intake.reference, user=self.actor, confirmed=False)
        url = reverse('membership:approval_email_retry', args=[intake.reference, job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        wrong = self.make(data={'pwd_number': '00-0000-000-0000009'})
        self.assertEqual(self.client.post(reverse('membership:approval_email_retry', args=[wrong.reference, job.pk]), {'confirm': '1'}).status_code, 404)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url, {'confirm': '1'}).status_code, 403)
        self.assertNotContains(self.client.get(reverse('membership:registration_detail', args=[intake.reference])), 'Retry approval email')

    def test_decline_and_onsite_intakes_do_not_send_online_approval_email(self):
        intake = self.make()
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(intake, self.data(intake, action='decline_registration'))
        grant(self.actor, 'membership.encode_registrationintake')
        binding = registration.binding_for('synthetic-onsite-email')
        context = registration.issue_context(binding, channel='walk_in', user=self.actor)
        onsite = registration.submit_registration(context.pk, binding, association_data(), channel='walk_in', user=self.actor)
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(onsite)
        self.assertFalse(MembershipApprovalEmail.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_older_missing_email_requires_correction_before_invitation_and_approval(self):
        with patch('membership.registration_services.OnlineRegistrationForm', RegistrationForm):
            intake = self.make(data={'email': ''}, invited=False)
        with self.assertRaisesMessage(ValidationError, 'valid email address'):
            self.approve(intake, email='')
        self.assertFalse(MembershipApprovalEmail.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_approval_redirect_member_page_and_review_show_delivery_status(self):
        intake = self.make()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('membership:registration_detail', args=[intake.reference]), self.data(intake))
        self.assertEqual(response.status_code, 302)
        for url in (response.url, reverse('membership:registration_detail', args=[intake.reference])):
            page = self.client.get(url)
            self.assertContains(page, 'Membership approval email')
            self.assertContains(page, 'Saved to test outbox')
            self.assertNotContains(page, 'Retry approval email')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend')
    def test_connected_gmail_transport_overrides_development_outbox(self):
        from assistance.referral_connection import encrypt_password
        with referral_write():
            self.sender.gmail_password_encrypted = encrypt_password(self.sender.sender_email, 'synthetic-password')
            self.sender.save(update_fields=['gmail_password_encrypted'])
        with patch('membership.approval_email.get_connection') as connection, patch('membership.approval_email.EmailMessage.send', return_value=1):
            _, job = self.approve()
        self.assertEqual(job.state, 'sent')
        self.assertEqual(connection.call_args.kwargs['backend'], 'django.core.mail.backends.smtp.EmailBackend')
        self.assertEqual(connection.call_args.kwargs['host'], 'smtp.gmail.com')
        self.assertEqual(connection.call_args.kwargs['username'], self.sender.sender_email)
        self.assertTrue(connection.call_args.kwargs['use_tls'])


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MembershipEmailConcurrencyTests(DecisionHelpers, TransactionTestCase):
    def test_concurrent_deliveries_claim_one_message(self):
        self.setup_decisions()
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []
        with patch('membership.approval_email.deliver_approval_email', return_value=False):
            self.decide(self.make())
        job = MembershipApprovalEmail.objects.get()
        ready = Barrier(2)

        def send():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return deliver_approval_email(job.pk)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: send(), range(2))), [True, False])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(MembershipApprovalEmailAttempt.objects.count(), 1)
