"""Membership placeholders, income controls, pending email and private print popup."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from assistance.referral_models import ReferralSettings, referral_write
from members.models import Member
from membership.pending_email_models import MembershipPendingEmail
from membership.test_registration_decisions import DecisionHelpers
from scripts.durable_test_runner import require_disposable


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MembershipPendingBrowserTests(DecisionHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_pending_message_income_and_form_preview(self):
        require_disposable()
        self.setup_decisions()
        intake = self.make(invited=False)
        original = intake.revisions.get().data
        self.client.force_login(self.actor)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []
        folder = Path(os.environ['G12_ARTIFACT_DIR']) / 'membership-pending-browser'
        folder.mkdir()
        result = subprocess.run(['node', 'scripts/membership_pending_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(folder),
            'QA_SESSION': self.client.cookies['sessionid'].value,
            'QA_ROUTE': reverse('membership:registration_detail', args=[intake.reference]),
            'QA_PUBLIC_ROUTE': reverse('membership:registration_apply'),
            'QA_RECIPIENT': original['email']}, capture_output=True, text=True, encoding='utf-8',
            timeout=150, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        intake.refresh_from_db()
        self.assertIsNone(intake.membership_application_id)
        self.assertEqual(intake.revisions.get().data, original)
        self.assertFalse(Member.objects.exists())
        notice = MembershipPendingEmail.objects.get()
        self.assertEqual((notice.state, notice.attempt_count), ('sent', 1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [original['email']])
        self.assertIn('Please bring a clear copy of your PWD ID.', mail.outbox[0].body)
        (folder / 'results.json').write_text(json.dumps({'pending_retained': True,
            'one_test_outbox_message': True, 'saved_recipient_used': True, 'submission_unchanged': True,
            'income_start': 1000, 'income_step': 500, 'typed_exact_and_zero_income_allowed': True,
            'private_print_popup': True, 'widths': [1440, 390]}, indent=2), encoding='utf-8')
