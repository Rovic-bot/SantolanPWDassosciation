"""Draft, published edit and archive checks using only disposable records."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from programs.models import Program
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class ProgramLifecycleBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_program_lifecycle(self):
        require_disposable()
        user = get_user_model().objects.create_superuser('lifecycle_browser')
        program = create_program(name='Synthetic published program', benefit='Synthetic support',
                                 ewaf_applicable=False, policy_authorized_by=user)
        client = Client()
        client.force_login(user)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-lifecycle-browser'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/program_lifecycle_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_EDIT': reverse('programs:edit', args=[program.pk]),
                 'QA_DETAIL': reverse('programs:manage_detail', args=[program.pk]),
                 'QA_BUILDER': reverse('program_builder'), 'QA_PORTFOLIO': reverse('program_portfolio'),
                 'QA_ADMIN_SESSION': client.cookies['sessionid'].value},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        program.refresh_from_db()
        self.assertEqual(program.name, 'Updated published program')
        self.assertEqual(program.status, 'archived')
        draft = Program.objects.exclude(pk=program.pk).get()
        self.assertEqual(draft.status, 'draft')
        self.assertIsNone(draft.registration_closes_at)
        self.assertIsNotNone(draft.registration_opens_at)
