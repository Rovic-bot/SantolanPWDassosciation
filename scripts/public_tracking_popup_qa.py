"""Exercise the tracking popup against synthetic records in disposable MySQL."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from members.models import Member
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program


@override_settings(PROGRAM_TRACKING_ENABLED=True,
                   PROGRAM_VERIFICATION_MEMBER_LIMIT=100,
                   PROGRAM_VERIFICATION_ADDRESS_LIMIT=250)
class TrackingPopupBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_tracking_stays_in_popup_and_preserves_private_records(self):
        member = create_member('SYNTHETIC-POPUP-MEMBER')
        program = create_program(name='Synthetic popup program')
        application = ProgramApplication.objects.create(
            program=program, member=member, public_reference='SPA-POPUP-TEST-001',
            answers={'1': 'PRIVATE-APPLICATION-ANSWER'},
            source_snapshot={'assessment': 'PRIVATE-ASSESSMENT-NOTE'})
        before = ProgramApplication.objects.values().get(pk=application.pk)
        member_before = Member.objects.values().get(pk=member.pk)
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_REFERENCE': application.public_reference,
               'QA_PROGRAM_URL': reverse('programs:detail', args=[program.pk]),
               'QA_MEMBER': member.full_name, 'QA_CONTROL': member.control_number}
        result = subprocess.run(['node', str(root / 'scripts/public_tracking_popup_qa.cjs')],
                                cwd=root, env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), before)
        self.assertEqual(Member.objects.values().get(pk=member.pk), member_before)
        print(result.stdout)
