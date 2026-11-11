import json
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, RequestFactory

from programs.tests import create_program
from ewaf import operational_services as service
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.program_cards import cards


def expected_cards(user):
    request = RequestFactory().get('/ewaf/')
    request.user = user
    return [{'id': str(p.pk), 'code': p.public_code, 'name': p.name,
             'state': p.ewaf_card['state'], 'weights': p.ewaf_card['rows'],
             'total': p.applicant_count, 'eligible': p.eligible_count, 'pending': p.pending_count,
             'used': p.allocated_slots, 'slots': p.slots} for p in cards(request)['page_obj']]


class EWAFCardBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_saved_weights_counts_and_responsive_cards(self):
        self.setup_operational(additional=3)
        self.lock_policy()
        self.choose(self.calculate())
        create_program(name='Fictional unconfigured program with a longer title for wrapping', ewaf_applicable=True)
        draft = create_program(name='Fictional proposed scoring configuration', ewaf_applicable=True)
        service.record_configuration(draft.pk, user=self.officer, expected=service.configuration_token(draft),
            proposed=self.proposal, judgments=self.operational_configuration.judgments,
            status='DRAFT', reason='Fictional draft only, not authorized')
        client = Client()
        client.force_login(self.officer)
        root = Path(settings.BASE_DIR)
        output = root / '.local/ewaf-cards/disposable-browser'
        output.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['node', str(root / 'scripts/ewaf_cards_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_EWAF_CARDS': json.dumps(expected_cards(self.officer)),
                 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                 'QA_OUTPUT': str(output)}, capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
