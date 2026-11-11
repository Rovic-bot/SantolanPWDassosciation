"""Synthetic browser proof of full pending form and reference-based prefill."""
import json
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from members.models import Member
from membership.models import MembershipApplication
from membership.registration_models import RegistrationIntake, RegistrationRevision
from membership.test_registration_prefill import applicant_data, profile_policy
from scripts.durable_test_runner import require_disposable


class RegistrationPrefillBrowserTests(StaticLiveServerTestCase):
    def test_public_submission_monitoring_and_staff_prefill(self):
        require_disposable()
        password = secrets.token_urlsafe(32)
        actor = get_user_model().objects.create_superuser('synthetic_prefill_browser', password=password)
        data = applicant_data()
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': actor.username,
               'QA_PASSWORD': password, 'QA_FORM_DATA': json.dumps(data)}
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=profile_policy()):
            result = subprocess.run(['node', str(root / 'scripts/registration_prefill_browser.cjs')],
                cwd=root, env=env, text=True, encoding='utf-8', capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)
