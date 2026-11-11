"""Program operations visual and interaction checks in disposable MySQL only."""
from datetime import timedelta
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from members.models import DisabilityType
from members.tests import create_member
from programs.models import Program, ProgramApplication, ProgramRequirement, ProgramLog
from programs.services import save_program
from programs.tests import program_data
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   EWAF_VAULT_ENABLED=True)
class ProgramDetailBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_profile_layout_and_protected_actions(self):
        require_disposable()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-detail-browser'
        output.mkdir()
        actor = get_user_model().objects.create_superuser('synthetic_profile_browser', password=None)
        now = timezone.now().replace(second=0, microsecond=0)
        program = save_program(user=actor, data=program_data(name='Medical Access Week',
            assistance_type='Healthcare & Medical Aid', slots=2, starts_at=now + timedelta(days=9),
            ends_at=now + timedelta(days=13), registration_opens_at=now - timedelta(days=1),
            registration_closes_at=now + timedelta(days=7),
            description='A focused week of consultations, medicine access, health screening and referral support for association members. Synthetic demonstration record.',
            benefit='Connect members with accessible local medical support.',
            selection_method='Authorized staff review verified requirements and record each beneficiary decision within the available slots.',
            photo_instructions='Present the approved identity evidence for staff verification. Contact the membership desk for assistance.'))
        program.eligible_disability_types.set([DisabilityType.objects.get_or_create(name=name)[0]
            for name in ('Physical / Orthopedic', 'Visual Disability', 'Hearing', 'Psychosocial', 'Intellectual', 'Rare Disease')])
        for index, (label, kind, required) in enumerate((('Supporting medical document', 'document', True),
                ('Preferred assistance', 'text', False), ('Review of applicant information', 'acknowledgement', True))):
            ProgramRequirement.objects.create(program=program, label=label, kind=kind, is_required=required,
                position=index, instructions='Synthetic requirement for this demonstration program.')
        for index in range(3):
            ProgramApplication.objects.create(program=program, member=create_member(f'PROFILE-BROWSER-{index}'),
                public_reference=f'SYNTHETIC-PROFILE-{index}')
        for index in range(22):
            ProgramLog.objects.create(program=program, action='updated', actor=actor,
                actor_label=actor.username, notes=f'Synthetic historical update {index + 1}.')
        blocked = save_program(user=actor, data=program_data(name='Assistive Device Distribution',
            benefit='Synthetic device assistance.', ewaf_applicable=True))
        client = Client()
        client.force_login(actor)
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
               'QA_ADMIN_SESSION': client.cookies['sessionid'].value,
               'QA_PROFILE_ROUTE': reverse('program_detail') + f'?program={program.pk}',
               'QA_PROFILE_LEGACY': reverse('programs:manage_detail', args=[program.pk]),
               'QA_BLOCKED_ROUTE': reverse('programs:manage_detail', args=[blocked.pk]),
               'QA_REVIEW_ROUTE': reverse('programs:applications', args=[program.pk])}
        env.update(QA_PORTFOLIO_ROUTE=reverse('program_portfolio'),
                   QA_APPLICATION_ROUTE=reverse('application_workspace'))
        result = subprocess.run(['node', 'scripts/program_detail_browser_qa.cjs'], env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')
        self.assertTrue(program.history.filter(action='published').exists())
        self.assertTrue(program.history.filter(action='draft').exists())
        self.assertEqual(Program.objects.get(pk=blocked.pk).status, 'draft')
        self.assertEqual(ProgramApplication.objects.count(), 3)
        print(result.stdout, flush=True)
