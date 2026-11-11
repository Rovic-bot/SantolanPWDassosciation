"""Directory filtering and actual bulk/single claim actions, fictional email only."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from members.models import DisabilityType, Member
from members.tests import create_member
from membership.pdao_email_models import PDAOReviewEmail as Email
from membership.test_pdao_claim_email import ClaimHelpers
from membership.tests import grant


@override_settings(PDAO_REGISTRATION_ENABLED=True, PDAO_CLAIM_EMAIL_BACKGROUND=True,
                   SHORT_REFERENCES_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOClaimBrowserTests(ClaimHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_directory_filters_bulk_notices_and_after_forwarding_action(self):
        self.setup_claims()
        grant(self.staff, 'members.view_member')
        one = self.record('BulkOnline')
        two = self.record('BulkOnsite', channel='walk_in')
        untouched = self.record('NotSelected')
        missing = self.record('MissingEmail', email='', channel='walk_in')
        single = self.record('Single', status='ready')
        for index in range(21):
            member = create_member(f'FILTER-VISUAL-{index:02d}')
            Member.objects.filter(pk=member.pk).update(full_name=f'Visual Example {index:02d}')
        visual = member.disability_type
        hearing = DisabilityType.objects.create(name='Synthetic Hearing')
        only = create_member('FILTER-HEARING')
        only.disability_types.set([hearing])
        Member.objects.filter(pk=only.pk).update(full_name='Hearing Example')
        shared = create_member('FILTER-SHARED')
        shared.disability_types.set([visual, hearing])
        Member.objects.filter(pk=shared.pk).update(full_name='Shared Example')
        self.client.force_login(self.staff)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'directory-pdao-claims'
        output.mkdir()
        payload = {'online': str(one.pk), 'onsite': str(two.pk), 'untouched': str(untouched.pk),
            'missing': str(missing.pk), 'single': reverse('membership:pdao_detail', args=[single.pk]),
            'visual': str(visual.pk), 'hearing': str(hearing.pk)}
        result = subprocess.run(['node', 'scripts/pdao_claim_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_SESSION': self.client.cookies['sessionid'].value,
            'QA_DATA': json.dumps(payload), 'QA_OUTPUT': str(output)}, capture_output=True, text=True,
            encoding='utf-8', timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(set(Email.objects.values_list('registration_id', flat=True)), {one.pk, two.pk, single.pk})
        self.assertEqual(set(Email.objects.values_list('state', flat=True)), {'sent'})
        self.assertFalse(untouched.review_emails.exists())
        self.assertFalse(missing.review_emails.exists())
        self.assertEqual({message.to[0] for message in mail.outbox}, {one.data['email'], two.data['email'], single.data['email']})
        (output / 'emails.json').write_text(json.dumps([{'to': message.to, 'subject': message.subject, 'body': message.body}
            for message in mail.outbox], indent=2), encoding='utf-8')
        print(f'PDAO claim/browser evidence: {output}\n{result.stdout}', flush=True)
