"""Real browser coverage of the requested Admin workflow, on disposable MySQL."""
import os
from pathlib import Path
import subprocess
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.utils import timezone
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_services import record_configuration, configuration_token
from ewaf.four_criterion_development import ahp
from programs.tests import create_program
from programs.testsupport import application_fixture
from members.tests import create_member
from membership.tests import pdf
from programs.models import ProgramRequirement, ProgramDocument


@override_settings(EWAF_FICTIONAL_DEMO=True)
class AdminWorkflowBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_admin_program_to_receipt_publication_and_reports(self):
        from programs.test_ui_cleanup import seed_catalog
        seed_catalog()
        self.setup_operational(additional=1)
        # Create all unrelated fixtures before capture: no source is mutated to
        # make a blocked calculation or selection appear current.
        review_program = create_program(name='Fictional browser identity review',
            registration_closes_at=timezone.now() - timezone.timedelta(hours=1))
        review_application = application_fixture(review_program, create_member('BROWSER-REVIEW'))
        negative_application = application_fixture(review_program, create_member('BROWSER-NEGATIVE'))
        pending_application = application_fixture(review_program, create_member('BROWSER-PENDING'))
        requirement = ProgramRequirement.objects.create(program=review_program,
            label='Fictional supporting document', kind='document', is_required=True)
        review_application.requirements_snapshot = [{
            'id': requirement.pk, 'label': requirement.label, 'kind': 'document',
            'instructions': 'Review the fictional submitted evidence.', 'is_required': True}]
        review_application.save(update_fields=['requirements_snapshot'])
        upload = pdf()
        ProgramDocument.objects.create(application=review_application, requirement=requirement,
            label=requirement.label, file=upload, content_type='application/pdf', size=upload.size)
        record_configuration(self.program.pk, user=self.officer, expected=configuration_token(self.program),
            proposed=self.proposal, judgments=ahp()['pairs'], status='DRAFT',
            reason='Fictional browser configuration. Not Association policy.')
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        output = root / '.local/ui-qa/admin-implementation'
        output.mkdir(parents=True, exist_ok=True)
        process = subprocess.run(['node', str(root / 'scripts/admin_workflow_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                 'QA_APPLICATION': str(self.application.pk), 'QA_MEMBER_NAME': self.member.full_name,
                 'QA_REVIEW_PROGRAM': str(review_program.pk), 'QA_REVIEW_APPLICATION': str(review_application.pk),
                 'QA_NEGATIVE_APPLICATION': str(negative_application.pk), 'QA_PENDING_APPLICATION': str(pending_application.pk),
                 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': str(output)},
            capture_output=True, text=True, encoding='utf-8', timeout=600)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        print(process.stdout)
        from assistance.models import AssistanceRelease
        from announcements.models import Announcement
        from ewaf.operational_models import OperationalRun, OperationalDecision
        self.assertEqual(OperationalRun.objects.filter(program=self.program).count(), 1)
        self.assertEqual(OperationalDecision.objects.filter(program=self.program, outcome='SELECTED').count(), 1)
        self.assertTrue(AssistanceRelease.objects.successful().filter(application=self.application).exists())
        self.assertTrue(Announcement.objects.published().filter(program=self.program).exists())
        from assistance.models import AssistanceCase
        self.assertEqual(AssistanceCase.objects.get(application=negative_application).eligibility_id, 'ineligible')
        self.assertEqual(AssistanceCase.objects.get(application=pending_application).eligibility_id, 'review')
