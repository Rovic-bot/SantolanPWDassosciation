"""Event workspace browser validation on a verified disposable database."""
from datetime import datetime, time, timedelta
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from events.annual_calendar import publish_annual_calendar
from events.models import Event, EventRegistration
from events.tests import create_event
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class EventsWorkspaceBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_events_calendar_interactions_and_layout(self):
        require_disposable()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'events-workspace-browser'
        output.mkdir()
        actor = get_user_model().objects.create_superuser('synthetic_events_browser', password=None)
        start = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=2), time(9)))
        members = [create_member(f'SYNTH-EVENTS-BROWSER-{index}') for index in range(6)]
        specs = [
            ('Medical Access Week Orientation', 'general', 'Santolan community hall', 0, 4, 5),
            ('Assistive Device Distribution', 'specific', 'Santolan covered court', 4, 3, 4),
            ('PWD Sports Festival', 'general', 'Santolan sports complex', 7, 5, 8),
            ('Inclusive Livelihood Lab', 'specific', 'Livelihood center', 10, 2, 3),
            ('International Day of Persons with Disabilities', 'general', 'Pasig community plaza', 25, 6, 5),
        ]
        for index, (title, category, location, offset, count, capacity) in enumerate(specs):
            event = create_event(title=title, event_category=category, location=location,
                starts_at=start + timedelta(days=offset), ends_at=start + timedelta(days=offset, hours=3), capacity=capacity)
            if index == 1:
                program = create_program(name=title, slots=capacity, assistance_type='Assistive Devices')
                Event.objects.filter(pk=event.pk).update(application_program=program)
                for member_index in range(count):
                    ProgramApplication.objects.create(program=program, member=members[member_index],
                        public_reference=f'SYNTH-EVENTS-APP-{member_index}')
                EventRegistration.objects.create(event=event, member=members[0])
            else:
                for member_index in range(count):
                    EventRegistration.objects.create(event=event, member=members[member_index])
        for status in ('draft', 'cancelled'):
            event = create_event(title=f'Synthetic {status} event', event_category='general', starts_at=start + timedelta(days=12),
                ends_at=start + timedelta(days=12, hours=2), capacity=None)
            Event.objects.filter(pk=event.pk).update(status=status, published_at=timezone.now() if status == 'cancelled' else None)
        create_event(title='Past community gathering', event_category='general',
            starts_at=start - timedelta(days=30), ends_at=start - timedelta(days=30, hours=-2))
        publish_annual_calendar(user=actor, notes='Synthetic browser annual calendar.')
        client = Client()
        client.force_login(actor)
        result = subprocess.run(['node', 'scripts/events_workspace_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output), 'QA_ROUTE': reverse('event_workspace'),
            'QA_MONTH': start.strftime('%Y-%m'), 'QA_DAY': start.date().isoformat(),
            'QA_ADMIN_SESSION': client.cookies['sessionid'].value}, capture_output=True, text=True,
            encoding='utf-8', timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Event.objects.count(), 8)
        print(result.stdout, flush=True)
