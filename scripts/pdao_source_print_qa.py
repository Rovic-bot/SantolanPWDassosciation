"""Render fictional PDAO applications and check their actual Chrome print output."""
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from membership.pdf_registration_forms import PDAOForm
from membership.test_pdf_registration import pdao_data


class PDAOSourceBrowserTests(SimpleTestCase):
    def test_source_form_print_layout(self):
        root = Path(settings.BASE_DIR)
        output = Path(os.environ.get('G12_ARTIFACT_DIR', tempfile.mkdtemp(prefix='pdao-print-qa-'))) / 'pdao-source-print'
        output.mkdir(parents=True, exist_ok=True)
        data = pdao_data() | {
            'first_name': 'Maria Luisa', 'middle_name': 'Santos', 'last_name': 'Dela Cruz',
            'suffix': 'Jr.', 'date_applied': '2026-11-05', 'birthdate': '1990-01-02',
            'sex': 'Female', 'civil_status': 'Married', 'education': 'College',
            'employment_status': 'Employed', 'employment_category': 'Private',
            'employment_nature': 'Permanent / Regular', 'occupation': 'Other',
            'occupation_other': 'Fictional research assistant', 'blood_type': 'O+',
            'disability_cause': 'Acquired', 'disability_cause_details': ['Injury'],
            'contact_number': '09170000000', 'landline': '0280000000', 'email': 'fictional@example.invalid',
            'province': 'Metro Manila', 'region': 'NCR', 'organization': 'Fictional Association',
            'organization_contact': 'Fictional Contact', 'organization_address': '12 Example Street',
            'organization_phone': '09170000001', 'father_last_name': 'Dela Cruz',
            'father_first_name': 'Juan', 'father_middle_name': 'Example', 'mother_last_name': 'Santos',
            'mother_first_name': 'Ana', 'mother_middle_name': 'Example', 'emergency_name': 'Juan Dela Cruz',
            'emergency_relationship': 'Father', 'emergency_phone': '09170000002',
            'pwd_number': '13-7400-001-0000001', 'sss_number': '00-0000000-0',
            'gsis_number': '00000000000', 'psn_number': '0000-0000-0000-0000',
            'philhealth_number': '00-000000000-0', 'philhealth_membership': 'Member',
        }
        for name, payload in [('filled', data), ('minimal', pdao_data()),
                              ('long', data | {field: 'Long example ' * (limit // 13)
                               for field, limit in [('house_street', 255), ('organization_address', 255),
                                                     ('organization', 150), ('emergency_name', 150)]})]:
            form = PDAOForm(payload)
            self.assertTrue(form.is_valid(), form.errors)
            html = render_to_string('membership/pdao/print.html', {
                'submitted': form.submitted_data() | {'intake_channel': 'online'},
                'registration': SimpleNamespace(pk=UUID('00000000-0000-4000-8000-000000000001'),
                                                short_reference='PDAO-000001')})
            html = html.replace('/static/', (root / 'static').as_uri() + '/')
            (output / f'{name}.html').write_text(html, encoding='utf-8')
        # Use the same validated filled declaration as the staff print fixture.
        form = PDAOForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        receipt = render_to_string('membership/pdao/receipt.html', {
            'submitted': form.submitted_data() | {'intake_channel': 'online'},
            'reference': 'PDAO-00000000-0000-4000-8000-000000000001',
            'received_at': datetime(2026, 11, 5, 4, 21, tzinfo=timezone.utc),
            'csrf_token': 'synthetic-browser-fixture',
        })
        (output / 'receipt.html').write_text(receipt.replace('/static/', (root / 'static').as_uri() + '/'), encoding='utf-8')
        result = subprocess.run(['node', str(root / 'scripts/pdao_source_print_qa.cjs'), str(output)],
                                capture_output=True, text=True, encoding='utf-8', timeout=90,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(f'PDAO source-form browser evidence: {output}\n{result.stdout}', flush=True)
