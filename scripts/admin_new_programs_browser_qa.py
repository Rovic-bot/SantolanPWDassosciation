"""Read-only New filter interactions on a disposable admin portfolio."""
from datetime import timedelta
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from programs.models import Program
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class AdminNewProgramsBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_status_filter_sort_labels_and_theme_layout(self):
        require_disposable()
        actor = get_user_model().objects.create_superuser('SYNTHETIC-NEW-BROWSER')
        now = timezone.now()
        for name, minutes, status, days in (
            ('Z recently published older draft', 1, 'published', 30),
            ('A earlier publication', 25, 'published', 1),
            ('Expired publication', 120, 'published', 0),
            ('Future publication', -5, 'published', 0),
            ('Private draft', 1, 'draft', 0),
            ('Archived program', 1, 'archived', 0),
        ):
            program = create_program(name=name, ewaf_applicable=True, slots=5)
            Program.objects.filter(pk=program.pk).update(status=status,
                published_at=now - timedelta(minutes=minutes), created_at=now - timedelta(days=days))
        client = Client()
        client.force_login(actor)
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'admin-new-programs-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/admin_new_programs_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
            'QA_ADMIN_SESSION': client.cookies['sessionid'].value,
            'QA_ROUTE': reverse('program_portfolio')},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Program.objects.count(), 6)
        print(result.stdout, flush=True)
