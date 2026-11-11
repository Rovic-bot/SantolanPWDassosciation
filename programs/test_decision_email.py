"""Eligibility notifications use captured mail and a disposable database only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import smtplib
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceCase, AssistanceLog
from assistance.referral_models import ReferralSettings, referral_write
from membership.tests import grant as permissions
from .decision_email import deliver_decision_email, recipient_for, retry_decision_email
from .decision_email_models import ApplicationDecisionEmail, ApplicationDecisionEmailAttempt
from .models import ProgramApplication, ProgramLog
from .review_services import review_submitted_application
from . import test_direct_review as direct_review


def setup_email_review(test):
    """A retained application under the current mandatory-EWAF program contract."""
    from assistance.tests import seed_statuses
    from .test_application_workflow import ConfirmedApplicationTests
    from .testsupport import application_fixture
    from .application_workflow import CONTRACT
    seed_statuses()
    ConfirmedApplicationTests.setUp(test)
    test.program.ewaf_applicable = True
    test.program.save(update_fields=['ewaf_applicable'])
    test.application = application_fixture(test.program, test.member)
    test.application.source_snapshot = {'application_confirmation': {
        'contract': CONTRACT, 'confirm_information': True, 'information_basis': 'member_record',
        'applicant_name': test.member.full_name, 'applicant_email': 'different@example.invalid'}}
    test.application.save(update_fields=['source_snapshot'])
    test.url = reverse('programs:application_detail', args=[test.program.pk, test.application.pk])
    test.client.force_login(test.admin)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DecisionEmailTests(TestCase):
    identity = direct_review.DirectApplicationReviewTests.identity
    grant = direct_review.DirectApplicationReviewTests.grant
    data = direct_review.DirectApplicationReviewTests.data
    submit = direct_review.DirectApplicationReviewTests.submit
    decision = direct_review.DirectApplicationReviewTests.decision

    def setUp(self):
        setup_email_review(self)
        with referral_write():
            self.sender = ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []

    def addresses(self, application='', registration=''):
        self.application.refresh_from_db()
        source = self.application.source_snapshot
        source['application_confirmation']['applicant_email'] = application
        self.application.source_snapshot = source
        self.application.save(update_fields=['source_snapshot'])
        self.member.email = registration
        self.member.save(update_fields=['email'])
        self.application.member = self.member

    def save_decision(self, outcome='eligible', notes='', execute=True):
        with self.captureOnCommitCallbacks(execute=execute):
            response = self.client.post(self.url, self.decision(outcome, notes=notes))
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        return self.application.decision_emails.first()

    def test_all_three_buttons_send_program_outcome_and_only_supplied_remarks(self):
        self.addresses('application@example.invalid', 'registration@example.invalid')
        for outcome, label, notes in (('eligible', 'Eligible', ''),
                ('review', 'Needs Information', 'Bring the missing proof of residency.'),
                ('ineligible', 'Ineligible', 'The submitted qualification does not meet this program requirement.')):
            job = self.save_decision(outcome, notes)
            self.assertEqual(job.state, 'sent')
            self.assertEqual(job.recipient_source, 'application')
            message = mail.outbox[-1]
            self.assertEqual(message.to, ['application@example.invalid'])
            self.assertEqual(message.reply_to, [self.sender.sender_email])
            self.assertIn(self.program.name, message.body)
            self.assertIn(f'Eligibility decision: {label}', message.body)
            if notes:
                self.assertIn(notes, message.body)
            else:
                self.assertNotIn("Administrator's remarks:", message.body)
                self.assertNotIn('Administrator marked Eligible', message.body)
            self.assertNotIn('/status/', message.body)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(ApplicationDecisionEmail.objects.count(), 3)
        self.assertEqual(ApplicationDecisionEmailAttempt.objects.count(), 3)
        self.assertFalse(self.application.assistance_releases.exists())

    def test_required_remarks_are_enforced_without_javascript_and_in_service(self):
        for outcome in ('review', 'ineligible'):
            for notes in ('', '   '):
                response = self.client.post(self.url, self.decision(outcome, notes=notes))
                self.assertTrue(response.context['decision_form'].errors.get('notes'))
                with self.assertRaises(ValidationError):
                    review_submitted_application(self.application.pk, user=self.admin,
                        data=self.decision(outcome, notes=notes))
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertFalse(ApplicationDecisionEmail.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_registration_fallback_and_missing_address_skip(self):
        self.addresses('', 'registration@example.invalid')
        job = self.save_decision()
        self.assertEqual((job.recipient, job.recipient_source, job.state),
                         ('registration@example.invalid', 'registration', 'sent'))
        self.addresses('', '')
        job = self.save_decision()
        self.assertEqual((job.state, job.skip_reason, job.attempt_count), ('skipped', 'missing', 0))
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(self.client.get(self.url), 'No email address was provided')

    def test_invalid_primary_address_never_silently_uses_registration(self):
        self.addresses('not-an-email', 'registration@example.invalid')
        self.assertEqual(recipient_for(self.application), ('', 'application', 'invalid'))
        job = self.save_decision()
        self.assertEqual((job.state, job.skip_reason), ('skipped', 'invalid'))
        self.assertEqual(mail.outbox, [])

    def test_duplicate_post_and_duplicate_delivery_send_once(self):
        data = self.decision()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, data)
        job = self.application.decision_emails.get()
        self.assertFalse(deliver_decision_email(job.pk))
        self.assertEqual(self.client.post(self.url, data).status_code, 200)
        self.assertEqual(ApplicationDecisionEmail.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_waits_for_commit_and_rollback_discards_it_with_the_decision(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(RuntimeError, 'rollback'):
                with transaction.atomic():
                    review_submitted_application(self.application.pk, user=self.admin, data=self.decision())
                    self.assertEqual(mail.outbox, [])
                    raise RuntimeError('rollback')
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertFalse(ApplicationDecisionEmail.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_send_failure_keeps_decision_and_retry_uses_saved_recipient(self):
        self.addresses('original@example.invalid', '')
        with patch('programs.decision_email.get_connection', side_effect=OSError('secret provider diagnostic')):
            job = self.save_decision(notes='Recorded eligibility remark.')
        self.assertEqual(job.state, 'failed')
        self.assertEqual(self.application.status, 'ELIGIBLE')
        self.assertEqual(job.attempts.get().error_type, 'OSError')
        self.assertNotIn('secret', job.attempts.get().error_type)
        version, audits = self.application.version, AssistanceLog.objects.count()
        self.addresses('changed@example.invalid', 'different@example.invalid')
        retry_url = reverse('programs:decision_email_retry', args=[self.program.pk, self.application.pk, job.pk])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(retry_url, {'confirm': '1', 'recipient': 'attacker@example.invalid'})
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 2))
        self.assertEqual(mail.outbox[-1].to, ['original@example.invalid'])
        self.assertEqual((self.application.version, AssistanceLog.objects.count()), (version, audits))
        self.assertTrue(ProgramLog.objects.filter(action='decision_email_retry').exists())
        with self.assertRaises(ValidationError):
            retry_decision_email(job.pk, application_id=self.application.pk, user=self.admin, confirmed=True)

    def test_disconnected_sender_does_not_undo_eligibility(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend'):
            job = self.save_decision()
        self.assertEqual((self.application.status, job.state), ('ELIGIBLE', 'failed'))
        self.assertEqual(job.attempts.get().error_type, 'EmailConnectionRequired')
        self.assertEqual(mail.outbox, [])
        self.assertContains(self.client.get(self.url), 'Retry email')

    def test_quit_failure_keeps_accepted_eligibility_email_and_prevents_resend(self):
        with patch('django.core.mail.backends.locmem.EmailBackend.close',
                   side_effect=smtplib.SMTPServerDisconnected('Synthetic QUIT')):
            job = self.save_decision()
        self.assertEqual((job.state, job.attempt_count), ('sent', 1))
        self.assertFalse(deliver_decision_email(job.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(job.attempts.get().outcome, 'accepted')

    def test_interrupted_submission_has_visible_uncertainty_and_no_automatic_resend(self):
        with patch('programs.decision_email.EmailMessage.send',
                   side_effect=smtplib.SMTPServerDisconnected('private provider detail')):
            job = self.save_decision()
        self.assertEqual(job.attempts.get().error_type, 'EmailDeliveryUnconfirmed')
        self.assertFalse(deliver_decision_email(job.pk))
        page = self.client.get(self.url)
        self.assertContains(page, 'Email delivery is unconfirmed')
        self.assertContains(page, 'another attempt could send a duplicate')
        self.assertNotContains(page, 'private provider detail')

    def test_sender_change_and_superseded_decision_cannot_send_old_message(self):
        job = self.save_decision(execute=False)
        with referral_write():
            self.sender.sender_email = 'replacement@example.invalid'
            self.sender.save(update_fields=['sender_email'])
        self.assertFalse(deliver_decision_email(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        newer = self.save_decision('review', 'Provide the missing information.', execute=False)
        with self.assertRaises(ValidationError):
            retry_decision_email(job.pk, application_id=self.application.pk, user=self.admin, confirmed=True)
        self.application.version += 1
        self.application.save(update_fields=['version'])
        self.assertFalse(deliver_decision_email(newer.pk))
        newer.refresh_from_db()
        self.assertEqual((newer.state, newer.skip_reason), ('skipped', 'superseded'))
        self.assertEqual(mail.outbox, [])

    def test_retry_permissions_csrf_and_application_binding(self):
        job = self.save_decision(execute=False)
        url = reverse('programs:decision_email_retry', args=[self.program.pk, self.application.pk, job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(reverse('programs:decision_email_retry',
            args=[uuid4(), self.application.pk, job.pk]), {'confirm': '1'}).status_code, 404)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(url, {'confirm': '1'}).status_code, 403)
        viewer = get_user_model().objects.create_user('notification_viewer', is_staff=True)
        permissions(viewer, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url, {'confirm': '1'}).status_code, 403)
        self.assertNotContains(self.client.get(self.url), 'Eligibility email')
        self.client.logout()
        self.assertEqual(self.client.post(url, {'confirm': '1'}).status_code, 302)

    def test_notification_contents_and_history_cannot_be_rewritten(self):
        job = self.save_decision()
        with self.assertRaises(PermissionDenied):
            job.body = 'Replacement'
            job.save()
        with self.assertRaises(PermissionDenied):
            ApplicationDecisionEmail.objects.filter(pk=job.pk).update(recipient='replacement@example.invalid')
        with self.assertRaises(PermissionDenied):
            job.attempts.all().delete()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DecisionEmailConcurrencyTests(TransactionTestCase):
    identity = direct_review.DirectApplicationReviewTests.identity
    grant = direct_review.DirectApplicationReviewTests.grant
    data = direct_review.DirectApplicationReviewTests.data
    submit = direct_review.DirectApplicationReviewTests.submit
    decision = direct_review.DirectApplicationReviewTests.decision

    def setUp(self):
        setup_email_review(self)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='concurrency@example.invalid')
        mail.outbox = []

    def test_concurrent_callbacks_claim_one_delivery_attempt(self):
        with patch('programs.decision_email.deliver_decision_email'):
            review_submitted_application(self.application.pk, user=self.admin, data=self.decision())
        job = self.application.decision_emails.get()
        barrier = Barrier(2)

        def deliver():
            try:
                barrier.wait(timeout=15)
                return deliver_decision_email(job.pk)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: deliver(), range(2)))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(job.attempts.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
