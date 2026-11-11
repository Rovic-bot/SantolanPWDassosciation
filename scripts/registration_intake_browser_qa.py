"""Isolated browser journey with explicitly fictional policy parameters."""
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from members.models import Member
from membership.models import MembershipApplication
from membership.registration_models import RegistrationIntake, RegistrationRevision
from membership.test_registration_intake import synthetic_policy, staff
from scripts.durable_test_runner import require_disposable


class RegistrationIntakeBrowserTests(StaticLiveServerTestCase):
    def test_synthetic_pending_intake_to_authorized_review_and_access_boundaries(self):
        require_disposable()
        actor = staff('synthetic_registration_browser', 'membership.encode_registrationintake',
            'membership.review_registrationintake', 'membership.correct_registrationintake',
            'membership.onsite_registrationintake', 'membership.view_registration_documents')
        password = secrets.token_urlsafe(32)
        actor.set_password(password)
        actor.save()
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': actor.username, 'QA_PASSWORD': password}
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(onsite_enabled=True)):
            result = subprocess.run(['node', str(root / 'scripts/registration_intake_browser_qa.cjs')],
                cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 2)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)
