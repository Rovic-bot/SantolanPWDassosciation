"""Browser acceptance using only disposable fictional registration data."""
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
from membership.registration_models import RegistrationIntake
from membership.test_pdf_registration import association_data, pdao_data, pdf_policy
from scripts.durable_test_runner import require_disposable


class DualRegistrationBrowserTests(StaticLiveServerTestCase):
    def test_forms_receipt_printing_and_staff_review(self):
        require_disposable()
        password = secrets.token_urlsafe(32)
        actor = get_user_model().objects.create_superuser('fictional_pdf_browser', password=password)
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': actor.username,
            'QA_PASSWORD': password, 'QA_ASSOCIATION': json.dumps(association_data()),
            'QA_PDAO': json.dumps(pdao_data())}
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy()):
            result = subprocess.run(['node', str(root/'scripts/dual_registration_browser.cjs')],
                cwd=root, env=env, text=True, encoding='utf-8', capture_output=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)
