"""Optional Chrome integration, using only the disposable Django test database."""
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from documents.models import DocumentType, MembershipDocumentRequirement
from members.models import DisabilityType, Member
from membership.models import MembershipApplication, MembershipSettings


class MembershipBrowserTests(StaticLiveServerTestCase):
    def test_membership_workflow_in_chrome(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        officer = get_user_model().objects.create_user('membership_browser_officer', password=password, is_staff=True)
        for capability in ('accounts.access_dashboard', 'membership.view_membershipapplication',
                'membership.encode_membershipapplication', 'membership.verify_membershipapplication',
                'membership.decide_membershipapplication', 'membership.view_membershipevent',
                'documents.view_membershipapplicationdocument', 'members.view_member'):
            app, codename = capability.split('.')
            officer.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
        MembershipSettings.objects.update_or_create(pk=1, defaults={
            'registration_open': False, 'prpwd_url': 'https://registry.example.test/verify'})
        disability = DisabilityType.objects.create(name='Synthetic browser classification')
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(
            name='Test supporting document'), instructions='Bring the original for onsite review.')
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(
            name='Optional browser evidence'), is_required=False)
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(
            name='Retired browser evidence'), is_active=False)
        env = {**os.environ, 'QA_URL': self.live_server_url,
               'QA_USERNAME': officer.username, 'QA_PASSWORD': password,
               'QA_DISABILITY': str(disability.pk)}
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            result = subprocess.run(['node', str(root / 'scripts/membership_browser_qa.cjs')],
                cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
            self.assertEqual(Member.objects.count(), 1)
            self.assertEqual(MembershipApplication.objects.filter(status='approved').count(), 1)
            self.assertEqual(MembershipApplication.objects.filter(status='rejected').count(), 1)
            approved = MembershipApplication.objects.get(status='approved')
            rejected = MembershipApplication.objects.get(status='rejected')
            self.assertEqual(approved.prpwd_verified_by, officer)
            self.assertEqual(approved.decided_by, officer)
            self.assertEqual(rejected.decided_by, officer)
            self.assertFalse(Member.objects.filter(application=rejected).exists())
            self.assertEqual(approved.documents.count(), 1)
            self.assertEqual(approved.requirements_snapshot[0]['label'], 'Test supporting document')
            self.assertEqual(set(approved.events.values_list('action', flat=True)),
                {'onsite_encoded', 'document_downloaded', 'prpwd_verified', 'approved'})
            self.assertEqual(get_user_model().objects.count(), 1)
            self.assertFalse(officer.is_superuser)
