"""Public navigation and Home information checks against disposable MySQL."""
import os
from pathlib import Path
import subprocess
from django.contrib.staticfiles.testing import StaticLiveServerTestCase


class PublicNavigationBrowserTests(StaticLiveServerTestCase):
    def test_public_pages_home_sections_and_accessible_navigation(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', str(root / 'scripts/public_navigation_browser_qa.cjs')],
            cwd=root, env={**os.environ, 'QA_URL': self.live_server_url},
            capture_output=True, text=True, encoding='utf-8', timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
