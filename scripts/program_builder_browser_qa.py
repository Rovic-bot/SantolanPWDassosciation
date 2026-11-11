"""Program creation browser coverage; all writes use disposable synthetic records."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.utils import timezone

from programs.models import Program, ProgramLog
from programs.test_ui_cleanup import seed_catalog
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class ProgramBuilderBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_builder_calendars_draft_saving_and_layout(self):
        require_disposable()
        seed_catalog()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-builder-browser'
        output.mkdir()
        actor = get_user_model().objects.create_superuser('synthetic_builder_browser', password=None)
        client = Client()
        client.force_login(actor)
        result = subprocess.run(['node', 'scripts/program_builder_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_ADMIN_SESSION': client.cookies['sessionid'].value},
            capture_output=True, text=True, encoding='utf-8', timeout=240,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        item = Program.objects.get()
        self.assertEqual(item.name, 'Synthetic Community Access — updated')
        self.assertEqual(item.status, 'draft')
        self.assertIsNone(item.published_at)
        self.assertIsNone(item.policy_authorized_at)
        self.assertFalse(item.ewaf_applicable)
        self.assertEqual(item.configured_requirements.count(), 3)
        self.assertEqual(timezone.localtime(item.registration_opens_at).strftime('%Y-%m-%d %H:%M'), '2027-02-17 09:00')
        self.assertEqual(timezone.localtime(item.registration_closes_at).strftime('%Y-%m-%d %H:%M'), '2027-02-22 17:00')
        self.assertEqual(timezone.localtime(item.starts_at).strftime('%Y-%m-%d %H:%M'), '2027-03-02 09:00')
        self.assertEqual(timezone.localtime(item.ends_at).strftime('%Y-%m-%d %H:%M'), '2027-03-05 17:00')
        self.assertTrue(ProgramLog.objects.filter(program=item, action='updated', notes='Synthetic title clarification.').exists())
        print(result.stdout, flush=True)
