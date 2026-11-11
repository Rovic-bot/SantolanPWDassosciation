"""Registration deadline notices with disposable synthetic program dates."""
from datetime import timedelta
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from programs.models import Program
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class PublicProgramDeadlinesBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_visible_notes_and_live_boundaries(self):
        require_disposable()
        now = timezone.now()
        closing = create_program(name='SYNTHETIC Closing program', ewaf_applicable=True,
            registration_closes_at=now + timedelta(minutes=30))
        later = create_program(name='SYNTHETIC Later registration', ewaf_applicable=True,
            registration_closes_at=now + timedelta(minutes=61))
        create_program(name='SYNTHETIC Closed registration', ewaf_applicable=True,
            registration_closes_at=now - timedelta(minutes=1))
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'public-program-deadlines-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/public_program_deadlines_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
            'QA_DETAIL': reverse('programs:detail', args=[closing.pk]),
            'QA_LATER': reverse('programs:detail', args=[later.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Program.objects.count(), 3)
        closing.refresh_from_db()
        self.assertEqual(closing.registration_closes_at, now + timedelta(minutes=30))
        print(result.stdout, flush=True)
