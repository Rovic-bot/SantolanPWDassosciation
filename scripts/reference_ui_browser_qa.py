import json
import os
from pathlib import Path
import subprocess
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from ewaf.operational_testsupport import OperationalHelpers
from programs.catalog import capacity_context


class ReferenceBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_reference_pages_with_real_data_and_private_previews(self):
        self.setup_operational(additional=2)
        self.lock_policy()
        self.choose(self.calculate())
        capacity_context(self.program, self.officer)
        client = Client()
        client.force_login(self.officer)
        root = Path(settings.BASE_DIR)
        output = root / '.local/reference-ui/disposable-browser'
        output.mkdir(parents=True, exist_ok=True)
        data = {'program': str(self.program.pk), 'application': str(self.application.pk),
                'name': self.program.name, 'code': self.program.public_code,
                'type': self.program.assistance_type, 'status': self.program.status,
                'slots': self.program.slots, 'allocated': self.program.allocated_slots,
                'applicants': self.program.applications.count(), 'control': self.member.control_number,
                'reference': self.application.public_reference}
        result = subprocess.run(['node', str(root / 'scripts/reference_ui_browser_qa.cjs')],
            cwd=root, env={**os.environ, 'QA_URL': self.live_server_url, 'QA_REFERENCE': json.dumps(data),
                          'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                          'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': str(output)},
            capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
