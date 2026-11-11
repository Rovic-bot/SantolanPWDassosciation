"""Populated Admin presentation QA using disposable fixtures and private media."""
import os
from pathlib import Path
import secrets
import subprocess
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from announcements.models import Announcement
from assistance.tests import seed_statuses
from events.tests import create_event
from members.tests import create_member
from programs.tests import create_program
from programs.testsupport import application_fixture, private_media


class AdminUIBrowserTests(StaticLiveServerTestCase):
    def test_populated_admin_pages_and_resilient_icons(self):
        private_media(self)
        seed_statuses()
        password = secrets.token_urlsafe(32)
        admin = get_user_model().objects.create_superuser('ui_sample_admin', password=password, first_name='Sample Admin')
        programs = []
        for index, title in enumerate(('Mobility assistance', 'Livelihood support', 'Community essentials'), 1):
            program = create_program(name='Sample ' + title, assistance_type='Sample assistance', slots=20)
            if index == 3:
                program.status = 'draft'
                program.save(update_fields=['status'])
            programs.append(program)
            member = create_member(f'QA-MEMBER-{index:03}')
            member.full_name = f'Sample Member {index:02}'
            member.save(update_fields=['full_name'])
            application_fixture(program, member)
        create_event(title='Sample community meeting', location='Synthetic Help Desk')
        Announcement.objects.create(title='Sample community update', content='Synthetic notice for visual validation.')
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root / 'scripts/admin_ui_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': admin.username,
                 'QA_PASSWORD': password, 'QA_PROGRAM': str(programs[0].pk)},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
