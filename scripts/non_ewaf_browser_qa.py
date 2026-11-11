"""Eligibility-only flow in a browser, against synthetic disposable MySQL only."""
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from assistance.models import AssistanceRelease
from assistance.tests import seed_statuses
from announcements.certificate_models import SelectionCertificateEmail
from announcements.models import Announcement
from programs.services import save_program
from programs.tests import create_program, program_data
from programs.testsupport import private_media, application_fixture
from members.tests import create_member
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   CERTIFICATE_EMAIL_BACKGROUND=False, CERTIFICATE_RESEND_ENABLED=False)
class NonEWAFBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_capacity_toggle_eligibility_and_publication(self):
        require_disposable()
        private_media(self)
        seed_statuses()
        from programs.test_ui_cleanup import seed_catalog
        seed_catalog()
        actor = get_user_model().objects.create_superuser('SYNTHETIC-NON-EWAF-BROWSER')
        draft = save_program(user=actor, setup_only=True,
            data=program_data(name='Synthetic capacity draft', ewaf_applicable=True, slots='', eligible_disability_types=[]))
        program = create_program(name='Synthetic unlimited program', ewaf_applicable=False,
            slots=1, policy_authorized_by=actor, eligible_disability_types=[])
        application = application_fixture(program, create_member('SYNTHETIC-BROWSER-ELIGIBLE'))
        intake = application.member.application
        intake.decided_by = actor
        intake.save(update_fields=['decided_by'])
        client = Client()
        client.force_login(actor)
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'non-ewaf-browser'
        directory.mkdir()
        with patch('announcements.certificate_delivery.send_certificate') as send, patch(
                'announcements.certificate_delivery.certificate_pdfs') as pdf:
            result = subprocess.run(['node', 'scripts/non_ewaf_browser_qa.cjs'], env={**os.environ,
                'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
                'QA_SESSION': client.cookies['sessionid'].value,
                'QA_DRAFT': reverse('programs:edit', args=[draft.pk]),
                'QA_PROFILE': reverse('programs:manage_detail', args=[program.pk]),
                'QA_APPLICATION': reverse('programs:application_detail', args=[program.pk, application.pk]),
                'QA_RESULTS': reverse('announcements:prepare_results', args=[program.pk])},
                capture_output=True, text=True, encoding='utf-8', timeout=180,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        draft.refresh_from_db()
        application.refresh_from_db()
        self.assertFalse(draft.ewaf_applicable)
        self.assertIsNone(draft.slots)
        self.assertEqual(application.status, 'SELECTED')
        item = Announcement.objects.get(program=program)
        self.assertEqual(item.status, 'published')
        self.assertEqual(len(item.result_revision.public_payload['rows']), 1)
        self.assertFalse(SelectionCertificateEmail.objects.exists())
        self.assertFalse(AssistanceRelease.objects.exists())
        send.assert_not_called()
        pdf.assert_not_called()
        print(result.stdout, flush=True)
