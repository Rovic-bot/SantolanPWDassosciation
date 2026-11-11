"""Event calendar and image submission against disposable synthetic data only."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from announcements.tests import image_upload
from events.models import Event
from scripts.durable_test_runner import require_disposable


class EventBuilderBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_calendar_image_and_private_draft_save(self):
        require_disposable()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'event-builder-browser'
        output.mkdir()
        image_path = output / 'synthetic-event.png'
        image_path.write_bytes(image_upload().read())
        actor = get_user_model().objects.create_superuser('synthetic_event_builder', password=None)
        client = Client()
        client.force_login(actor)
        result = subprocess.run(['node', 'scripts/event_builder_browser_qa.cjs'], env={
            **os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
            'QA_CREATE_ROUTE': reverse('events:create'), 'QA_IMAGE': str(image_path),
            'QA_ADMIN_SESSION': client.cookies['sessionid'].value,
        }, capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        event = Event.objects.get()
        self.assertEqual(event.title, 'Synthetic Santolan Community Day')
        self.assertEqual(event.description, 'A revised synthetic accessible community gathering.')
        self.assertEqual(event.location, 'Synthetic updated community hall')
        self.assertEqual(event.event_category, 'general')
        self.assertEqual(event.status, 'published')
        self.assertIsNotNone(event.published_at)
        self.assertIsNone(event.capacity)
        self.assertIsNone(event.application_program_id)
        self.assertEqual(timezone.localtime(event.starts_at).strftime('%Y-%m-%d %H:%M'), '2027-02-02 10:30')
        self.assertEqual(timezone.localtime(event.ends_at).strftime('%Y-%m-%d %H:%M'), '2027-02-07 18:15')
        self.assertTrue(event.image.storage.exists(event.image.name))
        self.assertEqual(event.image_alt, f'Event image for {event.title}')
        self.assertEqual(list(event.history.order_by('occurred_at','pk').values_list('action',flat=True)),
                         ['created','updated','published','updated'])
        public = Client()
        self.assertContains(public.get(reverse('events:detail', args=[event.pk]), {'popup': '1'}), event.description)
        image_response = public.get(reverse('events:image', args=[event.pk]))
        try:
            self.assertEqual(image_response.status_code, 200)
        finally:
            image_response.close()
        print(result.stdout, flush=True)
