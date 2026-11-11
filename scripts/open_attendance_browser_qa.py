"""Open-attendance Chrome acceptance in the disposable MySQL test database."""
from datetime import timedelta
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from events.models import EventAttendance
from events.tests import create_event, historical_registration
from members.tests import create_member
from membership.tests import grant


class OpenAttendanceBrowserTests(StaticLiveServerTestCase):
    def test_open_attendance_in_chrome(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        officer = get_user_model().objects.create_user('open_attendance_browser', password=password, is_staff=True)
        grant(officer, 'accounts.access_dashboard', 'events.view_event', 'events.view_eventattendance',
              'events.add_eventattendance', 'events.change_eventattendance', 'events.view_eventattendancelog',
              'events.view_eventregistration', 'members.view_member')
        event = create_event(starts_at=timezone.now()-timedelta(hours=1), ends_at=timezone.now()+timedelta(hours=1), capacity=1)
        member = create_member('OPEN-BROWSER')
        member.is_active = False
        member.archived_at = timezone.now()
        member.save()
        legacy = historical_registration(event, member)
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': officer.username,
               'QA_PASSWORD': password, 'QA_EVENT': str(event.pk), 'QA_MEMBER': str(member.pk)}
        result = subprocess.run(['node', str(root / 'scripts/open_attendance_browser_qa.cjs')],
            cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(EventAttendance.objects.count(), 2)
        visitor = EventAttendance.objects.get(attendee_name='Synthetic nonmember visitor')
        linked = EventAttendance.objects.get(member=member)
        self.assertIsNone(visitor.member_id)
        self.assertEqual((visitor.status, visitor.version, visitor.history.count()), ('absent', 2, 2))
        self.assertEqual((linked.status, linked.history.count()), ('attended', 1))
        self.assertEqual(set(visitor.history.values_list('actor_id', flat=True)), {officer.pk})
        legacy.refresh_from_db()
        self.assertEqual((legacy.status, legacy.version, legacy.history.count()), ('registered', 0, 1))
        self.assertFalse(officer.is_superuser)
