"""Public/staff rendered-page audit on fictional disposable records only."""
import json
import os
import subprocess
from pathlib import Path

from django.contrib.auth.models import User
from config.registration_workflow import association_policy
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_VAULT_ENABLED=True, REFERRAL_ENABLED=True,
                   PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, ONLINE_MEMBERSHIP_ENABLED=True, PDAO_REGISTRATION_ENABLED=True,
                   ASSOCIATION_REGISTRATION_POLICY=association_policy(5 * 1048576, 15 * 1048576))
class QualityBrowserAudit(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_rendered_pages(self):
        require_disposable()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'browser'
        output.mkdir()
        routes = ['/', '/about/', '/announcements/', '/events/', '/programs/',
                  '/membership/register/', '/resources/', '/information/privacy/',
                  '/information/accessibility/', '/accounts/login/', '/membership/registration/apply/', '/membership/registration/pdao/apply/']
        staff = ['/dashboard/', '/members/', '/programs/manage/', '/events/manage/',
                 '/workspace/applications/', '/ewaf/', '/assistance/', '/reports/members/',
                 '/content/', '/admin/', '/membership/registration/pdao/onsite/']
        queries = []
        for url in routes:
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(url)
            queries.append({'route': url, 'status': response.status_code, 'queries': len(captured)})
        user = User.objects.create_superuser('fictional_quality_auditor')
        self.client.force_login(user)
        (output / 'queries.json').write_text(json.dumps(queries, indent=2))
        result = subprocess.run(['node', 'scripts/quality_audit_browser.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_ROUTES': json.dumps(routes), 'QA_STAFF': json.dumps(staff),
                 'QA_SESSION': self.client.cookies['sessionid'].value},
            capture_output=True, text=True, encoding='utf-8', timeout=600,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        print('Browser audit artifacts:', output, flush=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)
