import json
import smtplib
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings

from .email_delivery import EmailDeliveryUnconfirmed, send_message
from .https_email import EmailBackend, NoRedirect


@override_settings(EMAIL_HTTPS_RELAY_URL='https://aaaaaaaaaaaaaaaaaaaa.supabase.co/functions/v1/deployment-gateway',
                   EMAIL_HTTPS_RELAY_TOKEN='fictional-token-for-isolated-tests-' * 3)
class HttpsEmailTests(SimpleTestCase):
    def backend(self):
        return EmailBackend(username='sender@example.invalid', password='fictional-password')

    def message(self, backend):
        return EmailMessage('Synthetic test', 'Synthetic notice', 'Sender <sender@example.invalid>',
                            ['recipient@example.invalid'], connection=backend)

    def test_authenticates_before_sending_and_submits_only_once(self):
        backend = self.backend()
        with patch.object(backend, '_request', return_value={'ok': True}) as request:
            send_message(self.message(backend))
        self.assertEqual([call.args[0] for call in request.call_args_list], ['verify', 'send'])
        self.assertEqual(request.call_args.kwargs['recipients'], ['recipient@example.invalid'])

    def test_uncertain_http_submission_is_not_reported_as_success(self):
        backend = self.backend()
        with patch.object(backend, '_request', side_effect=[{'ok': True}, OSError('connection lost')]) as request:
            with self.assertRaises(EmailDeliveryUnconfirmed):
                send_message(self.message(backend))
        self.assertEqual(request.call_count, 2)

    def test_gmail_rejection_retains_definite_failure(self):
        backend = self.backend()
        with patch.object(backend, '_request', side_effect=[{'ok': True}, smtplib.SMTPDataError(550,b'rejected')]):
            with self.assertRaises(smtplib.SMTPDataError):
                send_message(self.message(backend))

    def test_sender_is_bound_to_saved_account(self):
        backend = self.backend()
        message = self.message(backend)
        message.from_email = 'different@example.invalid'
        with patch.object(backend, '_request') as request:
            with self.assertRaises(smtplib.SMTPSenderRefused):
                backend.send_messages([message])
        request.assert_not_called()

    def test_provider_responses_and_passwords_are_not_exposed(self):
        backend = self.backend()
        response = Mock(status=422)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({'ok':False,'error':'authentication','detail':'sensitive'}).encode()
        with patch('core.https_email.build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertRaises(smtplib.SMTPAuthenticationError) as captured:
                backend.open()
        self.assertNotIn('sensitive', str(captured.exception))
        self.assertNotIn('fictional-password', str(captured.exception))

    def test_relay_cannot_redirect_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://elsewhere.invalid'))

    def test_rejects_arbitrary_or_insecure_relay_hosts(self):
        for url in ('http://aaaaaaaaaaaaaaaaaaaa.supabase.co/functions/v1/deployment-gateway',
                    'https://elsewhere.invalid/functions/v1/deployment-gateway'):
            with self.subTest(url=url), override_settings(EMAIL_HTTPS_RELAY_URL=url):
                with self.assertRaises(ImproperlyConfigured):
                    self.backend()
