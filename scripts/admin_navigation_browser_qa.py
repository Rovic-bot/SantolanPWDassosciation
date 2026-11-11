"""Eight-module navigation acceptance in disposable MySQL and temporary media."""
import os
from pathlib import Path
import secrets
import subprocess
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from core.tests.test_workspace_navigation import grant
from assistance.tests import seed_statuses
from programs.tests import create_program
from programs.testsupport import private_media


class AdminNavigationBrowserTests(StaticLiveServerTestCase):
    def test_modules_permissions_disclosures_scroll_and_responsive_navigation(self):
        private_media(self)
        seed_statuses()
        password = secrets.token_urlsafe(32)
        admin = get_user_model().objects.create_superuser('navigation_browser_admin', password=password)
        encoder = get_user_model().objects.create_user('navigation_browser_encoder', password=password, is_staff=True)
        grant(encoder, 'accounts.access_dashboard', 'membership.view_membershipapplication',
              'membership.encode_membershipapplication', 'auth.view_user', 'auth.change_user',
              'auth.view_group', 'auth.change_group')
        program = create_program()
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root/'scripts/admin_navigation_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': admin.username,
                 'QA_PASSWORD': password, 'QA_ENCODER': encoder.username, 'QA_PROGRAM': str(program.pk)},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
