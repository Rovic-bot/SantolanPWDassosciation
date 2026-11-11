"""Program archive controls and popup submission, using disposable records only."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from programs.services import save_program
from programs.tests import create_program
from programs.testsupport import private_media
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ProgramArchiveBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_program_archive_controls_and_popup(self):
        require_disposable()
        private_media(self)
        actor = get_user_model().objects.create_superuser('synthetic_archive_admin')
        published = create_program(name='Synthetic published program', policy_authorized_by=actor)
        draft = save_program(user=actor, data={'version': 0, 'name': 'Synthetic unused draft'})
        published_at = published.published_at
        client = Client()
        client.force_login(actor)
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-archive-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/program_archive_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
            'QA_SESSION': client.cookies['sessionid'].value,
            'QA_PORTFOLIO': reverse('program_portfolio'),
            'QA_PUBLISHED': reverse('programs:manage_detail', args=[published.pk]),
            'QA_DRAFT': reverse('programs:manage_detail', args=[draft.pk]),
            'QA_PUBLIC': reverse('programs:detail', args=[published.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        published.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual((published.status, draft.status), ('archived', 'archived'))
        self.assertEqual(published.published_at, published_at)
        self.assertIsNone(draft.published_at)
        self.assertEqual(published.history.get(action='archived').notes, 'Synthetic program withdrawal.')
        self.assertEqual(draft.history.get(action='archived').notes, 'Synthetic unused draft archived.')
        print(result.stdout, flush=True)
