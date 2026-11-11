"""Secure Gmail connection UI against disposable data and mocked authentication."""
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from assistance.referral_models import ReferralSettings, ReferralSettingsEvent
from assistance.test_referrals import Fixtures
from scripts.durable_test_runner import require_disposable


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AssociationEmailBrowserTests(Fixtures, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_connection_save_secret_redaction_and_responsive_history(self):
        require_disposable()
        self.client.force_login(self.admin)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'association-email-browser'
        output.mkdir()
        with patch('assistance.referral_connection.check_gmail_login') as login:
            result = subprocess.run(['node', 'scripts/association_email_browser_qa.cjs'],
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                     'QA_SESSION': self.client.cookies['sessionid'].value,
                     'QA_SETTINGS': reverse('assistance:referral_email_settings')},
                capture_output=True, text=True, encoding='utf-8', timeout=90,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        login.assert_called_once_with('updated.association@example.invalid', 'abcdefghijklmnop')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = ReferralSettings.objects.get(pk=1)
        self.assertEqual(row.sender_email, 'updated.association@example.invalid')
        self.assertEqual(ReferralSettingsEvent.objects.get(version=row.version).reason,
                         'Association Gmail connection updated from settings.')
        self.assertTrue(row.gmail_password_encrypted)
        print(result.stdout, flush=True)
