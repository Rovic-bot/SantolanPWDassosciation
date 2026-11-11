"""Fictional Gmail setup/replies, with all provider calls replaced locally."""
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.mail.backends.locmem import EmailBackend
from django.test import Client, override_settings
from django.urls import reverse

from assistance.referral_models import ReferralSettings
from assistance.test_referrals import Fixtures
from scripts.durable_test_runner import require_disposable


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend')
class DirectGmailBrowserTests(Fixtures, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_settings_connect_change_sender_and_compose_without_opening_gmail(self):
        require_disposable()
        ticket = self.submit()
        client = Client()
        client.force_login(self.admin)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'direct-gmail-browser'
        output.mkdir()
        with patch('assistance.referral_connection.check_gmail_login') as login, \
                patch('assistance.referral_mail.get_connection', side_effect=EmailBackend):
            result = subprocess.run(['node', 'scripts/direct_gmail_browser_qa.cjs'], env={**os.environ,
                'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                'QA_SESSION': client.cookies['sessionid'].value,
                'QA_INBOX': reverse('assistance:referral_inbox'),
                'QA_MEMBERS': reverse('member_directory'),
                'QA_SETTINGS': reverse('assistance:referral_email_settings')},
                capture_output=True, text=True, encoding='utf-8', timeout=120,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(login.call_count, 2)
        ticket.refresh_from_db()
        self.assertEqual(ticket.emails.count(), 3)
        replies = list(ticket.emails.exclude(action__action='submitted').order_by('created_at'))
        self.assertEqual([reply.sender for reply in replies], ['first@example.invalid', 'second@example.invalid'])
        self.assertTrue(all(reply.state == 'sent' for reply in replies))
        self.assertTrue(all(reply.recipient == 'fictional@example.invalid' for reply in replies))
        self.assertFalse(any('Private staff note' in reply.body for reply in replies))
        self.assertEqual(ReferralSettings.objects.get(pk=1).gmail_password_encrypted, '')
        print(result.stdout, flush=True)
