"""Chrome checks on a disposable MySQL live server with fictional applicants."""
import json
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from config.registration_workflow import association_policy
from members.models import Member
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from membership.pdao_models import PDAORegistration
from membership.registration_models import RegistrationIntake
from membership.test_pdf_registration import association_data, pdao_data


@override_settings(PDAO_REGISTRATION_ENABLED=True, SHORT_REFERENCES_ENABLED=True,
                   ASSOCIATION_REGISTRATION_POLICY=association_policy(5242880, 20971520))
class OnlineMembershipBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_applicant_admin_decisions_and_pdao_print_forward(self):
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'online-membership-browser'
        directory.mkdir()
        staff = get_user_model().objects.create_superuser('synthetic_browser_admin', 'fictional@example.invalid', None)
        admin = Client()
        admin.force_login(staff)
        program = create_program()
        program_application = ProgramApplication.objects.create(program=program,
            member=create_member('00-0000-000-0099999'), public_reference='SPA-BROWSER-ORIGINAL')
        config = {
            'base': self.live_server_url,
            'adminSession': admin.cookies['sessionid'].value,
            'association': association_data() | {'contact_number': '09170000000', 'pwd_number': '00-0000-000-0000001'},
            'pdao': pdao_data() | {'contact_number': '09170000000', 'pwd_number': '00-0000-000-0000002'},
            'routes': {name: reverse('membership:' + name) for name in
                       ('registration_apply', 'registration_receipt', 'pdao_apply', 'pdao_receipt',
                        'review_home', 'registration_inbox', 'pdao_inbox')},
            'guidance': reverse('core:membership'),
            'program': {'url': reverse('programs:applications', args=[program.pk]),
                        'reference': program_application.short_reference,
                        'original': program_application.public_reference},
        }
        config_path = directory / 'config.json'
        config_path.write_text(json.dumps(config), encoding='utf-8')
        try:
            process = subprocess.run(['node', 'scripts/pdao_browser_qa.cjs', str(config_path)],
                capture_output=True, text=True, encoding='utf-8', timeout=90,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout, flush=True)
        finally:
            # The cookie grants access only to the disposable test instance.
            config.pop('adminSession')
            config_path.write_text(json.dumps(config), encoding='utf-8')
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(Member.objects.count(), 2)
        member = Member.objects.get(control_number='00-0000-000-0000001')
        self.assertEqual(member.registration_profile['pwd_number'], member.control_number)
        self.assertEqual(member.contact_number, '09170000000')
        self.assertEqual(PDAORegistration.objects.get().data['pwd_number'], '00-0000-000-0000002')
        self.assertEqual(PDAORegistration.objects.get().data['first_name'], 'Fictional')
        self.assertEqual(PDAORegistration.objects.get().current_data['first_name'], 'Reviewed')
        self.assertEqual(PDAORegistration.objects.get().current_data['contact_number'], '09170000003')
        self.assertEqual(PDAORegistration.objects.get().data['intake_channel'], 'online')
        self.assertEqual(PDAORegistration.objects.get().status, 'forwarded')
