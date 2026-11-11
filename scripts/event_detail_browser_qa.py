"""Event Details layout and existing protected forms, using disposable records only."""
from datetime import datetime, time, timedelta
from io import BytesIO
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from events.models import Event, EventLog
from events.services import save_event
from events.tests import event_data
from scripts.durable_test_runner import require_disposable


class EventDetailBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_reference_layout_and_publication_controls(self):
        require_disposable()
        actor = get_user_model().objects.create_superuser('synthetic_event_detail')
        start = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=3), time(9)))
        # A visibly fictional bitmap tests the protected image route and resizing.
        poster = Image.new('RGB', (960, 280), '#102142')
        draw = ImageDraw.Draw(poster)
        draw.rectangle((28, 28, 932, 252), outline='#99c6ff', width=2)
        draw.text((70, 100), 'FICTIONAL COMMUNITY EVENT', fill='#99c6ff', font_size=34)
        draw.text((70, 154), 'Layout validation image - no real event content', fill='#c0cfe6', font_size=22)
        image_data = BytesIO()
        poster.save(image_data, format='PNG')
        item = save_event(user=actor, data=event_data(title='Community Wellness Gathering',
            description='A fictional community activity for checking the event details layout.\n\n'
                        'The complete saved description remains visible in the overview, including multiple paragraphs.',
            location='Synthetic Community Hall, Santolan', starts_at=start, ends_at=start + timedelta(hours=4)),
            files=MultiValueDict({'image': [SimpleUploadedFile('synthetic-event.png', image_data.getvalue(), content_type='image/png')]}))
        for index in range(22):
            EventLog.objects.create(event=item, actor=actor, actor_label=actor.username,
                                    action='updated', notes=f'Synthetic historical update {index + 1}.')
        client = Client()
        client.force_login(actor)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'event-detail-browser'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/event_detail_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
            'QA_SESSION': client.cookies['sessionid'].value,
            'QA_LIST': reverse('events:manage_list'),
            'QA_DETAIL': reverse('events:manage_detail', args=[item.pk]),
            'QA_EDIT': reverse('events:edit', args=[item.pk]),
            'QA_IMAGE': reverse('events:preview_image', args=[item.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=150,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.history.filter(action='published').count(), 1)
        self.assertEqual(item.history.filter(action='draft').count(), 1)
        self.assertEqual(Event.objects.count(), 1)
        print(result.stdout, flush=True)
