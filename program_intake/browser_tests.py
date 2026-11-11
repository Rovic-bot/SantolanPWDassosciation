"""Real public-to-Admin browser interaction on disposable native MySQL."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from core.demo_seed import upload, TEST
from members.tests import create_member
from membership.services import record_event
from programs.models import ProgramApplication
from ewaf.operational_models import OperationalConfiguration, OperationalRun
from ewaf.models import CriterionAssessment
from . import tests as intake_tests

templates = deepcopy(settings.TEMPLATES)
templates[0]['DIRS'].insert(0, Path(__file__).resolve().parents[1] / 'main_testing/templates')


@override_settings(ROOT_URLCONF='main_testing.urls', PROGRAM_INTAKE_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=True,
    EWAF_FICTIONAL_DEMO=True, TEMPLATES=templates, INSTALLED_APPS=[*settings.INSTALLED_APPS, 'main_testing'])
class PublicIntakeBrowserTests(StaticLiveServerTestCase):
    setUp = intake_tests.IntakeTests.setUp
    grant = intake_tests.IntakeTests.grant
    submit = intake_tests.IntakeTests.submit
    prepare = intake_tests.IntakeTests.prepare
    si = intake_tests.IntakeTests.si
    collect = intake_tests.IntakeTests.collect

    def run_browser(self, phase, **changes):
        client = Client()
        client.force_login(self.actor)
        root = Path(__file__).resolve().parents[1]
        output = Path(self.media.name) / 'browser'
        output.mkdir(exist_ok=True)
        for name, content in [('portrait.png', upload(portrait=True)), ('source.pdf', upload('Fictional verified observation: 90 assessment units'))]:
            (output / name).write_bytes(content.read())
        data = {'url': self.live_server_url, 'phase': phase, 'program': str(self.program.pk),
            'requirement': self.program.configured_requirements.get(is_required=True).pk,
            'member': {'control_number': self.member.control_number, 'disability_types': self.member.disability_ids,
                'cause': self.member.disability_cause, 'visibility': self.member.disability_visibility, 'name': self.member.full_name,
                'full_name': self.member.full_name},
            'photo': str(output / 'portrait.png'), 'document': str(output / 'source.pdf'), 'output': str(output),
            'cookie': {'name': settings.SESSION_COOKIE_NAME, 'value': client.cookies[settings.SESSION_COOKIE_NAME].value}, **changes}
        fixture = output / 'input.json'
        fixture.write_text(json.dumps(data), encoding='utf-8')
        process = subprocess.run(['node', str(root / 'scripts/intake_browser.cjs'), str(fixture)], cwd=root,
            capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        print(process.stdout.encode('ascii', 'backslashreplace').decode('ascii'), flush=True)

    def test_public_member_match_upload_admin_evidence_and_weight_recalculation(self):
        self.run_browser('intake')
        application = ProgramApplication.objects.get()
        self.assertEqual(application.status, 'ELIGIBLE')
        self.assertEqual(CriterionAssessment.objects.filter(application=application, state='VERIFIED').count(), 4)
        member = create_member('INTAKE-0002')
        member.full_name = 'Fictional Employment Comparison'
        member.disability_cause = 'acquired'
        member.disability_visibility = 'apparent'
        member.employment_status = 'retired'
        member.dependents = 1
        member.save()
        member.disability_types.set([member.disability_type_id])
        intake = member.application
        intake.prpwd_verified_by = intake.decided_by = self.actor
        intake.save()
        record_event(intake, 'prpwd_verified', TEST, user=self.actor)
        record_event(intake, 'approved', TEST, user=self.actor)
        self.prepare(app=self.submit(member=member), value='45')
        with patch('django.utils.timezone.now', return_value=self.program.registration_closes_at + timedelta(seconds=1)):
            self.run_browser('ranking', rankingProgram=str(self.program.pk))
        self.assertEqual(OperationalRun.objects.count(), 2)
        self.assertEqual(OperationalConfiguration.objects.count(), 3)
        for run in OperationalRun.objects.all():
            run.clean()
