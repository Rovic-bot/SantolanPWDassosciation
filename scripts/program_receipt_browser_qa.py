"""Check the receipt UI with fictional data in disposable MySQL only."""
import os
from pathlib import Path
import subprocess
from PIL import Image

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from members.models import Member
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_TRACKING_ENABLED=True, PROGRAM_TRACKING_QR_ENABLED=True,
                   PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ProgramReceiptBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_receipt_copy_tracking_print_and_responsive_layout(self):
        require_disposable()
        member = create_member('SYNTHETIC-RECEIPT-UI')
        program = create_program(name='Synthetic community assistance program')
        application = ProgramApplication.objects.create(
            program=program, member=member,
            public_reference='SPWDA-2026-PRG000013-0000000001',
            answers={'1': 'PRIVATE-SUBMITTED-ANSWER'},
            source_snapshot={'assessment': 'PRIVATE-ASSESSMENT'})
        before = ProgramApplication.objects.values().get(pk=application.pk)
        member_before = Member.objects.values().get(pk=member.pk)
        session = self.client.session
        session['program_receipt'] = str(application.pk)
        session.save()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-receipt-browser'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/program_receipt_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_SESSION': session.session_key,
                 'QA_ROUTE': reverse('programs:submitted', args=[program.pk]),
                 'QA_REFERENCE': application.public_reference,
                 'QA_MEMBER': member.full_name, 'QA_CONTROL': member.control_number},
            capture_output=True, text=True, encoding='utf-8', timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), before)
        self.assertEqual(Member.objects.values().get(pk=member.pk), member_before)
        for extension, kind in [('png', 'PNG'), ('jpeg', 'JPEG')]:
            with Image.open(output / f'receipt.{extension}') as saved:
                self.assertEqual(saved.format, kind)
                self.assertEqual(saved.width, 2400)
                self.assertGreater(saved.height, 1200)
                saved.verify()
        print(result.stdout, flush=True)

    def test_submitted_application_opens_receipt_without_navigation_or_resubmission(self):
        require_disposable()
        member = create_member('SYNTHETIC-POPUP-SUBMISSION')
        member.email = 'registered@example.invalid'
        member.save(update_fields=['email'])
        actor = get_user_model().objects.create_user('synthetic-receipt-reviewer')
        member.application.decided_by = actor
        member.application.save(update_fields=['decided_by'])
        program = create_program(policy_authorized_by=actor,
            name='Synthetic assistance program with a longer title to verify exported text wrapping')
        member_before = Member.objects.values().get(pk=member.pk)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-receipt-submission'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/program_receipt_submission_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_VERIFY': reverse('programs:verify', args=[program.pk]),
                 'QA_APPLY': reverse('programs:apply', args=[program.pk]),
                 'QA_RECEIPT': reverse('programs:submitted', args=[program.pk]),
                 'QA_MEMBER': member.full_name, 'QA_CONTROL': member.control_number},
            capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(ProgramApplication.objects.filter(program=program, member=member).count(), 1)
        self.assertEqual(Member.objects.values().get(pk=member.pk), member_before)
        with Image.open(output / 'changed-information.png') as saved:
            self.assertEqual(saved.format, 'PNG')
            self.assertEqual(saved.width, 2400)
            self.assertGreater(saved.height, 1600)
            saved.verify()
        print(result.stdout, flush=True)
