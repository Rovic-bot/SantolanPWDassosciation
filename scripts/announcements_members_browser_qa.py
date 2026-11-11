"""Synthetic publication and navigation acceptance in disposable MySQL."""
import os
from pathlib import Path
import secrets
import subprocess
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from assistance.services import review_eligibility, decide_assistance
from assistance.tests import seed_statuses, review_data, decision_data
from members.tests import create_member
from programs.tests import create_program
from programs.testsupport import private_media, application_fixture, close_non_ewaf_program
from announcements.models import Announcement


class AnnouncementsMembersBrowserTests(StaticLiveServerTestCase):
    def test_authorized_results_unified_members_and_scroll_preservation(self):
        private_media(self)
        seed_statuses()
        password = secrets.token_urlsafe(32)
        admin = get_user_model().objects.create_superuser('announcement_browser', password=password)
        program = create_program(eligible_disability_types=[])
        member = create_member('BROWSER-ANNOUNCEMENT')
        member.full_name = 'Juan Dela Cruz'
        member.save()
        application = application_fixture(program, member)
        review_eligibility(application.pk, user=admin, data=review_data(application))
        close_non_ewaf_program(program)
        decide_assistance(application.pk, user=admin, data=decision_data(application))
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'QA_URL':self.live_server_url, 'QA_USERNAME':admin.username, 'QA_PASSWORD':password,
               'QA_PROGRAM':str(program.pk), 'QA_REFERENCE':application.public_reference}
        result = subprocess.run(['node', str(root/'scripts/announcements_members_browser_qa.cjs')],
            cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        print(result.stdout)
        item = Announcement.objects.get(program=program)
        self.assertEqual(item.status, 'published')
        self.assertEqual(item.result_revisions.count(), 1)
