"""Firefox/WebKit acceptance against synthetic disposable records only."""
import json
import os
from pathlib import Path
import subprocess
from django.contrib.auth.models import User
from config.registration_workflow import association_policy
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_VAULT_ENABLED=True, REFERRAL_ENABLED=True,
                   PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, ONLINE_MEMBERSHIP_ENABLED=True,
                   PDAO_REGISTRATION_ENABLED=True,
                   ASSOCIATION_REGISTRATION_POLICY=association_policy(5 * 1048576, 15 * 1048576))
class CrossBrowserAudit(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def audit(self, engine):
        require_disposable()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / ('crossbrowser-' + engine)
        output.mkdir()
        public = ['/', '/about/', '/announcements/', '/events/', '/programs/',
                  '/membership/register/', '/resources/', '/information/privacy/',
                  '/information/accessibility/', '/accounts/login/',
                  '/membership/registration/apply/', '/membership/registration/pdao/apply/']
        staff = ['/dashboard/', '/members/', '/programs/manage/', '/events/manage/',
                 '/workspace/applications/', '/ewaf/', '/assistance/', '/reports/members/', '/content/', '/admin/',
                 '/membership/registration/pdao/onsite/']
        user = User.objects.create_superuser('synthetic_crossbrowser_auditor')
        self.client.force_login(user)
        result = subprocess.run(['node', 'scripts/quality_crossbrowser.cjs'],
            env={**os.environ, 'QA_ENGINE': engine, 'QA_URL': self.live_server_url,
                 'QA_OUTPUT': str(output), 'QA_ROUTES': json.dumps(public), 'QA_STAFF': json.dumps(staff),
                 'QA_SESSION': self.client.cookies['sessionid'].value},
            capture_output=True, text=True, encoding='utf-8', timeout=600,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)

    def test_firefox_routes_keyboard_and_reflow(self):
        self.audit('firefox')

    def test_webkit_routes_keyboard_and_reflow(self):
        self.audit('webkit')
