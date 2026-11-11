"""Public submission -> Admin approval -> captured email; disposable records only."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from assistance.referral_models import ReferralSettings, referral_write
from membership.approval_email_models import MembershipApprovalEmail
from membership.registration_models import RegistrationIntake
from membership.test_pdf_registration import association_data
from membership.test_registration_decisions import DecisionHelpers
from membership.tests import grant
from scripts.durable_test_runner import require_disposable


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MembershipApprovalEmailBrowserTests(DecisionHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_online_submission_and_approval_email(self):
        require_disposable()
        self.setup_decisions()
        grant(self.actor, 'membership.encode_membershipapplication')
        self.client.force_login(self.actor)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'membership-approval-email-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/membership_approval_email_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url,
                 'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
                 'QA_PUBLIC_ROUTE': reverse('membership:registration_apply'),
                 'QA_LOOKUP_ROUTE': reverse('membership:registration_lookup'),
                 'QA_FORM_DATA': json.dumps(association_data()), 'QA_OUTPUT': str(directory)},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        intake = RegistrationIntake.objects.get()
        self.assertEqual(intake.channel, 'online')
        self.assertEqual(intake.membership_application.status, 'approved')
        job = MembershipApprovalEmail.objects.get()
        self.assertEqual((job.state, job.attempt_count), ('sent', 1))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, [association_data()['email']])
        self.assertIn('Bring your PWD ID', mail.outbox[0].body)
        self.assertIn('not yet a member', mail.outbox[0].body)
        self.assertIn('You are now a member', mail.outbox[1].body)
        self.assertTrue(intake.actions.filter(action='office_information_verified').exists())
        (directory / 'synthetic-invitation.txt').write_text(mail.outbox[0].body, encoding='utf-8')
        (directory / 'synthetic-email.txt').write_text(mail.outbox[1].body, encoding='utf-8')
        print(f'Membership approval email browser evidence: {directory}\n{result.stdout}', flush=True)
