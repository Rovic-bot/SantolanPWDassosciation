"""Exercise the actual optional membership form with synthetic PDAO data."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from members.models import Member
from membership.models import MembershipSettings
from membership.pdao_models import PDAOIDClaim
from membership.registration_models import RegistrationIntake
from membership.test_pdf_registration import pdf_policy
from membership.test_pdao_membership import TransferHelpers


@override_settings(PDAO_REGISTRATION_ENABLED=True, ASSOCIATION_REGISTRATION_POLICY=pdf_policy(upload_slots=[]),
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOTransferBrowserTests(TransferHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_claim_prefill_review_and_save_at_desktop_and_mobile_widths(self):
        self.setup_transfer()
        record = self.record()
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'pdao-membership-browser'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/pdao_membership_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_SESSION': self.client.cookies['sessionid'].value,
            'QA_RECORD': reverse('membership:pdao_detail', args=[record.pk]), 'QA_OUTPUT': str(output)},
            capture_output=True, text=True, encoding='utf-8', timeout=150,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        intake = RegistrationIntake.objects.get()
        self.assertEqual(PDAOIDClaim.objects.get().membership_intake_id, intake.pk)
        self.assertEqual(intake.revisions.get(number=1).data['four_ps_member'], 'No')
        self.assertFalse(Member.objects.exists())
        print(json.dumps({'browser': 'passed', 'evidence': str(output)}), flush=True)
