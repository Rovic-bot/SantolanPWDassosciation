"""Rendering/privacy boundaries for optional, device-local OCR. No database access."""
import json
import os
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from .pdao_forms import PDAOOnlineForm, PDAOOnsiteForm, PRIVACY_NOTICE
from .registration_forms import OnlineRegistrationForm, OnsiteRegistrationForm


class ScanInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = []

    def handle_starttag(self, tag, attrs):
        if tag in {'input', 'select', 'textarea', 'button'}:
            self.controls.append(dict(attrs))


class DocumentOCRTests(SimpleTestCase):
    def test_scanner_has_no_submittable_fields_or_required_inputs(self):
        html = render_to_string('membership/registration/ocr_scan.html')
        inputs = ScanInputs()
        inputs.feed(html)
        self.assertTrue(inputs.controls)
        for control in inputs.controls:
            self.assertNotIn('name', control)
            self.assertNotIn('required', control)
            self.assertNotEqual(control.get('type'), 'submit')
        self.assertIn('not uploaded or attached', html)

    def test_real_application_templates_include_scan_without_changing_form_contract(self):
        policy = json.loads((settings.BASE_DIR / 'config/registration_policy.development.json').read_text(encoding='utf-8'))
        cases = [
            ('association', 'membership/registration/apply.html', OnlineRegistrationForm(policy=policy)),
            ('pdao', 'membership/pdao/apply.html', PDAOOnlineForm()),
            ('onsite-association', 'membership/onsite/intake.html', OnsiteRegistrationForm(policy=policy)),
            ('onsite-pdao', 'membership/pdao/onsite.html', PDAOOnsiteForm()),
        ]
        for name, template, form in cases:
            with self.subTest(name=name):
                request = RequestFactory().get('/')
                request.user = AnonymousUser()
                html = render_to_string(template, {'form': form, 'policy': policy,
                    'privacy_notice': PRIVACY_NOTICE, 'user': AnonymousUser(),
                    'request': request,
                    'public_redesign_enabled': True, 'context_id': 'synthetic-only'})
                self.assertEqual(html.count('data-document-ocr '), 1)
                self.assertIn('document-ocr.js', html)
                self.assertIn('name="acknowledgement"', html)
                self.assertIn('name="birthdate"', html)
                self.assertIn('name="pwd_number"', html)
                if os.environ.get('OCR_ARTIFACT_DIR'):
                    output = Path(os.environ['OCR_ARTIFACT_DIR'])
                    output.mkdir(parents=True, exist_ok=True)
                    (output / f'{name}.html').write_text(html, encoding='utf-8')
