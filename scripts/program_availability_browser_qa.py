"""Explicit G07-B browser checks; run only with a disposable local MySQL test DB."""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone

from programs.models import Program


class ProgramAvailabilityBrowserTests(StaticLiveServerTestCase):
    def run_browser(self, fixtures):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', str(root / 'scripts/program_availability_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAMS': json.dumps(fixtures)},
            capture_output=True, text=True, encoding='utf-8', timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)

    def test_lifecycle_filters_details_and_accessibility(self):
        now = timezone.now()

        def program(name, **changes):
            return Program.objects.create(**{
                'name': name, 'description': 'Synthetic browser guidance only.',
                'assistance_type': 'Synthetic support', 'status': 'published',
                'published_at': now - timedelta(days=2), 'policy_authorized_at': now - timedelta(days=2),
                'registration_opens_at': now - timedelta(days=1),
                'registration_closes_at': now + timedelta(days=1),
                'selection_method': 'Synthetic selection guidance.',
                'photo_instructions': 'Synthetic photo guidance.', **changes,
            })

        opened = [program(f'Synthetic open program {index}') for index in range(12)]
        fixtures = {'open': opened[0],
            'upcoming': program('Synthetic upcoming program', registration_opens_at=now + timedelta(hours=1)),
            'ended': program('Synthetic ended program', registration_closes_at=now - timedelta(hours=1)),
            'cancelled': program('Synthetic cancelled program', status='cancelled'),
            'unavailable': program('Synthetic unavailable program', photo_instructions='\t')}
        program('Synthetic hidden draft', status='draft', published_at=None)
        self.run_browser({key: str(value.pk) for key, value in fixtures.items()})

    def test_empty_catalog_and_category(self):
        self.run_browser({})
