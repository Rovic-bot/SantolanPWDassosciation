"""Local layout shift diagnosis; synthetic superuser and loopback requests only."""
import json
import os
from pathlib import Path
import subprocess
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from scripts.durable_test_runner import require_disposable

@override_settings(EWAF_VAULT_ENABLED=True, PDAO_REGISTRATION_ENABLED=True)
class LayoutShiftAudit(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_layout_shifts(self):
        require_disposable()
        user = get_user_model().objects.create_superuser('fictional_layout_audit')
        self.client.force_login(user)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'layout-shifts.json'
        result = subprocess.run(['node', 'scripts/quality_layout_shifts.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_SESSION': self.client.cookies['sessionid'].value},
            capture_output=True, text=True, encoding='utf-8', timeout=240,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)
