"""Assistance workflow in Chrome, using synthetic records in disposable MySQL."""
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from assistance.models import AssistanceCase, AssistanceRelease
from assistance.services import previous_assistance_count
from assistance.tests import create_application, seed_statuses
from membership.tests import pdf
from programs.models import ProgramRequirement, ProgramDocument


class AssistanceBrowserTests(StaticLiveServerTestCase):
    def test_review_decision_release_void_and_replacement(self):
        root = Path(__file__).resolve().parents[1]
        seed_statuses()
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('assistance_browser', password=password)
        application = create_application()
        requirement = ProgramRequirement.objects.create(program=application.program, label='Supporting proof', kind='document')
        application.requirements_snapshot = [{'id': requirement.pk, 'label': requirement.label, 'kind': 'document', 'is_required': True}]
        application.program_snapshot = {'requirements': 'Review the submitted proof and confirm receipt in person.'}
        application.save()
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            document = ProgramDocument(application=application, requirement=requirement, label=requirement.label, content_type='application/pdf', size=100)
            document.file.save('proof.pdf', pdf(), save=True)
            env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': 'assistance_browser', 'QA_PASSWORD': password,
                   'QA_APPLICATION': str(application.pk), 'QA_MEMBER_ID': str(application.member_id),
                   'QA_PROGRAM_ID': str(application.program_id), 'QA_REQUIREMENT_ID': str(requirement.pk)}
            result = subprocess.run(['node', str(root/'scripts/milestone70_browser_qa.cjs')], cwd=root, env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=300)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
            self.assertEqual(AssistanceCase.objects.get().decision, 'approved')
            self.assertEqual(AssistanceRelease.objects.count(), 2)
            self.assertEqual(AssistanceRelease.objects.successful().count(), 1)
            self.assertEqual(previous_assistance_count(application.member), 1)
