"""Direct Gmail setup and sending; provider calls use synthetic test doubles."""
import json
import smtplib
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import referral_services as service
from .referral_connection import (SMTP_BACKEND, EmailConnectionRequired, check_gmail_login,
    connection_status, decrypt_password, encrypt_password, transport_for)
from .referral_mail import deliver_email, retry_email
from .referral_models import ReferralSettings, ReferralSettingsEvent
from .test_referrals import Fixtures


PASSWORD = 'abcdefghijklmnop'  # Deliberately fictional; never sent to a provider.


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GmailConnectionTests(Fixtures, TestCase):
    def connect(self, sender='association@example.invalid', password=PASSWORD):
        row = ReferralSettings.objects.get(pk=1)
        with patch('assistance.referral_connection.check_gmail_login') as login:
            result = service.set_sender(user=self.admin, data={
                'version': row.version, 'sender_email': sender,
                'gmail_app_password': password, 'reason': 'Connect the approved mail account.',
            })
        login.assert_called_once_with(sender, ''.join(password.split()))
        return result

    def test_password_is_encrypted_bound_to_sender_and_not_in_history_or_html(self):
        row = self.connect(password='abcd efgh ijkl mnop')
        self.assertNotIn(PASSWORD, row.gmail_password_encrypted)
        self.assertEqual(decrypt_password(row.sender_email, row.gmail_password_encrypted), PASSWORD)
        with self.assertRaises(EmailConnectionRequired):
            decrypt_password('different@example.invalid', row.gmail_password_encrypted)
        self.assertNotIn(PASSWORD, json.dumps(list(ReferralSettingsEvent.objects.values()), default=str))
        self.client.force_login(self.admin)
        page = self.client.get(reverse('assistance:referral_email_settings'))
        self.assertContains(page, 'Email connection configured.')
        self.assertContains(page, 'type="password"')
        self.assertNotContains(page, 'name="reason"')
        self.assertNotContains(page, PASSWORD)
        self.assertNotContains(page, row.gmail_password_encrypted)

    def test_login_checks_tls_authentication_without_sending_mail(self):
        with patch('assistance.referral_connection.get_connection') as connection:
            check_gmail_login('synthetic@example.invalid', PASSWORD)
        connection.assert_called_once_with(backend=SMTP_BACKEND, host='smtp.gmail.com', port=587,
            username='synthetic@example.invalid', password=PASSWORD, use_tls=True, use_ssl=False, timeout=10)
        connection.return_value.send_messages.assert_not_called()
        connection.return_value.open.assert_called_once()
        connection.return_value.close.assert_called_once()

    def test_login_success_is_preserved_when_quit_disconnects(self):
        with patch('assistance.referral_connection.get_connection') as connection:
            connection.return_value.close.side_effect = smtplib.SMTPServerDisconnected('Synthetic QUIT')
            check_gmail_login('synthetic@example.invalid', PASSWORD)
        connection.return_value.open.assert_called_once()
        connection.return_value.send_messages.assert_not_called()

    def test_same_sender_can_reconnect_and_http_errors_never_echo_the_secret(self):
        self.client.force_login(self.admin)
        row = ReferralSettings.objects.get(pk=1)
        data = {'version': row.version, 'sender_email': row.sender_email, 'gmail_app_password': PASSWORD}
        with patch('assistance.referral_connection.check_gmail_login',
                   side_effect=ValidationError('Could not connect to Gmail.')):
            page = self.client.post(reverse('assistance:referral_email_settings'), data)
        self.assertContains(page, 'Could not connect to Gmail.', status_code=400)
        self.assertNotContains(page, PASSWORD, status_code=400)
        self.assertEqual(ReferralSettings.objects.get(pk=1).gmail_password_encrypted, '')
        with patch('assistance.referral_connection.check_gmail_login') as login:
            page = self.client.post(reverse('assistance:referral_email_settings'), data)
        self.assertEqual(page.status_code, 302)
        login.assert_called_once_with(row.sender_email, PASSWORD)
        saved = ReferralSettings.objects.get(pk=1)
        self.assertEqual(decrypt_password(saved.sender_email, saved.gmail_password_encrypted), PASSWORD)

    def test_connection_form_requires_permission_and_csrf_before_checking_credentials(self):
        url = reverse('assistance:referral_email_settings')
        data = {'version': 1, 'sender_email': 'association@example.invalid', 'gmail_app_password': PASSWORD}
        with patch('assistance.referral_connection.check_gmail_login') as login:
            self.client.force_login(self.viewer)
            self.assertEqual(self.client.post(url, data).status_code, 403)
            secured = Client(enforce_csrf_checks=True)
            secured.force_login(self.admin)
            self.assertEqual(secured.post(url, data).status_code, 403)
        login.assert_not_called()

    def test_invalid_login_retains_previous_settings_and_does_not_echo_password(self):
        row = self.connect()
        with patch('assistance.referral_connection.get_connection',
                   side_effect=smtplib.SMTPAuthenticationError(535, PASSWORD.encode())):
            with self.assertRaisesMessage(ValidationError, 'Google could not sign in.') as error:
                service.set_sender(user=self.admin, data={'version': row.version,
                    'sender_email': 'replacement@example.invalid',
                    'gmail_app_password': PASSWORD, 'reason': 'Change account.'})
        self.assertNotIn(PASSWORD, str(error.exception))
        retained = ReferralSettings.objects.get(pk=1)
        self.assertEqual((retained.sender_email, retained.version, retained.gmail_password_encrypted),
                         (row.sender_email, row.version, row.gmail_password_encrypted))

    def test_settings_reconnects_account_and_records_audit_without_exposing_password(self):
        original = self.connect()
        self.client.force_login(self.admin)
        with patch('assistance.referral_connection.check_gmail_login') as login:
            response = self.client.post(reverse('assistance:referral_email_settings'), {
                'version': original.version, 'sender_email': 'new@example.invalid',
                'gmail_app_password': PASSWORD, 'reason': 'Untrusted extra input',
            })
        login.assert_called_once_with('new@example.invalid', PASSWORD)
        self.assertRedirects(response, reverse('assistance:referral_email_settings'))
        row = ReferralSettings.objects.get(pk=1)
        self.assertEqual(row.sender_email, 'new@example.invalid')
        self.assertEqual(decrypt_password(row.sender_email, row.gmail_password_encrypted), PASSWORD)
        event = ReferralSettingsEvent.objects.get(version=row.version)
        self.assertEqual(event.reason, 'Association Gmail connection updated from settings.')
        self.assertEqual((event.before, event.after, event.actor),
            (original.sender_email, row.sender_email, self.admin))

    def test_email_only_settings_rejects_stale_and_invalid_submissions_without_history(self):
        self.client.force_login(self.admin)
        count = ReferralSettingsEvent.objects.count()
        for values in ({'version': 0, 'sender_email': 'new@example.invalid'},
                       {'version': 1, 'sender_email': 'invalid'}):
            response = self.client.post(reverse('assistance:referral_email_settings'), values)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(ReferralSettingsEvent.objects.count(), count)
        self.assertEqual(ReferralSettings.objects.get(pk=1).sender_email, 'association@example.invalid')

    def test_email_only_unchanged_address_preserves_connection_and_history(self):
        original = self.connect()
        self.client.force_login(self.admin)
        count = ReferralSettingsEvent.objects.count()
        response = self.client.post(reverse('assistance:referral_email_settings'), {
            'version': original.version, 'sender_email': original.sender_email,
        })
        self.assertContains(response, 'Enter a different email address.', status_code=400)
        row = ReferralSettings.objects.get(pk=1)
        self.assertEqual(row.gmail_password_encrypted, original.gmail_password_encrypted)
        self.assertEqual(ReferralSettingsEvent.objects.count(), count)

    def test_permission_stale_version_and_invalid_format_fail_before_login(self):
        data = {'version': 1, 'sender_email': 'new@example.invalid',
                'gmail_app_password': PASSWORD, 'reason': 'Change account.'}
        with patch('assistance.referral_connection.check_gmail_login') as login:
            with self.assertRaises(PermissionDenied):
                service.set_sender(user=self.viewer, data=data)
            for changes in ({'version': 0}, {'gmail_app_password': 'ordinary-password'}):
                with self.assertRaises(ValidationError):
                    service.set_sender(user=self.admin, data=data | changes)
        login.assert_not_called()

    def test_audit_failure_rolls_back_account_and_encrypted_password(self):
        original = self.connect()
        with patch('assistance.referral_connection.check_gmail_login'), \
                patch('assistance.referral_services.ReferralSettingsEvent.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                service.set_sender(user=self.admin, data={'version': original.version,
                    'sender_email': 'new@example.invalid', 'gmail_app_password': PASSWORD, 'reason': 'Change account.'})
        row = ReferralSettings.objects.get(pk=1)
        self.assertEqual((row.sender_email, row.version, row.gmail_password_encrypted),
                         (original.sender_email, original.version, original.gmail_password_encrypted))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend')
    def test_changing_address_without_password_disconnects_and_blocks_send_without_writes(self):
        ticket = self.submit()
        original = self.connect()
        changed = service.set_sender(user=self.admin, data={'version': original.version,
            'sender_email': 'new@example.invalid', 'reason': 'Change account.'})
        self.assertEqual(changed.gmail_password_encrypted, '')
        self.assertFalse(connection_status(changed)['ready'])
        with self.assertRaisesMessage(ValidationError, 'Connect this Gmail account'):
            self.review(ticket)
        ticket.refresh_from_db()
        self.assertEqual((ticket.version, ticket.status, ticket.emails.count()), (0, 'received', 1))

    def test_stale_sender_from_open_composer_cannot_silently_use_replacement(self):
        ticket = self.submit()
        composed = self.review_data()
        self.connect('replacement@example.invalid')
        with self.assertRaisesMessage(ValidationError, 'Association email settings changed'):
            service.review_ticket(ticket.pk, user=self.admin, data=composed)
        self.assertEqual(ticket.emails.count(), 1)

    def test_direct_reply_uses_settings_account_and_request_recipient_with_no_private_notes(self):
        ticket = self.submit()
        self.connect('connected@example.invalid')
        # Deliberately retain a development outbox as the global default: the
        # account connected in Settings must select Gmail SMTP itself.
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend'), \
                patch('assistance.referral_mail.get_connection') as connection, \
                self.captureOnCommitCallbacks(execute=True):
            connection.return_value.send_messages.return_value = 1
            self.review(ticket, member_message='A reply typed inside the system.')
        connection.assert_called_once_with(backend=SMTP_BACKEND, host='smtp.gmail.com', port=587,
            username='connected@example.invalid', password=PASSWORD, use_tls=True, use_ssl=False, timeout=10)
        message = connection.return_value.send_messages.call_args.args[0][0]
        self.assertEqual(message.to, [self.data['email']])
        self.assertEqual(message.reply_to, ['connected@example.invalid'])
        self.assertIn('<connected@example.invalid>', message.from_email)
        self.assertIn('A reply typed inside the system.', message.body)
        self.assertNotIn('Private staff note', message.body)
        job = ticket.emails.order_by('-created_at').first()
        self.assertEqual((job.state, job.backend, job.attempt_count), ('sent', SMTP_BACKEND, 1))
        self.assertFalse(deliver_email(job.pk))

    def test_old_queued_sender_is_never_sent_from_new_account(self):
        ticket = self.submit()
        job = ticket.emails.get()
        self.connect('replacement@example.invalid')
        with patch('assistance.referral_mail.get_connection') as connection:
            self.assertFalse(deliver_email(job.pk))
        connection.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.sender, 'association@example.invalid')
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempts.get().error_type, 'EmailConnectionRequired')

    def test_provider_failure_is_redacted_and_retry_keeps_original_sender(self):
        ticket = self.submit()
        self.connect()
        with patch('assistance.referral_mail.get_connection',
                   side_effect=smtplib.SMTPAuthenticationError(535, PASSWORD.encode())), \
                self.captureOnCommitCallbacks(execute=True):
            self.review(ticket)
        job = ticket.emails.order_by('-created_at').first()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempts.get().error_type, 'SMTPAuthenticationError')
        with patch('assistance.referral_mail.get_connection') as connection, self.captureOnCommitCallbacks(execute=True):
            connection.return_value.send_messages.return_value = 1
            retry_email(job.pk, user=self.admin, reason='Reconnected the account.', confirmed=True)
        job.refresh_from_db()
        self.assertEqual((job.state, job.attempt_count), ('sent', 2))
        self.assertEqual(job.sender, 'association@example.invalid')

    def test_server_key_rotation_fails_closed_without_fallback_and_supports_fallback(self):
        from django.conf import settings
        original_key = settings.SECRET_KEY
        encrypted = encrypt_password('synthetic@example.invalid', PASSWORD)
        with override_settings(SECRET_KEY='another-generated-test-key-' * 3):
            with self.assertRaises(EmailConnectionRequired):
                decrypt_password('synthetic@example.invalid', encrypted)
            with override_settings(SECRET_KEY_FALLBACKS=[original_key]):
                self.assertEqual(decrypt_password('synthetic@example.invalid', encrypted), PASSWORD)
