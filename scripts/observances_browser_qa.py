"""Annual calendar UI checks using fictional actors and disposable MySQL only."""
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from PIL import Image, ImageDraw
from events.models import AnnualObservance, Event


class ObservancesBrowserTests(StaticLiveServerTestCase):
    def test_calendar_mobile_keyboard_contrast_and_source_preview(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('fictional_calendar_qa', password=password)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            photo = Path(media) / 'fictional-poster.png'
            fixture = Image.new('RGB', (640, 360), '#e9f2ef')
            ImageDraw.Draw(fixture).text((45, 150), 'FICTIONAL OBSERVANCE - BROWSER TEST', fill='#21685e')
            fixture.save(photo)
            result = subprocess.run(['node', str(root / 'scripts/observances_browser_qa.cjs')],
                cwd=root, env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PHOTO': str(photo),
                               'QA_USERNAME': 'fictional_calendar_qa', 'QA_PASSWORD': password},
                capture_output=True, text=True, encoding='utf-8', timeout=240)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(AnnualObservance.objects.get().status, 'published')
            self.assertEqual(AnnualObservance.objects.get().revisions.count(), 5)
            self.assertEqual(Event.objects.count(), 0)
            print(result.stdout)
