"""Fictional recipients only; protected collection notices on disposable MySQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.referral_connection import EmailConnectionRequired
from assistance.referral_models import ReferralSettings, referral_write
from members.models import Member
from scripts.durable_test_runner import require_disposable
from . import pdao_services as services
from .pdao_claim_email import queue_claim_notices
from .pdao_email import deliver_review_email, retry_review_email
from .pdao_email_models import PDAOReviewEmail as Email, PDAOReviewEmailAttempt as Attempt
from .pdao_forms import PDAOClaimNoticeForm, PDAOOnsiteForm, ONSITE_PRIVACY_VERSION
from .pdao_models import PDAORegistration
from .registration_models import registration_write
from .registration_policy import digest
from .test_pdao_registration import actor
from .test_pdf_registration import pdao_data
from .tests import grant


class ClaimHelpers:
    def setup_claims(self):
        require_disposable()
        self.staff = actor(services.VIEW, services.FORWARD, services.CORRECT, services.ADD)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []

    def record(self, name='One', *, email=None, channel='online', status='forwarded'):
        form = PDAOOnsiteForm(pdao_data() | {'submission_token': 'synthetic', 'first_name': name,
            'email': email if email is not None else f'{name.lower()}@example.invalid'})
        assert form.is_valid(), form.errors
        data = form.submitted_data() | {'intake_channel': channel}
        with registration_write():
            item = PDAORegistration.objects.create(submission_key=uuid4(), data=data, payload_digest=digest(data),
                privacy_version=ONSITE_PRIVACY_VERSION, binding_digest='synthetic',
                receipt_expires_at=timezone.now() + timedelta(hours=1), status=status,
                version=2 if status == 'forwarded' else 0)
            services.record_event(item, 'forwarded' if status == 'forwarded' else 'submitted', self.staff)
        return item

    def request_claims(self, *records, confirmed=True):
        return queue_claim_notices(user=self.staff, selections={item.pk: item.version for item in records}, confirmed=confirmed)


@override_settings(PDAO_REGISTRATION_ENABLED=True, PDAO_CLAIM_EMAIL_BACKGROUND=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOClaimNoticeTests(ClaimHelpers, TestCase):
    def setUp(self):
        self.setup_claims()
        self.url = reverse('membership:pdao_claim_notices')

    def test_bulk_notice_is_private_commit_only_and_keeps_forwarded_records_unchanged(self):
        online = self.record('Online')
        onsite = self.record('Onsite', channel='walk_in')
        original = list(PDAORegistration.objects.order_by('pk').values())
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            result = self.request_claims(online, onsite)
        self.assertEqual(result, {'queued': 2, 'already_requested': 0})
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(mail.outbox, [])
        callbacks[0]()
        self.assertEqual(len(mail.outbox), 2)
        for item in (online, onsite):
            job = Email.objects.get(registration=item, outcome='claim_ready')
            self.assertEqual(job.state, 'sent')
            message = next(message for message in mail.outbox if message.to == [item.data['email']])
            self.assertEqual(message.cc, [])
            self.assertEqual(message.bcc, [])
            self.assertIn('ready for collection at the Barangay Santolan office', message.body)
            self.assertIn(item.short_reference, message.body)
            self.assertNotIn('Visual Disability', message.body)
            self.assertEqual(job.attempts.count(), 1)
            self.assertTrue(item.events.get(action='claim_notice_queued').details['availability_confirmed'])
        self.assertEqual(list(PDAORegistration.objects.order_by('pk').values()), original)
        self.assertFalse(Member.objects.exists())

    def test_duplicate_clicks_do_not_create_or_deliver_another_notice(self):
        item = self.record()
        with self.captureOnCommitCallbacks(execute=True):
            self.request_claims(item)
            self.assertEqual(self.request_claims(item), {'queued': 0, 'already_requested': 1})
        self.assertEqual(Email.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(deliver_review_email(Email.objects.get().pk))
        with self.assertRaises(ValidationError):
            retry_review_email(item.pk, user=self.staff, identifier=Email.objects.get().pk)

    def test_unforwarded_stale_or_missing_email_rejects_entire_batch(self):
        valid = self.record('Valid')
        missing = self.record('Missing', email='', channel='walk_in')
        pending = self.record('Pending', status='received')
        cases = [{valid.pk: 2, missing.pk: 2}, {valid.pk: 2, pending.pk: 0}, {valid.pk: 1}, {uuid4(): 2}]
        for selection in cases:
            with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValidationError):
                queue_claim_notices(user=self.staff, selections=selection, confirmed=True)
            self.assertFalse(Email.objects.exists())
        with self.assertRaises(ValidationError):
            self.request_claims(valid, confirmed=False)
        self.assertFalse(valid.events.filter(action='claim_notice_queued').exists())
        self.assertEqual(mail.outbox, [])

    def test_audit_failure_rolls_back_whole_batch_and_callbacks(self):
        one, two = self.record('One'), self.record('Two')
        original = services.record_event
        calls = []
        def failing(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('Synthetic audit failure')
            return original(*args, **kwargs)
        with patch.object(services, 'record_event', side_effect=failing), self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                self.request_claims(one, two)
        self.assertFalse(Email.objects.exists())
        self.assertFalse(one.events.filter(action='claim_notice_queued').exists())
        self.assertEqual(mail.outbox, [])

    def test_permission_revocation_before_commit_rolls_back(self):
        item = self.record()
        with patch.object(services, 'require_staff', side_effect=[self.staff, PermissionDenied]), self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(PermissionDenied):
                self.request_claims(item)
        self.assertFalse(Email.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_known_delivery_failure_retries_saved_message_for_onsite_application(self):
        item = self.record(channel='walk_in')
        with patch('membership.approval_email.transport_for', side_effect=EmailConnectionRequired('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            self.request_claims(item)
        job = Email.objects.get()
        self.assertEqual(job.state, 'failed')
        body, recipient = job.body, job.recipient
        with self.captureOnCommitCallbacks(execute=True):
            retry_review_email(item.pk, user=self.staff, identifier=job.pk)
        job.refresh_from_db()
        self.assertEqual((job.state, job.body, job.recipient), ('sent', body, recipient))
        self.assertEqual(len(mail.outbox), 1)

    def test_uncertain_delivery_never_automatically_resends(self):
        item = self.record()
        with patch('membership.approval_email.EmailMessage.send', side_effect=TimeoutError('Synthetic')), self.captureOnCommitCallbacks(execute=True):
            self.request_claims(item)
        job = Email.objects.get()
        self.assertEqual(job.state, 'uncertain')
        with self.assertRaisesMessage(ValidationError, 'unconfirmed'):
            retry_review_email(item.pk, user=self.staff, identifier=job.pk)
        self.assertEqual(self.request_claims(item)['queued'], 0)
        self.assertFalse(deliver_review_email(job.pk))

    def test_http_permission_csrf_post_and_recipient_binding(self):
        item = self.record()
        data = {'applications': [f'{item.pk}:{item.version}'], 'confirmed': 'on',
            'recipient': 'untrusted@example.invalid', 'return_to': 'detail'}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        viewer = get_user_model().objects.create_user('synthetic_claim_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', services.VIEW)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.staff)
        self.assertEqual(protected.post(self.url, data).status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('membership:pdao_detail', args=[item.pk]), fetch_redirect_response=False)
        self.assertEqual(mail.outbox[0].to, [item.data['email']])

    def test_forwarded_inbox_and_record_offer_only_available_notices(self):
        available = self.record('Available')
        missing = self.record('Missing', email='')
        notified = self.record('Notified')
        self.request_claims(notified)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('membership:pdao_inbox'), {'state': 'forwarded'})
        self.assertEqual(response.context['claim_eligible_count'], 1)
        self.assertContains(response, 'No valid email recorded')
        self.assertContains(response, 'Email queued')
        self.assertContains(response, 'data-claim-select', count=3)
        self.assertContains(response, 'Send PWD ID claim emails')
        self.assertContains(self.client.get(reverse('membership:pdao_detail', args=[available.pk])), 'Send PWD ID claim email')
        self.assertNotContains(self.client.get(reverse('membership:pdao_detail', args=[missing.pk])), 'Send PWD ID claim email')
        self.assertNotContains(self.client.get(reverse('membership:pdao_inbox'), {'state': 'ready'}), 'id="pdao-claim-form"')
        viewer = get_user_model().objects.create_user('synthetic_claim_readonly', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', services.VIEW)
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(reverse('membership:pdao_inbox'), {'state': 'forwarded'}), 'data-claim-select')

    def test_selection_limits_confirmation_and_immutable_snapshots(self):
        item = self.record()
        valid = {'applications': [f'{item.pk}:2'], 'confirmed': 'on'}
        for changes in ({'applications': []}, {'applications': ['bad']}, {'applications': [f'{item.pk}:-1']},
                        {'applications': [f'{uuid4()}:2' for _ in range(26)]}, {'confirmed': ''}):
            self.assertFalse(PDAOClaimNoticeForm(valid | changes).is_valid())
        form = PDAOClaimNoticeForm(valid)
        self.assertTrue(form.is_valid(), form.errors)
        self.request_claims(item)
        job = Email.objects.get()
        with self.assertRaises(PermissionDenied):
            Email.objects.filter(pk=job.pk).update(recipient='changed@example.invalid')
        job.body = 'changed'
        with self.assertRaises(PermissionDenied):
            job.save(update_fields=['body'])


@override_settings(PDAO_REGISTRATION_ENABLED=True, PDAO_CLAIM_EMAIL_BACKGROUND=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOClaimConcurrencyTests(ClaimHelpers, TransactionTestCase):
    def test_overlapping_batches_create_one_notice_per_application(self):
        self.setup_claims()
        one, two, three = self.record('One'), self.record('Two'), self.record('Three')
        barrier = Barrier(2)
        def run(records):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.request_claims(*records)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, [(one, two), (three, two)]))
        self.assertEqual(sum(result['queued'] for result in results), 3)
        self.assertEqual(sum(result['already_requested'] for result in results), 1)
        self.assertEqual(Email.objects.count(), 3)
        self.assertEqual(Attempt.objects.count(), 3)
        self.assertEqual(len(mail.outbox), 3)
