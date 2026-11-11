"""Transport acceptance boundaries without any external connection."""
import smtplib
from types import SimpleNamespace
from unittest.mock import Mock

from django.core.mail import BadHeaderError, EmailMessage
from django.test import SimpleTestCase

from .email_delivery import (EmailDeliveryUnconfirmed, EmailNotAccepted,
                            delivery_help, delivery_unconfirmed, send_message)


class EmailDeliveryTests(SimpleTestCase):
    def message(self):
        connection = Mock()
        connection.send_messages.return_value = 1
        return EmailMessage('Synthetic notice', 'Synthetic content',
            'association@example.invalid', ['recipient@example.invalid'], connection=connection)

    def test_successful_submission_is_not_reversed_by_quit_failure(self):
        message = self.message()
        message.connection.close.side_effect = smtplib.SMTPServerDisconnected('private detail')
        send_message(message)
        message.connection.open.assert_called_once_with()
        message.connection.send_messages.assert_called_once_with([message])
        message.connection.close.assert_called_once_with()

    def test_connection_and_authentication_failures_never_submit(self):
        for error in (smtplib.SMTPServerDisconnected('private'), TimeoutError('private'),
                      smtplib.SMTPAuthenticationError(535, b'private')):
            with self.subTest(error=type(error).__name__):
                message = self.message()
                message.connection.open.side_effect = error
                with self.assertRaises(type(error)):
                    send_message(message)
                message.connection.send_messages.assert_not_called()
                message.connection.close.assert_called_once()

    def test_disconnect_during_submission_has_no_automatic_retry_or_private_diagnostics(self):
        message = self.message()
        message.connection.send_messages.side_effect = smtplib.SMTPServerDisconnected('private')
        with self.assertRaises(EmailDeliveryUnconfirmed) as caught:
            send_message(message)
        self.assertNotIn('private', str(caught.exception))
        message.connection.send_messages.assert_called_once()

    def test_explicit_provider_rejections_and_zero_acceptance_remain_failures(self):
        for error in (smtplib.SMTPRecipientsRefused({'recipient@example.invalid': (550, b'private')}),
                      smtplib.SMTPSenderRefused(550, b'private', 'association@example.invalid'),
                      smtplib.SMTPDataError(550, b'private')):
            with self.subTest(error=type(error).__name__):
                message = self.message()
                message.connection.send_messages.side_effect = error
                with self.assertRaises(type(error)):
                    send_message(message)
        message = self.message()
        message.connection.send_messages.return_value = 0
        with self.assertRaises(EmailNotAccepted):
            send_message(message)

    def test_invalid_headers_fail_before_opening_connection(self):
        message = self.message()
        message.subject = 'Invalid\nheader'
        with self.assertRaises(BadHeaderError):
            send_message(message)
        message.connection.open.assert_not_called()
        message.connection.send_messages.assert_not_called()

    def test_failure_guidance_distinguishes_missing_connection_and_unconfirmed_delivery(self):
        attempts = Mock()
        job = SimpleNamespace(state='failed', attempts=attempts)
        attempts.order_by.return_value.first.return_value = SimpleNamespace(error_type='EmailConnectionRequired')
        self.assertIn('Connect that Gmail account', delivery_help(job))
        self.assertFalse(delivery_unconfirmed(job))
        attempts.order_by.return_value.first.return_value.error_type = 'EmailDeliveryUnconfirmed'
        self.assertIn('duplicate', delivery_help(job))
        self.assertTrue(delivery_unconfirmed(job))
