"""Exercise one-click configuration approval against disposable MySQL only."""
import os
from pathlib import Path
import subprocess
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from ewaf.vault_models import VaultRevision
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_VAULT_ENABLED=True)
class VaultBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory(prefix='vault-browser-media-')
        self.addCleanup(media.cleanup)
        options = override_settings(MEDIA_ROOT=media.name)
        options.enable()
        self.addCleanup(options.disable)

    def test_one_click_approval_and_weight_changes(self):
        require_disposable()
        admin = get_user_model().objects.create_superuser('fictional-vault-browser', password='synthetic-only')
        client = Client()
        client.force_login(admin)
        root = Path(__file__).resolve().parents[1]
        output = root / 'docs/ewaf-one-click-2026-10-25'
        output.mkdir(parents=True, exist_ok=True)
        process = subprocess.run(['node', str(root / 'scripts/ewaf_vault_browser_qa.cjs')],
            cwd=root, env={**os.environ, 'QA_URL': self.live_server_url,
                'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': str(output)},
            capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(VaultRevision.objects.count(), 2)
        for row in VaultRevision.objects.all():
            row.clean()
        self.assertNotEqual(VaultRevision.objects.first().judgments, VaultRevision.objects.last().judgments)
        print(process.stdout)
