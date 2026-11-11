import json
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from assistance.services import decide_assistance
from assistance.tests import decision_data
from ewaf.operational_testsupport import OperationalHelpers
from membership.tests import grant
from programs.workflow import review_photo


class ChecklistBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_clickable_checklist_and_inline_review_workflow(self):
        self.setup_operational()
        grant(self.officer, 'membership.view_membershipapplication')
        decide_assistance(self.application.pk, user=self.officer,
            data=decision_data(self.application, decision='pending'))
        self.application.refresh_from_db()
        review_photo(self.application.pk, user=self.officer, data={'version': self.application.version,
            'photo_id': str(self.application.current_photo_id), 'outcome': 'NEEDS_RESUBMISSION',
            'category': 'Fictional test', 'reason': 'Fictional identity check pending.', 'confirm': True})
        original_history = self.application.current_photo.reviews.count()
        client = Client()
        client.force_login(self.officer)
        root = Path(settings.BASE_DIR)
        output = root / '.local/checklist-ui/browser'
        output.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['node', str(root / 'scripts/checklist_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url,
                 'QA_APPLICATION': reverse('programs:application_detail', args=[self.program.pk, self.application.pk]),
                 'QA_PR_EVIDENCE': str(self.criterion_reviews['PR'].pk),
                 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                 'QA_OUTPUT': str(output)}, capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')
        self.assertEqual(self.application.current_photo.reviews.count(), original_history + 1)
        self.assertEqual(self.application.current_photo.reviews.first().reviewer_id, self.officer.pk)
