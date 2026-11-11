"""Chrome event workflow using synthetic records and the disposable test database."""
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
from announcements.tests import image_upload
from events.models import Event, EventRegistration
from members.tests import create_member


class EventBrowserTests(StaticLiveServerTestCase):
    def test_event_publishing_registration_and_attendance(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('events_browser', password=password)
        member = create_member('BROWSER-50')
        member.contact_number = '09171234567'
        member.save()
        now = timezone.localtime().replace(second=0, microsecond=0)
        schedule = {name: (now + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M') for name, hours in {
            'registration_opens_at': -48, 'registration_closes_at': 24, 'starts_at': 48, 'ends_at': 50}.items()}
        past_schedule = {name: (now + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M') for name, hours in {
            'registration_opens_at': -48, 'registration_closes_at': -24, 'starts_at': -2, 'ends_at': -1}.items()}
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            fixture = Path(media) / 'event.png'
            fixture.write_bytes(image_upload().read())
            env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': 'events_browser', 'QA_PASSWORD': password,
                   'QA_MEMBER_ID': str(member.pk), 'QA_BIRTHDATE': str(member.birthdate), 'QA_IMAGE': str(fixture),
                   'QA_SCHEDULE': json.dumps(schedule), 'QA_PAST_SCHEDULE': json.dumps(past_schedule)}
            result = subprocess.run(['node', str(root / 'scripts/milestone50_browser_qa.cjs')], cwd=root,
                env=env, capture_output=True, text=True, encoding='utf-8', timeout=300)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
            self.assertEqual(Event.objects.get().status, 'archived')
            registration = EventRegistration.objects.get()
            self.assertEqual(registration.status, 'attended')
            self.assertEqual(registration.member, member)
            self.assertEqual(registration.history.count(), 5)
