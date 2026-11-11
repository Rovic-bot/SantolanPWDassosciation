"""Disposable UI checks for onsite lookup and the approved member profile."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from members.models import Member
from membership.pdf_registration_forms import AssociationPDFForm
from membership.test_pdf_registration import association_data
from membership.test_registration_decisions import DecisionHelpers
from membership.tests import grant
from scripts.durable_test_runner import require_disposable


class MemberRegistrationBrowserTests(DecisionHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_onsite_required_email_and_pwd(self):
        require_disposable()
        self.setup_decisions()
        grant(self.actor, 'membership.encode_membershipapplication', 'membership.encode_registrationintake')
        self.client.force_login(self.actor)
        result = subprocess.run(['node', 'scripts/member_registration_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_ONSITE_ONLY': '1',
                 'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
                 'QA_ONSITE': reverse('membership:encode'),
                 'QA_FORM_DATA': json.dumps(association_data() | {
                     'pwd_number': '00-0000-000-0000003', 'email': 'onsite@example.invalid'})},
            capture_output=True, text=True, encoding='utf-8', timeout=60,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)

    def test_lookup_photo_edit_and_onsite_review(self):
        require_disposable()
        self.setup_decisions()
        grant(self.actor, 'membership.encode_membershipapplication', 'membership.encode_registrationintake',
              'membership.view_registration_documents', 'members.change_member')
        intake = self.make(files=MultiValueDict({'photo_2x2': [image_upload()]}))
        self.decide(intake)
        member = Member.objects.get()
        original = member.application.registration_profile
        plain = self.make(data={'last_name': 'Plain', 'pwd_number': '00-0000-000-0000002'})
        self.decide(plain, self.data(plain, last_name='Plain'))
        plain_member = Member.objects.exclude(pk=member.pk).get()
        self.client.force_login(self.actor)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'member-registration-browser'
        output.mkdir()
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
               'QA_ONSITE': reverse('membership:encode'), 'QA_REFERENCE': intake.reference,
               'QA_MEMBER': reverse('members:detail', args=[member.pk]),
               'QA_PLAIN_MEMBER': reverse('members:detail', args=[plain_member.pk]),
               'QA_FIELDS': json.dumps(list(AssociationPDFForm.base_fields)),
               'QA_FORM_DATA': json.dumps(association_data() | {
                   'pwd_number': '00-0000-000-0000003', 'email': 'onsite@example.invalid'}),
               'QA_OUTPUT': str(output)}
        result = subprocess.run(['node', 'scripts/member_registration_browser_qa.cjs'], env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=150,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        member.refresh_from_db()
        member.application.refresh_from_db()
        self.assertEqual(member.registration_profile['guardian_name'], 'Updated fictional guardian')
        self.assertEqual(member.application.registration_profile, original)
        self.assertEqual(Member.objects.count(), 2)
        print(f'Member registration browser evidence: {output}\n{result.stdout}', flush=True)
