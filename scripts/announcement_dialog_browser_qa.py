"""Announcements preview remains modal after workspace tab navigation."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from announcements.models import Announcement, ProgramResultRevision
from announcements import test_results as result_fixtures
from scripts.durable_test_runner import require_disposable


class AnnouncementDialogBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_tab_preview_is_hidden_when_closed_and_compact_when_open(self):
        require_disposable()
        result_fixtures.ProgramResultTests.setUp(self)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'announcement-dialog-browser'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/announcement_dialog_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_SESSION': self.client.cookies['sessionid'].value,
                 'QA_START': reverse('core:dashboard'),
                 'QA_LIST': reverse('announcements:manage_list'),
                 'QA_PREVIEW': reverse('announcements:prepare_results', args=[self.program.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=120,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(Announcement.objects.exists())
        self.assertFalse(ProgramResultRevision.objects.exists())
        print(result.stdout, flush=True)
