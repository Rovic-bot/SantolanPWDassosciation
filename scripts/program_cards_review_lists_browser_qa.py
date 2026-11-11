"""Synthetic program cards and review-list browser checks, disposable database only."""
import os
from datetime import timedelta
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from membership import pdao_services, registration_services
from membership.pdao_models import PDAORegistrationEvent
from membership.registration_models import RegistrationAction
from membership.test_pdao_registration import PDAOHelpers, actor
from membership.test_pdf_registration import association_data, pdf_policy
from programs.models import ProgramPicture
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_REGISTRATION_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   PROGRAM_APPLICATION_WORKFLOW_ENABLED=False,
                   ASSOCIATION_REGISTRATION_POLICY=pdf_policy(upload_slots=[]))
class ProgramCardsReviewListsBrowserTests(PDAOHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_responsive_cards_and_shared_review_lists(self):
        require_disposable()
        self.submit()
        user = actor(pdao_services.VIEW, pdao_services.ADD, 'membership.view_registrationintake',
                     'membership.view_membershipapplication', 'membership.encode_registrationintake')
        binding = registration_services.binding_for('synthetic-shared-review-list')
        token = registration_services.issue_context(binding)
        registration_services.submit_registration(token.pk, binding, association_data())
        before = (RegistrationAction.objects.count(), PDAORegistrationEvent.objects.count())
        featured = create_program(name='Community mobility support',
            description='Explore support for everyday mobility and independent living. Review the program requirements and application period before applying.')
        create_program(name='Family food assistance', description='Food support for eligible Association members and their households.')
        create_program(name='Community learning and skills development for members and their families',
            description='Browse the published requirements for this upcoming program.',
            registration_opens_at=timezone.now() + timedelta(hours=6))
        image = Path('static/images/home-pavilion-illustration.png').read_bytes()
        ProgramPicture.objects.create(program=featured, image=SimpleUploadedFile('synthetic-program.png', image, content_type='image/png'))
        self.client.force_login(user)
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-cards-review-lists'
        output.mkdir()
        env = {**os.environ, 'QA_URL': self.live_server_url,
            'QA_ADMIN_SESSION': self.client.cookies['sessionid'].value,
            'QA_ASSOCIATION_ROUTE': reverse('membership:registration_inbox'),
            'QA_PDAO_ROUTE': reverse('membership:pdao_inbox'),
            'QA_PROGRAM_ROUTE': reverse('programs:list'), 'QA_OUTPUT': str(output)}
        result = subprocess.run(['node', 'scripts/program_cards_review_lists_browser_qa.cjs'], env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, (RegistrationAction.objects.count(), PDAORegistrationEvent.objects.count()))
        print(f'Program cards and review lists evidence: {output}\n{result.stdout}', flush=True)
