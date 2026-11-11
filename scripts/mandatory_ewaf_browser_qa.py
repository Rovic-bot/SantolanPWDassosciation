"""Required EWAF program setup, using only disposable synthetic records."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from programs.models import Program
from programs.test_ui_cleanup import seed_catalog
from programs.testsupport import private_media
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class MandatoryEWAFBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_required_capacity_and_select_all(self):
        require_disposable()
        private_media(self)
        seed_catalog()
        actor = get_user_model().objects.create_superuser('SYNTHETIC-MANDATORY-EWAF-BROWSER')
        client = Client()
        client.force_login(actor)
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'mandatory-ewaf-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/mandatory_ewaf_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
            'QA_SESSION': client.cookies['sessionid'].value,
            'QA_CREATE': reverse('programs:create')},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        program = Program.objects.get()
        self.assertTrue(program.ewaf_applicable)
        self.assertEqual(program.slots, 4)
        self.assertEqual(program.eligible_disability_types.count(), 10)
        self.assertEqual(program.status, 'draft')
        self.assertIsNone(program.published_at)
        print(result.stdout, flush=True)
