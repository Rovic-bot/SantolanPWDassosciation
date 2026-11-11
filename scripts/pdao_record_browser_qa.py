"""Synthetic staff PDAO record checks; never creates live applications."""
import os
import json
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from membership import pdao_services as services
from membership.test_pdao_registration import PDAOHelpers, actor
from membership.test_pdf_registration import pdao_data
from membership.pdao_models import PDAORegistration
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAORecordBrowserTests(PDAOHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_record_layout_editing_and_manual_forwarding(self):
        require_disposable()
        item, _ = self.submit()
        original = item.data
        staff = actor(services.VIEW, services.PRINT, services.CORRECT, services.FORWARD, services.ADD,
                      'membership.view_membershipapplication')
        self.client.force_login(staff)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'pdao-record-browser'
        output.mkdir()
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
               'QA_RECORD_ROUTE': reverse('membership:pdao_detail', args=[item.pk]),
               'QA_ONSITE_ROUTE': reverse('membership:pdao_onsite'),
               'QA_PUBLIC_ROUTE': reverse('membership:pdao_apply'),
               'QA_ONSITE_DATA': json.dumps(pdao_data() | {'first_name': 'Onsite'}),
               'QA_OLD_LIST': reverse('membership:list'), 'QA_OUTPUT': str(output)}
        result = subprocess.run(['node', 'scripts/pdao_record_browser_qa.cjs'], env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=150,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        item.refresh_from_db()
        self.assertEqual(item.status, 'forwarded')
        self.assertEqual(item.data, original)
        self.assertEqual(item.current_data['first_name'], 'Reviewed')
        self.assertEqual(item.revisions.count(), 1)
        onsite = PDAORegistration.objects.exclude(pk=item.pk).get()
        self.assertEqual(onsite.data['intake_channel'], 'walk_in')
        self.assertEqual(onsite.status, 'received')
        self.assertTrue(onsite.events.filter(action='onsite_submitted', actor=staff).exists())
        print(f'PDAO record browser evidence: {output}\n{result.stdout}', flush=True)
