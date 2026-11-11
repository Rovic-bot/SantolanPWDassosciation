from datetime import timedelta
from importlib import import_module
import smtplib
from unittest.mock import Mock, patch

from django.apps import apps
from django.core import mail
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from assistance.referral_models import ReferralSettings, referral_write
from .certificate_delivery import deliver_certificate, retry_certificates, retryable, certificate_context
from .certificate_mail import DeliveryFailure, send_certificate
from .certificate_models import SelectionCertificateEmail as Email, certificate_write
from . import test_certificate_delivery as fixtures


@override_settings(CERTIFICATE_EMAIL_PROVIDER='gmail', CERTIFICATE_EMAIL_BACKGROUND=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GmailCertificateTests(fixtures.OperationalHelpers, TestCase):
    publish = fixtures.CertificateDeliveryTests.publish

    def setUp(self):
        fixtures.CertificateDeliveryTests.setUp(self)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')

    def test_selected_certificate_uses_saved_gmail_sender_and_private_attachment(self):
        self.publish()
        job = Email.objects.get()
        self.assertEqual((job.provider, job.state), ('gmail', 'queued'))
        self.assertTrue(deliver_certificate(job.pk))
        self.assertFalse(deliver_certificate(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.state, 'sent')
        self.assertEqual(job.provider_id, '')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.member.email])
        self.assertEqual(message.cc, [])
        self.assertEqual(message.bcc, [])
        self.assertIn('association@example.invalid', message.from_email)
        self.assertEqual(message.attachments[0].content, bytes(job.document))
        self.assertEqual(message.attachments[0].filename, 'Santolan-PWD-Certificate.pdf')
        self.assertEqual(message.attachments[0].mimetype, 'application/pdf')
        self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
        context = certificate_context(self.program, self.admin)
        self.assertEqual(context['certificate_jobs'][0].delivery_label, 'Accepted by Gmail')

    def test_unconfirmed_smtp_send_is_never_automatically_retried(self):
        self.publish()
        job = Email.objects.get()
        with patch('announcements.certificate_delivery.send_certificate',
                side_effect=DeliveryFailure('gmail_uncertain', uncertain=True)) as send:
            self.assertFalse(deliver_certificate(job.pk))
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
            self.assertFalse(deliver_certificate(job.pk))
        self.assertEqual(send.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertFalse(retryable(job))

    def test_crashed_gmail_worker_claim_cannot_be_reclaimed(self):
        self.publish()
        job = Email.objects.get()
        with certificate_write():
            job.state, job.acceptance_unknown = 'sending', True
            job.first_attempt_at = job.last_attempt_at = timezone.now() - timedelta(minutes=10)
            job.save(update_fields=['state', 'acceptance_unknown', 'first_attempt_at', 'last_attempt_at'])
        self.assertFalse(retryable(job))

    def test_authentication_failure_is_retryable_without_exposing_details(self):
        self.publish()
        job = Email.objects.get()
        with patch('announcements.certificate_mail.get_connection') as create:
            create.return_value.open.side_effect = smtplib.SMTPAuthenticationError(535, b'private detail')
            self.assertFalse(deliver_certificate(job.pk))
        job.refresh_from_db()
        self.assertEqual((job.state, job.reason, job.acceptance_unknown), ('failed', 'gmail_setup', False))
        self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 1)
        self.assertTrue(deliver_certificate(job.pk))

    def test_smtp_data_failure_classification_and_quit_after_acceptance(self):
        self.publish()
        job = Email.objects.get()
        job.sender = 'association@example.invalid'
        for error, unknown in [(smtplib.SMTPDataError(550, b'private'), False),
                               (smtplib.SMTPServerDisconnected('private'), True)]:
            with patch('announcements.certificate_mail.get_connection') as create:
                create.return_value.send_messages.side_effect = error
                with self.assertRaises(DeliveryFailure) as raised:
                    send_certificate(job)
                self.assertEqual(raised.exception.uncertain, unknown)
                self.assertNotIn('private', str(raised.exception))
        with patch('announcements.certificate_mail.get_connection') as create:
            create.return_value.send_messages.return_value = 1
            create.return_value.close.side_effect = smtplib.SMTPServerDisconnected('QUIT')
            self.assertEqual(send_certificate(job), '')

    def test_saved_provider_is_not_changed_by_new_configuration(self):
        self.publish()
        job = Email.objects.get()
        with self.settings(CERTIFICATE_EMAIL_PROVIDER='resend', CERTIFICATE_RESEND_ENABLED=False):
            self.assertTrue(deliver_certificate(job.pk))
        self.assertEqual(len(mail.outbox), 1)


class GmailCertificateMigrationTests(TransactionTestCase):
    def test_provider_field_defaults_to_resend_for_historical_records(self):
        from scripts.durable_test_runner import require_disposable
        require_disposable()
        state = ProjectState.from_apps(apps)
        state.remove_field('announcements', 'selectioncertificateemail', 'provider')
        migration = import_module('announcements.migrations.0007_certificate_email_provider').Migration(
            '0007_certificate_email_provider', 'announcements')
        field = Email._meta.get_field('provider')
        try:
            with connection.schema_editor() as editor:
                editor.remove_field(Email, field)
            with connection.schema_editor() as editor:
                migration.apply(state, editor)
            with connection.cursor() as cursor:
                columns = connection.introspection.get_table_description(cursor, Email._meta.db_table)
                self.assertIn('provider', {column.name for column in columns})
            operation = next(op for op in migration.operations if type(op).__name__ == 'AddField')
            self.assertEqual(operation.field.default, 'resend')
        finally:
            with connection.cursor() as cursor:
                names = {col.name for col in connection.introspection.get_table_description(cursor, Email._meta.db_table)}
            if 'provider' not in names:
                with connection.schema_editor() as editor:
                    editor.add_field(Email, field)
