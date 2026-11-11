"""Program workflow in Chrome with synthetic records and a disposable MySQL database."""
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from members.tests import create_member
from membership.tests import pdf
from programs.models import Program, ProgramApplication


class ProgramBrowserTests(StaticLiveServerTestCase):
    def test_program_configuration_submission_and_review(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('program_browser', password=password)
        member = create_member('BROWSER-60')
        now = timezone.localtime().replace(second=0, microsecond=0)
        schedule = {name: (now + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M') for name, hours in {
            'registration_opens_at': -24, 'registration_closes_at': 24}.items()}
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            fixture = Path(media) / 'proof.pdf'
            fixture.write_bytes(pdf().read())
            env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': 'program_browser', 'QA_PASSWORD': password,
                   'QA_MEMBER_ID': str(member.pk), 'QA_BIRTHDATE': str(member.birthdate), 'QA_DOCUMENT': str(fixture),
                   'QA_SCHEDULE': json.dumps(schedule)}
            result = subprocess.run(['node', str(root / 'scripts/milestone60_browser_qa.cjs')], cwd=root, env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=300)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
            self.assertEqual(Program.objects.get().status, 'archived')
            application = ProgramApplication.objects.get()
            self.assertEqual(application.member, member)
            self.assertEqual(application.status, 'under_review')
            self.assertEqual(application.documents.count(), 1)
            self.assertEqual(len(application.requirements_snapshot), 3)
