"""Private approved-member popup and A4 output, using disposable records only."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from members.models import Member
from membership.registration_models import RegistrationAction
from membership.test_registration_decisions import DecisionHelpers
from scripts.durable_test_runner import require_disposable


class MemberPrintPreviewBrowserTests(DecisionHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_private_member_preview_and_document_printing(self):
        require_disposable()
        self.setup_decisions()
        intake = self.make()
        self.decide(intake)
        member = Member.objects.select_related('application').get()
        original = deepcopy(member.application.registration_profile)
        self.client.force_login(self.actor)
        folder = Path(os.environ['G12_ARTIFACT_DIR']) / 'member-print-preview-browser'
        folder.mkdir()
        result = subprocess.run(['node', 'scripts/member_print_preview_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(folder),
            'QA_SESSION': self.client.cookies['sessionid'].value,
            'QA_MEMBER_ROUTE': reverse('members:detail', args=[member.pk]),
            'QA_PRINT_ROUTE': reverse('members:registration_print', args=[member.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=150,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        member.application.refresh_from_db()
        self.assertEqual(member.application.registration_profile, original)
        self.assertEqual(Member.objects.count(), 1)
        self.assertTrue(RegistrationAction.objects.filter(intake=intake,
            action='staff_completed_form_viewed', actor=self.actor).exists())
        print(f'Member print browser evidence: {folder}\n{result.stdout}', flush=True)
