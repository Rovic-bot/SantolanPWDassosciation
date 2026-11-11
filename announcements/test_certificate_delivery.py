import base64
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from threading import Barrier
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.tests import create_member
from programs.models import ProgramApplication
from programs.testsupport import application_fixture
from ewaf.operational_testsupport import OperationalHelpers
from . import test_results as fixtures
from .certificate_delivery import deliver_certificate, retry_certificates
from .certificate_models import SelectionCertificateEmail as Email, SelectionCertificateAttempt, certificate_write
from .certificates import TEMPLATE, certificate_document
from .models import Announcement
from .recorded_results import recorded_preview, publish_recorded_results
from .resend_mail import ResendFailure, send_certificate, setup_problem


@override_settings(CERTIFICATE_RESEND_ENABLED=False, CERTIFICATE_EMAIL_BACKGROUND=False,
                   RESEND_API_KEY='', RESEND_FROM_EMAIL='')
class CertificateDeliveryTests(OperationalHelpers, TestCase):
    def setUp(self):
        # Certificate delivery applies to EWAF selections. Use a real locked
        # configuration and recorded decision instead of a non-EWAF selection.
        fixtures.mock_pdf_conversion(self)
        self.setup_operational()
        self.member.email = 'member@example.invalid'
        self.member.save()
        self.lock_policy()
        self.choose(self.calculate())
        self.admin = self.officer
        self.client.force_login(self.admin)

    def publish(self):
        plan = recorded_preview(self.program.pk, user=self.admin)
        return publish_recorded_results(self.program.pk, user=self.admin,
            expected=plan['expected'], version=plan['version'],
            selection_reason='Synthetic human-reviewed selections within the program capacity.')

    def enabled(self):
        return self.settings(CERTIFICATE_RESEND_ENABLED=True,
            RESEND_API_KEY='synthetic-test-key', RESEND_FROM_EMAIL='certificates@example.invalid')

    def test_only_selected_members_queued_with_personalized_template(self):
        other = application_fixture(self.program, create_member('CERT-NOT-SELECTED'))
        before = list(ProgramApplication.objects.values())
        with self.captureOnCommitCallbacks(execute=True) as callbacks, patch(
                'announcements.certificate_delivery.kick_delivery') as kick:
            item = self.publish()
        self.assertEqual(len(callbacks), 1)
        kick.assert_called_once()
        job = Email.objects.get()
        self.assertEqual(job.application_id, self.application.pk)
        self.assertNotEqual(job.application_id, other.pk)
        self.assertEqual(job.recipient, self.member.email)
        self.assertEqual((job.state, job.reason), ('blocked', 'setup'))
        self.assertEqual(job.revision_id, item.result_revision_id)
        self.assertEqual(job.issued_on, timezone.localdate(item.published_at))
        self.assertEqual(list(ProgramApplication.objects.values()), before)
        self.assertTrue(bytes(job.document).startswith(b'%PDF-'))
        self.assertIn('PDF', job.body)
        personalized = self.pdf_converter.call_args.args[0][0]
        with ZipFile(BytesIO(personalized)) as document, ZipFile(TEMPLATE) as original:
            xml = document.read('word/document.xml')
            ET.fromstring(xml)
            self.assertIn(self.member.full_name.encode(), xml)
            self.assertIn(self.program.name.encode(), xml)
            self.assertNotIn(b'[Recipient Name:', xml)
            self.assertNotIn(b'Date here', xml)
            for name in original.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(document.read(name), original.read(name))

    def test_application_email_takes_precedence_without_invalid_fallback(self):
        self.application.refresh_from_db()
        self.application.source_snapshot['application_confirmation'] = {'applicant_email': 'application@example.invalid'}
        self.application.save()
        self.publish()
        self.assertEqual(Email.objects.get().recipient, 'application@example.invalid')

    def test_missing_email_can_be_corrected_before_any_delivery_attempt(self):
        self.member.email = ''
        self.member.save()
        self.publish()
        self.assertEqual(Email.objects.get().reason, 'missing')
        self.member.email = 'corrected@example.invalid'
        self.member.save()
        with self.enabled():
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 1)
        job = Email.objects.get()
        self.assertEqual(job.recipient, 'corrected@example.invalid')
        self.assertEqual(job.state, 'queued')

    def test_invalid_application_address_is_not_replaced_by_member_email(self):
        self.application.refresh_from_db()
        self.application.source_snapshot['application_confirmation'] = {'applicant_email': 'invalid'}
        self.application.save()
        self.publish()
        job = Email.objects.get()
        self.assertEqual((job.recipient, job.reason), ('', 'invalid'))

    def test_republication_never_duplicates_certificate(self):
        self.publish()
        first = Email.objects.get()
        self.publish()
        self.assertEqual(Email.objects.count(), 1)
        current = Email.objects.get()
        self.assertEqual((current.pk, bytes(current.document), current.revision_id),
                         (first.pk, bytes(first.document), first.revision_id))

    def test_rollback_drops_publication_jobs_and_callbacks(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.publish()
                raise RuntimeError('Synthetic rollback')
        self.assertFalse(Email.objects.exists())
        self.assertFalse(Announcement.objects.exists())
        self.assertEqual(callbacks, [])

    def test_pdf_failure_rolls_back_publication_and_all_emails(self):
        self.pdf_converter.side_effect = ValidationError('Certificate PDF conversion failed.')
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(ValidationError):
                self.publish()
        self.assertFalse(Email.objects.exists())
        self.assertFalse(Announcement.objects.exists())
        self.assertEqual(callbacks, [])

    @patch('announcements.certificate_delivery.send_certificate', return_value='synthetic-provider-id')
    def test_after_commit_send_acceptance_and_repeat_delivery_guard(self, send):
        with self.enabled():
            self.publish()
            job = Email.objects.get()
            self.assertTrue(deliver_certificate(job.pk))
            self.assertFalse(deliver_certificate(job.pk))
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
        send.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, 'sent')
        self.assertEqual(job.provider_id, 'synthetic-provider-id')
        self.assertEqual(job.attempts.count(), 1)
        self.assertEqual(job.sender, 'certificates@example.invalid')

    @patch('announcements.certificate_delivery.send_certificate')
    def test_timeout_safe_retry_uses_identical_content_and_stops_after_window(self, send):
        send.side_effect = ResendFailure('connection', uncertain=True)
        with self.enabled():
            self.publish()
            job = Email.objects.get()
            self.assertFalse(deliver_certificate(job.pk))
            self.member.email = 'different@example.invalid'
            self.member.save()
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 1)
            self.assertFalse(deliver_certificate(job.pk))
            self.assertEqual(send.call_args_list[0].args[0].recipient, send.call_args_list[1].args[0].recipient)
            job.refresh_from_db()
            with certificate_write():
                job.first_attempt_at = timezone.now() - timedelta(hours=24)
                job.save(update_fields=['first_attempt_at'])
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
        self.assertEqual(send.call_count, 2)

    @patch('announcements.certificate_delivery.send_certificate')
    def test_setup_and_withdrawn_selection_prevent_network_delivery(self, send):
        self.publish()
        job = Email.objects.get()
        self.assertFalse(deliver_certificate(job.pk))
        with self.enabled():
            retry_certificates(self.program.pk, user=self.admin)
            from ewaf.operational_models import OperationalDecision
            decision = OperationalDecision.objects.get(application=self.application)
            self.choose(decision.run, expected_revision=decision.revision, outcome='NOT_SELECTED')
            self.assertFalse(deliver_certificate(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.reason, 'changed')
        send.assert_not_called()

    def test_private_download_status_permissions_and_csrf(self):
        item = self.publish()
        job = Email.objects.get()
        download = reverse('announcements:certificate_download', args=[job.pk])
        self.assertEqual(Client().get(download).status_code, 302)
        response = self.client.get(download)
        self.assertEqual(response.content, bytes(job.document))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('Certificate.pdf', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        for route in ('announcements:detail', 'core:result_detail'):
            response = Client().get(reverse(route, args=[item.pk]))
            self.assertNotContains(response, self.member.email)
            self.assertNotContains(response, str(job.pk))
            self.assertNotContains(response, download)
        user = get_user_model().objects.create_user('certificate-no-permissions', is_staff=True)
        with self.enabled(), self.assertRaises(PermissionDenied):
            retry_certificates(self.program.pk, user=user)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(reverse('announcements:certificate_retry', args=[self.program.pk])).status_code, 403)

    def test_immutable_document_and_history(self):
        self.publish()
        job = Email.objects.get()
        with self.assertRaises(PermissionDenied):
            job.save()
        with certificate_write(), self.assertRaises(PermissionDenied):
            job.save(update_fields=['document'])
        with self.assertRaises(PermissionDenied):
            Email.objects.all().delete()
        with self.assertRaises(PermissionDenied):
            SelectionCertificateAttempt.objects.all().update(error_code='changed')

    def test_certificate_xml_escapes_names_and_programs(self):
        data = certificate_document(member_name='Peña & Dela Cruz <Sample>',
            program_name='Food & Medicine', issued_on=timezone.localdate())
        with ZipFile(BytesIO(data)) as document:
            root = ET.fromstring(document.read('word/document.xml'))
            text = ''.join(root.itertext())
            self.assertIn('Peña & Dela Cruz <Sample>', text)
            self.assertIn('Food & Medicine', text)

    def test_placeholder_like_member_text_is_not_reinterpreted(self):
        data = certificate_document(member_name='Example [PROGRAM NAME]',
            program_name='Food Assistance', issued_on=timezone.localdate())
        with ZipFile(BytesIO(data)) as document:
            self.assertIn('Example [PROGRAM NAME]', ''.join(
                ET.fromstring(document.read('word/document.xml')).itertext()))

    @patch('announcements.resend_mail.urlopen')
    def test_resend_payload_is_private_with_attachment_and_stable_idempotency(self, network):
        self.publish()
        job = Email.objects.get()
        job.sender = 'certificates@example.invalid'
        network.return_value.__enter__.return_value.read.return_value = b'{"id":"test-id"}'
        with self.enabled():
            self.assertEqual(send_certificate(job), 'test-id')
        request = network.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.resend.com/emails')
        self.assertEqual(request.get_header('Idempotency-key'), f'selection-certificate/{job.pk}')
        payload = json.loads(request.data)
        self.assertEqual(payload['to'], [self.member.email])
        self.assertNotIn('cc', payload)
        self.assertNotIn('bcc', payload)
        self.assertEqual(payload['attachments'][0]['filename'], 'Santolan-PWD-Certificate.pdf')
        self.assertEqual(base64.b64decode(payload['attachments'][0]['content']), bytes(job.document))

    @patch('announcements.resend_mail.urlopen')
    def test_provider_failures_never_store_provider_response_or_secret(self, network):
        self.publish()
        job = Email.objects.get()
        for error, code, unknown in (
            (HTTPError('https://api.resend.com/emails', 403, 'private secret details', {}, None), 'domain', False),
            (HTTPError('https://api.resend.com/emails', 429, 'private recipient', {}, None), 'rate_limit', False),
            (URLError('private recipient and credentials'), 'connection', True),
        ):
            network.side_effect = error
            with self.assertRaises(ResendFailure) as raised:
                send_certificate(job)
            self.assertEqual((str(raised.exception), raised.exception.uncertain), (code, unknown))

    def test_test_domain_cannot_enable_member_delivery(self):
        with self.enabled(), self.settings(RESEND_FROM_EMAIL='onboarding@resend.dev'):
            self.assertEqual(setup_problem(), 'domain')


@override_settings(CERTIFICATE_RESEND_ENABLED=True, CERTIFICATE_EMAIL_BACKGROUND=False,
                   RESEND_API_KEY='synthetic-test-key', RESEND_FROM_EMAIL='certificates@example.invalid')
class CertificateConcurrencyTests(OperationalHelpers, TransactionTestCase):
    @patch('announcements.certificate_delivery.send_certificate', return_value='synthetic-concurrent-id')
    def test_simultaneous_workers_submit_certificate_once(self, send):
        from scripts.durable_test_runner import require_disposable
        require_disposable()
        CertificateDeliveryTests.setUp(self)
        plan = recorded_preview(self.program.pk, user=self.admin)
        publish_recorded_results(self.program.pk, user=self.admin,
            expected=plan['expected'], version=plan['version'],
            selection_reason='Synthetic human-reviewed selections within the program capacity.')
        job = Email.objects.get()
        ready = Barrier(2)

        def worker():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return deliver_certificate(job.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            self.assertEqual(sorted(future.result(timeout=20) for future in futures), [False, True])
        send.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, 'sent')
        self.assertEqual(job.attempts.count(), 1)
