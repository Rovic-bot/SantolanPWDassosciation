"""Actual onsite Admin forms with fictional records and disposable MySQL only."""
import json
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse

from documents.models import DocumentType, MembershipDocumentRequirement, DocumentVerification
from members.models import Member, DisabilityType
from membership.models import MembershipSettings
from membership.test_onsite_profile import seed_capture_slots, portrait
from programs.testsupport import private_media


class OnsiteBrowserTests(StaticLiveServerTestCase):
    def test_actual_onsite_create_review_edit_and_mobile_layout(self):
        private_media(self)
        seed_capture_slots()
        officer = get_user_model().objects.create_superuser('fictional_onsite_browser')
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/'})
        from programs.test_ui_cleanup import seed_catalog
        seed_catalog()
        MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Association 2×2 photograph'),
            is_active=True, is_required=True)
        client = Client()
        client.force_login(officer)
        root = Path(__file__).resolve().parents[1]
        output = root / '.local/ui-qa/onsite-registration'
        output.mkdir(parents=True, exist_ok=True)
        photo = output / 'fictional-photo.png'
        photo.write_bytes(portrait().read())
        process = subprocess.run(['node', str(root / 'scripts/onsite_profile_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PATH': reverse('membership:encode'),
                'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                'QA_OUTPUT': str(output), 'QA_PHOTO': str(photo),
                'QA_UPLOADS': json.dumps({str(row.pk): row.capture_key or 'association_photo'
                    for row in MembershipDocumentRequirement.objects.all()})},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        print(process.stdout)
        member = Member.objects.get(control_number='FICTIONAL-ONSITE-BROWSER')
        self.assertEqual(member.full_name, 'Mara Santos VII')
        self.assertEqual(member.dependents, 4)
        self.assertEqual(member.disability_types.count(), 2)
        self.assertEqual(member.employment_status, 'retired')
        self.assertEqual(member.application.employment_status, 'self_employed')
        self.assertEqual(member.application.documents.count(), 6)
        self.assertEqual(DocumentVerification.objects.count(), 1)
        self.assertEqual(member.events.filter(action='profile_updated').count(), 1)
