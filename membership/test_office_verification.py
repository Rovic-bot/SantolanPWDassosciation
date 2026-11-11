"""PRPWD, office invitation, then Association approval; isolated test email only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import uuid

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.referral_connection import EmailConnectionRequired
from assistance.referral_models import ReferralSettings, referral_write
from members.models import Member
from .approval_email import deliver_approval_email, retry_approval_email
from .approval_email_models import MembershipApprovalEmail
from .office_verification import INVITATION_ACTION, send_invitation
from .pending_email import deliver_pending_email, retry_pending_email, send_pending_email
from .pending_email_models import MembershipPendingEmail, MembershipPendingEmailAttempt
from .test_registration_decisions import DecisionHelpers
from .test_registration_intake import staff


class OfficeHelpers(DecisionHelpers):
    invited_by_default = False

    def setup_office(self):
        self.setup_decisions()
        self.intake = self.make()
        self.client.force_login(self.actor)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []
        self.values = {'version': self.intake.version, 'request_key': uuid.uuid4()}
        self.url = reverse('membership:registration_detail', args=[self.intake.reference])

    def invite(self, **changes):
        review = {'prpwd_lookup_number': self.intake.revisions.get(number=self.intake.current_revision).data['pwd_number'],
                  'prpwd_verified': True}
        return send_invitation(self.intake.reference, user=self.actor, **(self.values | review | changes))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OfficeVerificationTests(OfficeHelpers, TestCase):
    def setUp(self):
        self.setup_office()

    def test_invitation_requires_manual_prpwd_confirmation_for_saved_number(self):
        before = self.intake.actions.count()
        for changes in ({'prpwd_verified': False}, {'prpwd_lookup_number': ''},
                        {'prpwd_lookup_number': 'not-the-saved-number'}):
            with self.subTest(changes=changes), self.assertRaisesMessage(ValidationError, 'Check the saved PWD number'):
                self.invite(**changes)
        self.assertFalse(MembershipPendingEmail.objects.exists())
        self.assertEqual(self.intake.actions.count(), before)
        self.assertEqual(mail.outbox, [])

    def test_prpwd_and_confirmed_visit_allow_approval_without_invitation(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake, self.data(self.intake))
        self.assertEqual(Member.objects.count(), 1)
        self.assertFalse(MembershipPendingEmail.objects.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('You are now a member', mail.outbox[0].body)
        proof = self.intake.actions.get(action='office_information_verified')
        self.assertIsNone(proof.payload['email_id'])
        self.assertIsNone(proof.payload['invited_revision'])
        self.assertFalse(proof.payload['invitation_sent'])

    def test_invitation_records_prpwd_attestation_with_revision_and_actor(self):
        from .office_verification import recorded_prpwd_review
        job = self.invite()
        revision = self.intake.revisions.get(number=self.intake.current_revision)
        event = self.intake.actions.get(action=INVITATION_ACTION)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.revision, revision)
        self.assertEqual(event.payload['email_id'], str(job.pk))
        self.assertEqual(event.payload['prpwd_review'], recorded_prpwd_review(self.intake, revision))
        self.assertEqual(event.payload['prpwd_review']['number'], revision.data['pwd_number'])
        self.assertIs(event.payload['prpwd_review']['verified'], True)

    def test_send_then_confirm_visit_then_approve_creates_member_and_two_distinct_emails(self):
        original = self.intake.revisions.get().data
        with self.assertRaisesMessage(ValidationError, 'visited the barangay office'):
            self.decide(self.intake, self.data(self.intake, office_verification_confirmed=''))
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            invitation = self.invite()
        self.assertEqual(mail.outbox, [])
        self.intake.refresh_from_db()
        self.assertIsNone(self.intake.membership_application_id)
        self.assertFalse(Member.objects.exists())
        self.assertEqual(self.intake.revisions.get().data, original)
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertIn('not yet a member', mail.outbox[0].body)
        self.assertIn('barangay office', mail.outbox[0].body)
        self.assertIn('Bring your PWD ID', mail.outbox[0].body)
        with self.assertRaisesMessage(ValidationError, 'visited the barangay office'):
            self.decide(self.intake, self.data(self.intake, office_verification_confirmed=''))
        data = self.data(self.intake)
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake, data)
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('You are now a member', mail.outbox[1].body)
        self.assertNotIn('Please come', mail.outbox[1].body)
        for message in mail.outbox:
            self.assertEqual(message.to, [original['email']])
            for private in (original['pwd_number'], original['birthdate'], original['household_monthly_income']):
                self.assertNotIn(private, message.body)
        proof = self.intake.actions.get(action='office_information_verified')
        self.assertEqual(proof.actor, self.actor)
        self.assertEqual(proof.payload['email_id'], str(invitation.pk))
        self.assertEqual(proof.payload['invited_revision'], 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake, data)
        self.assertFalse(deliver_pending_email(invitation.pk))
        self.assertFalse(deliver_approval_email(MembershipApprovalEmail.objects.get().pk))
        self.assertEqual(len(mail.outbox), 2)

    def test_failed_or_uncertain_invitation_does_not_replace_visit_confirmation(self):
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            job = self.invite()
        self.intake.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        with self.assertRaisesMessage(ValidationError, 'visited the barangay office'):
            self.decide(self.intake, self.data(self.intake, office_verification_confirmed=''))
        # A fresh button request reuses the failed message rather than silently resending it.
        self.assertEqual(self.invite(version=self.intake.version, request_key=uuid.uuid4()).pk, job.pk)
        with patch('membership.approval_email.EmailMessage.send', side_effect=TimeoutError('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        with self.assertRaisesMessage(ValidationError, 'visited the barangay office'):
            self.decide(self.intake, self.data(self.intake, office_verification_confirmed=''))
        with self.assertRaisesMessage(ValidationError, 'unconfirmed'):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        self.assertFalse(Member.objects.exists())

    def test_known_failure_retry_and_confirmed_visit_preserve_both_emails(self):
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            job = self.invite()
        with self.captureOnCommitCallbacks(execute=True):
            retry_pending_email(self.intake.reference, user=self.actor, identifier=job.pk)
        self.intake.refresh_from_db()
        self.assertFalse(Member.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake)
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_ordinary_pending_notice_cannot_replace_visit_confirmation(self):
        from .office_verification import INVITATION_REASON
        with self.captureOnCommitCallbacks(execute=True):
            send_pending_email(self.intake.reference, user=self.actor, **self.values, reason=INVITATION_REASON)
        self.intake.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'visited the barangay office'):
            self.decide(self.intake, self.data(self.intake, office_verification_confirmed=''))
        with self.assertRaises(ValidationError):
            self.invite()  # cannot reuse a generic notice's request key as an invitation
        self.assertFalse(Member.objects.exists())

    def test_permission_post_csrf_saved_recipient_and_stale_version_guards(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        viewer = staff('synthetic_invitation_viewer')
        with self.assertRaises(PermissionDenied):
            send_invitation(self.intake.reference, user=viewer, **self.values)
        with self.assertRaises(ValidationError):
            self.invite(version=999)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.actor)
        post = self.values | {'action': 'send_office_invitation', 'email': 'tampered@example.invalid',
            'prpwd_lookup_number': self.intake.revisions.get().data['pwd_number'], 'prpwd_verified': 'on'}
        self.assertEqual(browser.post(self.url, post).status_code, 403)
        self.assertFalse(MembershipPendingEmail.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(self.url, post).status_code, 302)
        self.assertEqual(mail.outbox[0].to, [self.intake.revisions.get().data['email']])
        self.assertFalse(Member.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'Another administrator'):
            self.decide(self.intake)  # invitation increments the version

    def test_changed_recipient_does_not_inherit_original_invitation_proof(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.invite()
        self.intake.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake, self.data(self.intake, email='corrected@example.invalid'))
        proof = self.intake.actions.get(action='office_information_verified')
        self.assertIsNone(proof.payload['email_id'])
        self.assertFalse(proof.payload['invitation_sent'])
        self.assertEqual(mail.outbox[-1].to, ['corrected@example.invalid'])

    def test_saved_correction_invalidates_prior_invitation_and_queues_new_recipient(self):
        from . import registration_services
        from .test_pdf_registration import association_data
        old = self.invite()
        self.intake.refresh_from_db()
        registration_services.correct_registration(self.intake.reference, user=self.actor,
            version=self.intake.version, reason='Fictional corrected contact address',
            data=association_data() | {'email': 'corrected@example.invalid'})
        self.intake.refresh_from_db()
        self.assertFalse(deliver_pending_email(old.pk))
        old.refresh_from_db()
        self.assertEqual(old.state, 'cancelled')
        with self.assertRaisesMessage(ValidationError, 'visited the barangay office'):
            self.decide(self.intake, self.data(self.intake, email='corrected@example.invalid', office_verification_confirmed=''))
        with self.captureOnCommitCallbacks(execute=True):
            new = self.invite(version=self.intake.version, request_key=uuid.uuid4())
        self.assertNotEqual(old.pk, new.pk)
        self.assertEqual(mail.outbox[0].to, ['corrected@example.invalid'])
        self.intake.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake, self.data(self.intake, email='corrected@example.invalid'))
        self.assertEqual(mail.outbox[1].to, ['corrected@example.invalid'])
        self.assertEqual(Member.objects.count(), 1)

    def test_invitation_audit_failure_rolls_back_message_version_and_delivery(self):
        with patch('membership.pending_email.registration.record_action', side_effect=RuntimeError('Synthetic audit')), self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                self.invite()
        self.intake.refresh_from_db()
        self.assertEqual(self.intake.version, self.values['version'])
        self.assertFalse(MembershipPendingEmail.objects.exists())
        self.assertFalse(self.intake.actions.filter(action=INVITATION_ACTION).exists())
        self.assertEqual(mail.outbox, [])

    def test_visit_audit_failure_rolls_back_final_approval_and_confirmation(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.invite()
        self.intake.refresh_from_db()
        from . import registration_services
        original = registration_services.record_action
        def fail_visit(*args, **kwargs):
            if args[1] == 'office_information_verified':
                raise RuntimeError('Synthetic visit audit failure')
            return original(*args, **kwargs)
        with patch.object(registration_services, 'record_action', side_effect=fail_visit), self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                self.decide(self.intake)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApprovalEmail.objects.exists())
        self.assertFalse(self.intake.actions.filter(action='office_information_verified').exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_final_email_failure_keeps_verified_membership_and_can_retry(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.invite()
        self.intake.refresh_from_db()
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            self.decide(self.intake)
        job = MembershipApprovalEmail.objects.get()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(Member.objects.count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            retry_approval_email(job.pk, reference=self.intake.reference, user=self.actor, confirmed=True)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('now a member', mail.outbox[1].body)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OfficeInvitationConcurrencyTests(OfficeHelpers, TransactionTestCase):
    def test_concurrent_invitation_requests_send_once_and_remain_pending(self):
        self.setup_office()
        ready = Barrier(2)
        def send():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return self.invite().pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: send(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPendingEmail.objects.count(), 1)
        self.assertEqual(MembershipPendingEmailAttempt.objects.count(), 1)
        self.assertEqual(self.intake.actions.filter(action=INVITATION_ACTION).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(Member.objects.exists())
