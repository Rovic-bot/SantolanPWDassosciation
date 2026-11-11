"""Synthetic browser approval in verified disposable MySQL only."""
import json
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from membership.test_registration_handoff import HandoffHelpers
from members.models import Member
from scripts.durable_test_runner import require_disposable


class RegistrationApprovalBrowserTests(HandoffHelpers, StaticLiveServerTestCase):
    def test_pending_registration_to_authorized_member(self):
        require_disposable()
        self.setup_handoff()
        intake = self.make()
        password = secrets.token_urlsafe(32)
        self.actor.set_password(password)
        self.actor.save(update_fields=['password'])
        root = Path(__file__).resolve().parents[1]
        data = dict(self.form(intake).data.items())
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': self.actor.username,
            'QA_PASSWORD': password, 'QA_REFERENCE': intake.reference, 'QA_DATA': json.dumps(data),
            'QA_REQUIREMENT': str(self.requirement.pk)}
        result = subprocess.run(['node', str(root / 'scripts/registration_approval_browser.cjs')],
            cwd=root, env=env, text=True, encoding='utf-8', capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        intake.refresh_from_db()
        self.assertEqual(intake.membership_application.status, 'approved')
        self.assertEqual(Member.objects.filter(application=intake.membership_application).count(), 1)
