"""Review layout and retained decision controls, using disposable records only."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from members.models import Member
from membership.test_registration_decisions import DecisionHelpers
from membership.test_registration_intake import staff, upload
from membership.tests import grant
from scripts.durable_test_runner import require_disposable


class AssociationReviewBrowserTests(DecisionHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_review_fields_permissions_and_layout(self):
        require_disposable()
        self.setup_decisions()
        grant(self.actor, 'membership.view_registration_documents')
        pending = self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        approved = self.make(data={'last_name': 'Approved', 'pwd_number': '00-0000-000-0000002'})
        self.decide(approved, self.data(approved, last_name='Approved'))
        declined = self.make(data={'last_name': 'Declined', 'pwd_number': '00-0000-000-0000003'})
        self.decide(declined, self.data(declined, last_name='Declined', action='decline_registration'))
        self.client.force_login(self.actor)
        routes = {name: reverse('membership:registration_detail', args=[item.reference])
                  for name, item in [('pending', pending), ('approved', approved), ('declined', declined)]}
        response = self.client.get(routes['pending'])
        self.assertEqual(response.status_code, 200)
        fields = [field.name for field in response.context['editor_form'].visible_fields()]
        viewer = Client()
        viewer.force_login(staff('synthetic_review_viewer'))
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'association-review-browser'
        directory.mkdir()
        invalid = self.client.post(routes['pending'], self.data(pending, first_name=''))
        self.assertEqual(invalid.status_code, 400)
        (directory / 'invalid.html').write_bytes(invalid.content)
        result = subprocess.run(['node', 'scripts/association_review_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url,
                 'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
                 'QA_VIEWER_SESSION': viewer.cookies['sessionid'].value,
                 'QA_ROUTES': json.dumps(routes), 'QA_FIELDS': json.dumps(fields),
                 'QA_OUTPUT': str(directory)},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pending.refresh_from_db()
        self.assertIsNone(pending.membership_application_id)
        self.assertEqual(pending.current_revision, 1)
        self.assertEqual(Member.objects.count(), 1)
        print(f'Association review browser evidence: {directory}\n{result.stdout}', flush=True)
