"""Tab navigation uses fictional records in a separate disposable MySQL database."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from membership.test_pdf_registration import pdf_policy
from membership.test_registration_intake import synthetic_policy
from scripts import admin_theme_fixtures
from scripts.durable_test_runner import require_disposable


@override_settings(REFERRAL_ENABLED=True, PDAO_REGISTRATION_ENABLED=True,
    ASSOCIATION_REGISTRATION_POLICY=pdf_policy())
class WorkspaceNavigationBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_tabs_preserve_document_scroll_and_page_controls(self):
        require_disposable()
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            admin_theme_fixtures.AdminThemeFixtures.setUpTestData.__func__(type(self))
        client = Client()
        client.force_login(self.admin)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'workspace-navigation-browser'
        output.mkdir()
        routes = {name: reverse(name) for name in (
            'membership:encode', 'membership:review_home', 'membership:registration_inbox',
            'membership:pdao_inbox', 'member_directory', 'program_portfolio',
            'event_workspace', 'application_workspace', 'ewaf_selection', 'core:dashboard',
            'announcements:manage_list', 'core:content_list', 'assistance:referral_inbox',
            'assistance:release_programs', 'reports:members')}
        result = subprocess.run(['node', 'scripts/workspace_navigation_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                'QA_SESSION': client.cookies['sessionid'].value, 'QA_ROUTES': json.dumps(routes)},
            capture_output=True, text=True, encoding='utf-8', timeout=240,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)
