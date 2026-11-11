"""Popup replies and layout checks using fictional data and local-only mail."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from assistance.test_referrals import Fixtures
from membership.test_pdf_registration import pdf_policy
from scripts.durable_test_runner import require_disposable


@override_settings(REFERRAL_ENABLED=True, PDAO_REGISTRATION_ENABLED=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ASSOCIATION_REGISTRATION_POLICY=pdf_policy(upload_slots=[]))
class AdminCleanupBrowserTests(Fixtures, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_ticket_popup_reply_and_admin_layouts(self):
        require_disposable()
        ticket = self.submit()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'admin-cleanup-browser'
        output.mkdir()
        client = Client()
        client.force_login(self.admin)
        result = subprocess.run(['node', 'scripts/admin_cleanup_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
            'QA_SESSION': client.cookies['sessionid'].value,
            'QA_INBOX': reverse('assistance:referral_inbox')},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'in_review')
        self.assertEqual(ticket.emails.count(), 2)
        reply = ticket.emails.order_by('-created_at').first()
        self.assertEqual(reply.recipient, 'fictional@example.invalid')
        self.assertIn('Synthetic reply from the popup.', reply.body)
        self.assertNotIn('Synthetic private review note.', reply.body)
        self.assertEqual(reply.state, 'sent')
        self.assertEqual(ticket.actions.filter(action='review_started').count(), 1)
        print(result.stdout, flush=True)
