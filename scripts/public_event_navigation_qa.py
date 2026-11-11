"""Home-to-Events navigation and popup-only details, with disposable records."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone

from events.tests import create_event
from programs.testsupport import private_media
from scripts.durable_test_runner import require_disposable


class EventNavigationBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_home_card_navigation_popup_retry_and_keyboard(self):
        require_disposable()
        private_media(self)
        now = timezone.now()
        event = create_event(title='Synthetic community gathering',
            starts_at=now - timezone.timedelta(hours=1), ends_at=now + timezone.timedelta(hours=1))
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'event-navigation-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/public_event_navigation_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
            'QA_EVENT_DETAIL': reverse('events:detail', args=[event.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)
