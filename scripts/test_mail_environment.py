"""Local launch never inherits real mail credentials without explicit opt-in."""
import os
from unittest import TestCase
from unittest.mock import patch

from scripts.ewaf_twelve_demo import environment


class MailEnvironmentTests(TestCase):
    @patch.dict(os.environ, {'RESEND_API_KEY': 'synthetic-key',
        'RESEND_FROM_EMAIL': 'sender@example.invalid'}, clear=True)
    def test_local_launch_requires_explicit_resend_opt_in(self):
        self.assertNotIn('RESEND_API_KEY', environment())
        with patch.dict(os.environ, {'CERTIFICATE_RESEND_ENABLED': 'True'}):
            self.assertEqual(environment()['RESEND_API_KEY'], 'synthetic-key')

    @patch.dict(os.environ, {'EMAIL_HOST_USER': 'synthetic@example.invalid',
        'EMAIL_HOST_PASSWORD': 'fictional-test-secret', 'EMAIL_BACKEND': 'arbitrary.backend'}, clear=True)
    def test_default_launch_excludes_smtp_credentials(self):
        result = environment()
        self.assertNotIn('EMAIL_HOST_USER', result)
        self.assertNotIn('EMAIL_HOST_PASSWORD', result)
        self.assertNotIn('EMAIL_BACKEND', result)

    @patch.dict(os.environ, {'SANTOLAN_DIRECT_EMAIL': '1', 'EMAIL_HOST_USER': 'synthetic@example.invalid',
        'EMAIL_HOST_PASSWORD': 'fictional-test-secret', 'DB_PASSWORD': 'never-inherit',
        'EMAIL_BACKEND': 'arbitrary.backend'}, clear=True)
    def test_explicit_opt_in_passes_only_mail_settings(self):
        result = environment()
        self.assertEqual(result['EMAIL_HOST_USER'], 'synthetic@example.invalid')
        self.assertEqual(result['EMAIL_HOST_PASSWORD'], 'fictional-test-secret')
        self.assertEqual(result['EMAIL_BACKEND'], 'django.core.mail.backends.smtp.EmailBackend')
        self.assertNotIn('DB_PASSWORD', result)
