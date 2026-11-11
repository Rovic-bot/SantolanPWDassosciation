"""Optional browser integration check. See docs/authentication-validation.md."""
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase


class PortalBrowserTests(StaticLiveServerTestCase):
    def test_browser_workflows(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('browser_test_admin', password=password)
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_USERNAME': 'browser_test_admin', 'QA_PASSWORD': password}
        result = subprocess.run(['node', str(root / 'scripts/browser_qa.cjs')],
                                cwd=root, env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
