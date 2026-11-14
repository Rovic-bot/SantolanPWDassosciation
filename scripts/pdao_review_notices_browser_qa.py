"""Real browser workflow on disposable data with an in-memory email backend."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from assistance.referral_models import ReferralSettings, referral_write
from membership import pdao_services as services
from membership.models import MembershipSettings
from membership.pdao_models import PDAORegistration
from membership.pdao_email_models import PDAOReviewEmail
from membership.test_pdao_registration import PDAOHelpers, actor
from membership.test_pdf_registration import pdao_data
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_REGISTRATION_ENABLED=True, SHORT_REFERENCES_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOReviewBrowserTests(PDAOHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_online_notices_onsite_silence_and_public_receipt(self):
        require_disposable()
        data = self.prepare() | {'pwd_number': '00-0000-000-0000001'}
        self.client.post(reverse('membership:pdao_apply'), data)
        online = PDAORegistration.objects.get()
        public_session = self.client.cookies['sessionid'].value
        staff = actor(services.VIEW, services.PRINT, services.CORRECT, services.FORWARD, services.ADD)
        self.client = Client()
        self.client.force_login(staff)
        page = self.client.get(reverse('membership:pdao_onsite'))
        self.client.post(reverse('membership:pdao_onsite'), pdao_data() | {'first_name': 'Onsite',
            'submission_token': page.context['form'].initial['submission_token']})
        onsite = PDAORegistration.objects.exclude(pk=online.pk).get()
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/check'})
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='association@example.invalid')
        mail.outbox = []
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'pdao-review-notices'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/pdao_review_notices_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
            'QA_PUBLIC_SESSION': public_session,
            'QA_ONLINE': reverse('membership:pdao_detail', args=[online.pk]),
            'QA_ONSITE': reverse('membership:pdao_detail', args=[onsite.pk]), 'QA_OUTPUT': str(output)},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        online.refresh_from_db(); onsite.refresh_from_db()
        self.assertEqual((online.status, onsite.status), ('forwarded', 'forwarded'))
        self.assertEqual(online.data['first_name'], 'Fictional')
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(online.review_emails.count(), 2)
        self.assertEqual(onsite.review_emails.count(), 0)
        self.assertEqual(set(PDAOReviewEmail.objects.values_list('state', flat=True)), {'sent'})
        (output/'emails.json').write_text(json.dumps([{'to': message.to, 'subject': message.subject, 'body': message.body}
            for message in mail.outbox], indent=2), encoding='utf-8')
        print(f'PDAO review evidence: {output}\n{result.stdout}', flush=True)
