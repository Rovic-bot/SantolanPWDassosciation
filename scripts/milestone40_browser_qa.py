"""Optional milestone browser test: synthetic records in Django's disposable test database."""
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from announcements.models import Announcement
from announcements.tests import image_upload
from members.models import Member
from members.tests import create_member


class Milestone40BrowserTests(StaticLiveServerTestCase):
    def test_member_and_publishing_workflows(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('milestone40_browser', password=password)
        member = create_member('BROWSER-40')
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = Path(directory) / 'fixture.png'
            image.write_bytes(image_upload().read())
            env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': 'milestone40_browser',
                   'QA_PASSWORD': password, 'QA_MEMBER_ID': str(member.pk), 'QA_IMAGE': str(image)}
            result = subprocess.run(['node', str(root / 'scripts/milestone40_browser_qa.cjs')],
                cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=240)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
            member.refresh_from_db()
            self.assertEqual(member.full_name, 'Updated Browser Member')
            self.assertEqual(member.application.full_name, 'Sample Applicant')
            self.assertEqual(member.status, 'active')
            self.assertEqual(member.events.count(), 3)
            self.assertEqual(Member.objects.count(), 1)
            item = Announcement.objects.get()
            self.assertEqual(item.status, 'deleted')
            self.assertGreaterEqual(item.events.count(), 6)
