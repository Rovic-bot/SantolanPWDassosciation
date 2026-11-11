"""Synthetic end-to-end member correction, invitation and reapproval."""
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from members.test_public_updates import UpdateHelpers
from members.update_models import MemberUpdateRequest, MemberUpdateEmail
from programs.models import ProgramApplication
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class MemberUpdatesBrowserTests(UpdateHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_member_submission_admin_interview_block_and_reapproval(self):
        require_disposable()
        self.setup_update()
        program = create_program(ewaf_applicable=True)
        admin = Client()
        admin.force_login(self.actor)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'member-updates-browser'
        output.mkdir()
        with patch('members.update_services.secrets.randbelow', return_value=123456):
            result = subprocess.run(['node', 'scripts/member_updates_browser_qa.cjs'], env={**os.environ,
                'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                'QA_ADMIN_SESSION': admin.cookies['sessionid'].value,
                'QA_IDENTITY': json.dumps(self.identity(), default=str),
                'QA_PROGRAM_IDENTITY': json.dumps(self.identity() | {'birthdate': self.member.birthdate,
                    'contact_number': self.member.contact_number}, default=str),
                'QA_PROGRAM_VERIFY': reverse('programs:verify', args=[program.pk]),
                'QA_DIRECTORY': reverse('member_directory')},
                capture_output=True, text=True, encoding='utf-8', timeout=180,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.member.refresh_from_db(); self.application.refresh_from_db()
        self.assertEqual(self.member.registration_profile['guardian_name'], 'Updated synthetic guardian')
        self.assertEqual(self.member.email, 'updated@example.invalid')
        self.assertEqual(self.member.control_number, '00-0000-000-0000001')
        self.assertEqual(self.application.registration_profile, self.source)
        self.assertEqual(MemberUpdateRequest.objects.get().state, 'approved')
        self.assertEqual(MemberUpdateEmail.objects.filter(request__isnull=False, state='sent').count(), 1)
        self.assertEqual(ProgramApplication.objects.count(), 0)
        print(result.stdout, flush=True)
