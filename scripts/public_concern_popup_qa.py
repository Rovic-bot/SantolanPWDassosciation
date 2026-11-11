"""Exercise popup submissions only with synthetic members and captured mail."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from assistance.referral_models import ReferralAttachment, ReferralTicket
from assistance.test_referrals import Fixtures
from membership.tests import pdf


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConcernPopupBrowserTests(Fixtures, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_verified_request_upload_receipt_and_finish_stay_in_popup(self):
        root = Path(__file__).resolve().parents[1]
        evidence = Path(self.media.name) / 'synthetic-evidence.pdf'
        evidence.write_bytes(pdf().read())
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_CONTROL': self.member.control_number, 'QA_NAME': self.member.full_name,
               'QA_EVIDENCE': str(evidence)}
        result = subprocess.run(['node', str(root / 'scripts/public_concern_popup_qa.cjs')],
                                cwd=root, env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(ReferralTicket.objects.count(), 1)
        self.assertEqual(ReferralAttachment.objects.count(), 1)
        self.assertEqual(ReferralTicket.objects.get().member_id, self.member.pk)
        self.assertEqual(ReferralTicket.objects.get().subject, 'Synthetic popup request')
        print(result.stdout)
