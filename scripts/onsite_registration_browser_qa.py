"""Shared Association forms and onsite PWD requirement on disposable MySQL."""
import json
import os
from pathlib import Path
import subprocess
import time

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from config.registration_workflow import association_policy
from members.models import Member
from membership.models import MembershipSettings
from membership.registration_models import RegistrationIntake
from membership.test_pdf_registration import association_data, pdf_policy
from scripts.durable_test_runner import require_disposable


@override_settings(ASSOCIATION_REGISTRATION_POLICY=association_policy(5242880, 20971520))
class OnsiteRegistrationBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_shared_fields_required_pwd_and_onsite_approval(self):
        require_disposable()
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'onsite-registration-browser'
        directory.mkdir()
        actor = get_user_model().objects.create_superuser('synthetic_onsite_browser', password=None)
        MembershipSettings.objects.update_or_create(pk=1, defaults={
            'prpwd_url': 'https://registry.example.test/manual'})
        admin = Client()
        admin.force_login(actor)
        data = association_data() | {
            'contact_number': '09170000000', 'pwd_number': '00-0000-000-0000001'}
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy()):
            uploads = admin.get(reverse('membership:encode'))
            self.assertEqual(uploads.status_code, 200)
            (directory / 'configured-uploads.html').write_bytes(uploads.content)
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_ADMIN_SESSION': admin.cookies['sessionid'].value,
               'QA_FORM_DATA': json.dumps(data), 'QA_OUTPUT': str(directory),
               'QA_PUBLIC_ROUTE': reverse('membership:registration_apply'),
               'QA_ONSITE_ROUTE': reverse('membership:encode')}
        # File-backed browser output avoids Node's restricted Windows pipe
        # creation. The profile and debugging endpoint belong only to this test.
        profile = directory / 'chrome-profile'
        profile.mkdir()
        browser_path = os.environ.get('CHROME_EXECUTABLE',
                                      r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        with (directory / 'browser.log').open('wb') as log:
            browser = subprocess.Popen([browser_path, '--headless=new', '--disable-gpu',
                '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
                f'--user-data-dir={profile}', 'about:blank'],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                port_file = profile / 'DevToolsActivePort'
                deadline = time.monotonic() + 15
                while not port_file.exists() and browser.poll() is None and time.monotonic() < deadline:
                    time.sleep(.1)
                self.assertTrue(port_file.exists(), 'The isolated browser did not start; see browser.log.')
                env['QA_BROWSER_URL'] = 'http://127.0.0.1:' + port_file.read_text().splitlines()[0]
                result = subprocess.run(['node', 'scripts/onsite_registration_browser_qa.cjs'],
                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=240,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            finally:
                if browser.poll() is None:
                    browser.terminate()
                browser.wait(timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)
        intake = RegistrationIntake.objects.get()
        self.assertEqual(intake.channel, 'walk_in')
        self.assertEqual(intake.revisions.count(), 1)
        member = Member.objects.get()
        self.assertEqual(member.control_number, data['pwd_number'])
        self.assertEqual(member.registration_profile, intake.revisions.get().data)
        self.assertEqual(member.household_members, 5)
        self.assertEqual(str(member.household_monthly_income), '14500.50')
