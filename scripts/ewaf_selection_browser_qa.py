"""Browser checks use synthetic applications in a verified disposable database."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse

from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_models import OperationalRun, OperationalDecision
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


class EWAFSelectionBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_program_selection_filters_and_service_backed_generation(self):
        require_disposable()
        self.setup_operational(additional=3)
        self.lock_policy()
        other = create_program(name='Synthetic Community Care', ewaf_applicable=True)
        for name in ['Synthetic Mobility Support', 'Synthetic Education Access', 'Synthetic Food Support']:
            create_program(name=name, ewaf_applicable=True)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'ewaf-selection-browser'
        output.mkdir()
        client = Client()
        client.force_login(self.officer)
        result = subprocess.run(['node', 'scripts/ewaf_selection_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
            'QA_SESSION': client.cookies['sessionid'].value,
            'QA_DATA': json.dumps({'ready': str(self.program.pk), 'other': str(other.pk),
                'code': self.program.public_code, 'workspace': reverse('ewaf:operational_workspace', args=[self.program.pk])})},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(OperationalRun.objects.filter(program=self.program).count(), 2)
        self.assertEqual(OperationalDecision.objects.count(), 0)
        for run in OperationalRun.objects.filter(program=self.program):
            run.clean()
        print(result.stdout, flush=True)
