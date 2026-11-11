"""Publication and configuration UI acceptance on disposable MySQL only."""
import os
import subprocess
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from programs.test_approved_terms import TermsHelpers
from programs.test_ui_cleanup import seed_catalog
from programs.tests import create_program
from programs.models import Program


@override_settings(PDAO_ENFORCEMENT_ENABLED=True, EWAF_FICTIONAL_DEMO=True)
class CleanupBrowserTests(TermsHelpers, StaticLiveServerTestCase):
    def test_optional_requirements_publication_pdao_and_guided_settings(self):
        seed_catalog()
        self.setup_terms(draft=True)
        self.program.photo_instructions = ''
        self.program.selection_method = ''
        self.program.requirements = ''
        self.program.save()
        self.reconcile()
        scoring = create_program(name='Fictional settings incomplete', ewaf_applicable=True)
        client = Client()
        client.force_login(self.officer)
        root = Path(settings.BASE_DIR)
        output = root / '.local/ui-cleanup/browser'
        output.mkdir(parents=True, exist_ok=True)
        process = subprocess.run(['node', str(root / 'scripts/ui_cleanup_browser_qa.cjs')],
            cwd=root, env={**os.environ, 'QA_URL': self.live_server_url,
                'QA_PROGRAM': str(self.program.pk), 'QA_SCORING': str(scoring.pk),
                'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                'QA_OUTPUT': str(output)}, capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        print(process.stdout)
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'published')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertFalse(self.program.registration_available)
        created = Program.objects.get(name='Fictional optional requirements browser')
        self.assertEqual(created.status, 'draft')
        self.assertFalse(created.configured_requirements.exists())
        self.assertEqual(created.eligible_disability_types.count(), 2)
