"""Application retry across a real login/token rotation, in disposable MySQL."""
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from announcements.tests import image_upload
from members import test_registration_edit as member_tests
from members.models import DisabilityType
from members.tests import create_member
from programs.models import ProgramApplication, ProgramRequirement, PhotoVerification
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   CSRF_COOKIE_NAME='synthetic_program_csrf', PROGRAM_TRACKING_ENABLED=True)
class ProgramApplicationBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_retry_submission_review_and_registration_record(self):
        require_disposable()
        from assistance.tests import seed_statuses
        seed_statuses()
        member_tests.MemberRegistrationEditTests.setUp(self)
        password = secrets.token_urlsafe(32)
        self.actor.set_password(password)
        self.actor.save(update_fields=['password'])
        self.application.decided_at = timezone.now()
        self.application.decided_by = self.actor
        self.application.save(update_fields=['decided_at', 'decided_by'])
        rejected = create_member('SYNTHETIC-UNMATCHED')
        rejected.application.decided_by = self.actor
        rejected.application.save(update_fields=['decided_by'])
        unrelated = DisabilityType.objects.create(name='Synthetic excluded classification')
        rejected.disability_type = unrelated
        rejected.save(update_fields=['disability_type'])
        rejected.disability_types.set([unrelated])
        program = create_program(policy_authorized_by=self.actor,
            eligible_disability_types=list(self.member.disability_types.all()))
        photo = ProgramRequirement.objects.create(program=program, label='Configured calendar photo', kind='document',
            instructions='Synthetic requirement: upload the requested calendar photograph.', is_required=True)
        statement = ProgramRequirement.objects.create(program=program, label='Applicant statement', kind='text')
        ranking_program = create_program(ewaf_applicable=True, name='Synthetic registration inputs')
        ProgramApplication.objects.create(program=ranking_program, member=self.member,
            public_reference='SYNTHETIC-RANKING-REGISTRATION', status='ELIGIBLE')
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-application-browser'
        output.mkdir()
        upload = output / 'synthetic-photo.png'
        upload.write_bytes(image_upload().read())
        result = subprocess.run(['node', 'scripts/program_application_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
            'QA_USERNAME': self.actor.username, 'QA_PASSWORD': password,
            'QA_LOGIN': reverse('accounts:login'), 'QA_VERIFY': reverse('programs:verify', args=[program.pk]),
            'QA_APPLY': reverse('programs:apply', args=[program.pk]),
            'QA_TRACK': reverse('programs:tracking'),
            'QA_PROGRAM': reverse('programs:detail', args=[program.pk]),
            'QA_ANNOUNCEMENTS': reverse('announcements:manage_list'),
            'QA_NOTICES': reverse('announcements:manage_notices'),
            'QA_CREATE_ANNOUNCEMENT': reverse('announcements:create'),
            'QA_APPS': reverse('programs:applications', args=[program.pk]),
            'QA_RANKING': reverse('ewaf:operational_workspace', args=[ranking_program.pk]),
            'QA_MEMBER': reverse('members:detail', args=[self.member.pk]),
            'QA_CONTROL': self.member.control_number, 'QA_NAME': self.member.full_name,
            'QA_CONTACT': self.member.contact_number,
            'QA_BAD_CONTROL': rejected.control_number, 'QA_BAD_NAME': rejected.full_name,
            'QA_FILE': str(upload), 'QA_DOCUMENT_FIELD': f'requirement_{photo.pk}',
            'QA_STATEMENT_FIELD': f'requirement_{statement.pk}'},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        application = ProgramApplication.objects.get(program=program)
        self.assertEqual(application.member_id, self.member.pk)
        self.assertEqual(application.status, 'ELIGIBLE')
        self.assertEqual(application.documents.count(), 1)
        self.assertEqual(application.source_snapshot['application_confirmation']['applicant_contact'], self.member.contact_number)
        self.assertEqual(application.source_snapshot['application_confirmation']['contact_source'], 'member_record')
        self.assertIsNone(application.current_photo_id)
        self.assertFalse(PhotoVerification.objects.exists())
        self.assertFalse(application.assistance_releases.exists())
        print(result.stdout, flush=True)
