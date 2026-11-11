"""Read-only activity UI checks against fictional, disposable MySQL records."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse

from audit.test_activity import activity_fixture
from programs.models import ProgramLog
from programs.testsupport import private_media


class ActivityBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_filters_details_and_responsive_layout(self):
        private_media(self)
        actor, program, application, logs = activity_fixture()
        ProgramLog.objects.bulk_create([ProgramLog(program=program, actor=actor, actor_label=actor.username,
            action='updated', notes=f'Fictional program correction {number}.') for number in range(32)])
        before = list(ProgramLog.objects.values())
        client = Client()
        client.force_login(actor)
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'admin-activity-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/admin_activity_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_ADMIN_SESSION': client.cookies['sessionid'].value,
            'QA_OUTPUT': str(directory), 'QA_ROUTE': reverse('admin:admin_logentry_changelist')},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(ProgramLog.objects.values()), before)
        print(result.stdout, flush=True)
