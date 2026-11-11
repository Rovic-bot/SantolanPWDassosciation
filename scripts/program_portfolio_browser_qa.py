"""Program portfolio browser checks with disposable synthetic data only."""
from datetime import timedelta
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from members.tests import create_member
from programs.models import Program, ProgramApplication
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class ProgramPortfolioBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_portfolio_interactions_and_layout(self):
        require_disposable()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'program-portfolio-browser'
        output.mkdir()
        actor = get_user_model().objects.create_superuser('synthetic_portfolio_browser', password=None)
        now = timezone.now()
        members = [create_member(f'SYNTH-PORTFOLIO-{index}') for index in range(6)]
        specs = [
            ('Medical Access Week', 'Healthcare', 'published', 5, 4),
            ('Assistive Device Distribution', 'Assistive Devices', 'published', 4, 3),
            ('Inclusive Livelihood Lab', 'Livelihood', 'published', 3, 2),
            ('Nutrition Support Batch 4', 'Food & Nutrition', 'draft', 8, 0),
            ('PWD Sports Festival', 'Community', 'published', 15, 5),
            ('Financial Assistance Q4', 'Financial', 'published', 5, 6),
            ('Digital Skills Workshop', 'Education', 'published', None, 2),
            ('Family Caregiver Forum', 'Community', 'draft', 6, 0),
        ]
        programs = []
        for index, (name, category, status, slots, applications) in enumerate(specs):
            program = create_program(name=name, public_code=f'SP-{index + 1:06d}', assistance_type=category, slots=slots,
                registration_opens_at=now - timedelta(days=3),
                registration_closes_at=now + timedelta(days=7 + index) if index != 5 else now - timedelta(days=1),
                starts_at=now + timedelta(days=10 + index), ends_at=now + timedelta(days=11 + index))
            Program.objects.filter(pk=program.pk).update(status=status,
                published_at=now - timedelta(days=3) if status == 'published' else None,
                created_at=now - timedelta(hours=index))
            programs.append(program)
            for member_index in range(applications):
                ProgramApplication.objects.create(program=program, member=members[member_index],
                    public_reference=f'SYNTH-PORTFOLIO-APP-{index}-{member_index}')
        client = Client()
        client.force_login(actor)
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
               'QA_ADMIN_SESSION': client.cookies['sessionid'].value,
               'QA_PORTFOLIO_ROUTE': reverse('program_portfolio'),
               'QA_FIRST_CODE': programs[0].public_code}
        result = subprocess.run(['node', 'scripts/program_portfolio_browser_qa.cjs'], env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Program.objects.count(), 8)
        self.assertEqual(ProgramApplication.objects.count(), 22)
        print(result.stdout, flush=True)
