"""Fictional PDAO review, separate onsite workflow and commit-only notices."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.referral_connection import EmailConnectionRequired
from assistance.referral_models import ReferralSettings, referral_write
from members.models import Member
from .models import MembershipApplication, MembershipSettings
from . import pdao_services as services
from .pdao_email import deliver_review_email, retry_review_email
from .pdao_email_models import PDAOReviewEmail as Email, PDAOReviewEmailAttempt as Attempt
from .pdao_models import PDAORegistration
from .test_pdao_registration import PDAOHelpers, actor
from .test_pdao_review import review_data
from .test_pdf_registration import pdao_data


class NoticeHelpers(PDAOHelpers):
    def setup_review(self, number=True):
        self.staff = actor(services.VIEW, services.FORWARD, services.CORRECT, services.ADD)
        data = self.prepare() | ({'pwd_number': '00-0000-000-0000001'} if number else {})
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data).status_code, 302)
        self.item = PDAORegistration.objects.get()
        self.original = self.item.data
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/check'})
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []

    def transition(self, action='ready', **changes):
        return services.transition(self.item.pk, self.staff, {'version': self.item.version, 'action': action,
            'prpwd_lookup_number': self.item.current_data.get('pwd_number', ''), 'ready_confirmed': 'on', **changes})


@override_settings(PDAO_REGISTRATION_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOReviewNoticeTests(NoticeHelpers, TestCase):
    def setUp(self):
        self.setup_review()

    def test_ready_without_confirmation_leaves_status_audit_and_email_unchanged(self):
        for channel in ('online', 'walk_in'):
            with self.subTest(channel=channel):
                if channel == 'walk_in':
                    self.client.force_login(self.staff)
                    page = self.client.get(reverse('membership:pdao_onsite'))
                    data = pdao_data() | {'submission_token': page.context['form'].initial['submission_token']}
                    self.assertEqual(self.client.post(reverse('membership:pdao_onsite'), data).status_code, 302)
                    item = PDAORegistration.objects.exclude(pk=self.item.pk).get()
                else:
                    item = self.item
                event_count = item.events.count()
                values = {'version': item.version, 'action': 'ready', 'prpwd_lookup_number': item.current_data.get('pwd_number', '')}
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    with self.assertRaises(ValidationError):
                        services.transition(item.pk, self.staff, values)
                item.refresh_from_db()
                self.assertEqual((item.status, item.version), ('received', 0))
                self.assertEqual(item.events.count(), event_count)
                self.assertEqual(callbacks, [])
                self.assertFalse(Email.objects.exists())
                self.assertEqual(mail.outbox, [])

    def test_http_requires_explicit_ready_confirmation_and_renders_recovery(self):
        self.client.force_login(self.staff)
        url = reverse('membership:pdao_detail', args=[self.item.pk])
        values = {'version': 0, 'action': 'ready', 'prpwd_lookup_number': self.original['pwd_number']}
        response = self.client.post(url, values)
        self.assertContains(response, 'Confirm that this application is ready', status_code=400)
        self.assertContains(response, 'id="pdao-ready-dialog"', status_code=400)
        self.assertFalse(Email.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url, values | {'ready_confirmed': 'on'}).status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'ready')
        self.assertEqual(len(mail.outbox), 1)

    def test_ready_requires_manual_lookup_and_sends_only_after_commit_once(self):
        for number in ('', 'wrong-number'):
            with self.assertRaisesMessage(ValidationError, 'Open PRPWD'):
                self.transition(prpwd_lookup_number=number)
        self.assertFalse(Email.objects.exists())
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.transition()
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(mail.outbox, [])
        callbacks[0]()
        job = Email.objects.get()
        self.assertFalse(deliver_review_email(job.pk))
        with self.assertRaises(ValidationError):
            self.transition()
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'ready')
        self.assertEqual(self.item.data, self.original)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.original['email']])
        self.assertIn('verify your information in person', job.body)
        self.assertIn(self.item.short_reference, job.body)
        self.assertNotIn(self.original['pwd_number'], job.body)
        self.assertEqual(Attempt.objects.count(), 1)
        event = self.item.events.get(action='ready')
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.details['manual_result'], 'verified')
        self.assertEqual(event.details['registry_url'], 'https://registry.example.test/check')
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())

    def test_needs_information_email_reason_and_no_forwarding_bypass(self):
        with self.assertRaises(ValidationError):
            self.transition('needs_info')
        with self.captureOnCommitCallbacks(execute=True):
            self.transition('needs_info', reason='Please check your PWD number and spelling.')
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'needs_info')
        job = Email.objects.get()
        self.assertIn('complete the PDAO application form again', job.body)
        self.assertIn('or visit', job.body)
        self.assertIn('Please check your PWD number', job.body)
        with self.assertRaises(ValidationError):
            self.transition('forwarded', confirmed='on')
        with self.assertRaises(ValidationError):
            self.transition('needs_info', reason='Duplicate')
        with self.captureOnCommitCallbacks(execute=True):
            self.transition('ready')
        self.assertEqual(len(mail.outbox), 2)

    def test_correction_invalidates_queued_notice_and_prpwd_proof(self):
        self.transition()
        job = Email.objects.get()
        self.item.refresh_from_db()
        services.correct(self.item.pk, self.staff, review_data(self.item, pwd_number='00-0000-000-0000002'))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'received')
        self.assertFalse(deliver_review_email(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.state, 'cancelled')
        with self.assertRaises(ValidationError):
            self.transition(prpwd_lookup_number=self.original['pwd_number'])
        with self.assertRaises(ValidationError):
            retry_review_email(self.item.pk, user=self.staff, identifier=job.pk)
        self.assertEqual(mail.outbox, [])

    def test_audit_failure_rolls_back_status_notice_and_callback(self):
        with self.captureOnCommitCallbacks(execute=True), patch.object(services, 'record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.transition()
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.version), ('received', 0))
        self.assertFalse(Email.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_sender_failure_retries_same_saved_message(self):
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            self.transition()
        job = Email.objects.get()
        self.assertEqual(job.state, 'failed')
        with self.captureOnCommitCallbacks(execute=True):
            retry_review_email(self.item.pk, user=self.staff, identifier=job.pk)
        job.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 2))
        self.assertEqual(len(mail.outbox), 1)
        with self.assertRaises(ValidationError):
            retry_review_email(self.item.pk, user=self.staff, identifier=job.pk)

    def test_uncertain_delivery_is_not_retried(self):
        with patch('membership.approval_email.EmailMessage.send', side_effect=TimeoutError('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            self.transition()
        job = Email.objects.get()
        self.assertEqual(job.state, 'uncertain')
        with self.assertRaisesMessage(ValidationError, 'unconfirmed'):
            retry_review_email(self.item.pk, user=self.staff, identifier=job.pk)
        self.assertFalse(deliver_review_email(job.pk))

    def test_permissions_missing_registry_and_email_fail_closed(self):
        MembershipSettings.objects.update(prpwd_url='')
        with self.assertRaisesMessage(ValidationError, 'official PRPWD'):
            self.transition()
        with patch('membership.pdao_email.validate_email', side_effect=ValidationError('Missing')):
            with self.assertRaisesMessage(ValidationError, 'valid applicant email'):
                self.transition()
        self.staff.user_permissions.remove(Permission.objects.get(codename='forward_pdaoregistration'))
        with self.assertRaises(PermissionDenied):
            self.transition()
        self.assertFalse(Email.objects.exists())

    def test_http_ignores_recipient_override_and_enforces_csrf(self):
        self.client.force_login(self.staff)
        url = reverse('membership:pdao_detail', args=[self.item.pk])
        values = {'version': 0, 'action': 'ready', 'ready_confirmed': 'on', 'prpwd_lookup_number': self.original['pwd_number'], 'email': 'wrong@example.invalid'}
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(url, values).status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(Email.objects.get().recipient, self.original['email'])
        response = self.client.get(url)
        self.assertContains(response, 'Applicant emails')
        self.assertContains(response, 'Saved to test outbox')

    def test_receipt_and_print_are_session_bound_and_share_public_shell(self):
        receipt = self.client.get(reverse('membership:pdao_receipt'))
        self.assertContains(receipt, 'portal-navigation')
        self.assertContains(receipt, 'data-pdao-receipt-print')
        self.assertContains(receipt, self.original['full_name'])
        url = reverse('membership:pdao_receipt_form')
        response = self.client.get(url)
        self.assertContains(response, 'pdao-sheet')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(Client().get(url).status_code, 404)
        self.client.post(reverse('membership:pdao_finish'))
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_onsite_can_ready_and_forward_without_email_or_registry(self):
        self.client.force_login(self.staff)
        page = self.client.get(reverse('membership:pdao_onsite'))
        values = pdao_data() | {'submission_token': page.context['form'].initial['submission_token']}
        self.assertEqual(self.client.post(reverse('membership:pdao_onsite'), values).status_code, 302)
        onsite = PDAORegistration.objects.exclude(pk=self.item.pk).get()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValidationError):
                services.transition(onsite.pk, self.staff, {'version': 0, 'action': 'needs_info', 'reason': 'No email'})
            services.transition(onsite.pk, self.staff, {'version': 0, 'action': 'ready', 'ready_confirmed': 'on'})
            services.transition(onsite.pk, self.staff, {'version': 1, 'action': 'forwarded', 'confirmed': 'on'})
        onsite.refresh_from_db()
        self.assertEqual(onsite.status, 'forwarded')
        self.assertFalse(Email.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_online_email_required_existing_number_optional(self):
        from .pdao_forms import PDAOOnlineForm
        values = pdao_data() | {'submission_token': 'synthetic'}
        self.assertTrue(PDAOOnlineForm(values).is_valid())
        self.assertIn('email', PDAOOnlineForm(values | {'email': ''}).errors)


@override_settings(PDAO_REGISTRATION_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOReviewNoticeConcurrencyTests(NoticeHelpers, TransactionTestCase):
    def test_simultaneous_ready_requests_send_once(self):
        self.setup_review()
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    self.transition()
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(run, range(2))), ['saved', 'stale'])
        self.assertEqual(Email.objects.count(), 1)
        self.assertEqual(Attempt.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
