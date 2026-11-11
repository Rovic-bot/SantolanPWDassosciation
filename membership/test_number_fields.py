"""Submitted number declarations reject letters without losing zeroes/history."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from .pdao_forms import PDAOOnlineForm
from .registration_editor import RegistrationEditorForm
from .registration_forms import RegistrationForm
from .test_pdf_registration import association_data, pdao_data, pdf_policy


ASSOCIATION_NUMBERS = ('zip_code', 'contact_number', 'spouse_contact', 'guardian_contact',
                       'pwd_number', 'voter_certification_number', 'philhealth_number')
PDAO_NUMBERS = ('pwd_number', 'landline', 'contact_number', 'organization_phone',
                'sss_number', 'gsis_number', 'psn_number', 'philhealth_number', 'emergency_phone')


class OnlineNumberValidationTests(SimpleTestCase):
    def association(self, **changes):
        return RegistrationForm(association_data() | changes, policy=pdf_policy())

    def pdao(self, **changes):
        return PDAOOnlineForm(pdao_data() | {'submission_token': 'synthetic-form-token'} | changes)

    def test_letters_and_scientific_notation_are_rejected_in_every_number_field(self):
        for make, names in ((self.association, ASSOCIATION_NUMBERS), (self.pdao, PDAO_NUMBERS)):
            for name in names:
                for value in ('ABC123', '1e10', '0123x', '１２３'):
                    with self.subTest(field=name, value=value, form=make.__name__):
                        form = make(**{name: value})
                        self.assertFalse(form.is_valid())
                        self.assertIn(name, form.errors)

    def test_leading_zeroes_are_retained_in_submitted_payloads(self):
        for make, names in ((self.association, ASSOCIATION_NUMBERS), (self.pdao, PDAO_NUMBERS)):
            values = {name: '001234' for name in names}
            form = make(**values)
            self.assertTrue(form.is_valid(), form.errors)
            payload = form.submitted_data()
            for name, expected in values.items():
                self.assertEqual(payload[name], expected)

    def test_formatted_ids_keep_hyphens_and_reject_malformed_groups(self):
        for make, names in ((self.association, ('pwd_number', 'voter_certification_number', 'philhealth_number')),
                            (self.pdao, ('pwd_number', 'sss_number', 'gsis_number', 'psn_number', 'philhealth_number'))):
            for name in names:
                form = make(**{name: '00-0000-000-0000001'})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.submitted_data()[name], '00-0000-000-0000001')
                for value in ('--', '12--34', '-123', '123-', '12.34'):
                    with self.subTest(field=name, value=value):
                        invalid = make(**{name: value})
                        self.assertFalse(invalid.is_valid())
                        self.assertIn(name, invalid.errors)

    def test_contact_numbers_remain_optional_and_address_still_accepts_street_names(self):
        for make in (self.association, self.pdao):
            form = make(house_street='12A Example Street', contact_number='')
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.submitted_data()['house_street'], '12A Example Street')
            for value in ('0917-000-0000', '12.3', '+639170000000', '0' * 31):
                invalid = make(contact_number=value)
                self.assertFalse(invalid.is_valid())
                self.assertIn('contact_number', invalid.errors)

    def test_admin_can_preserve_original_text_but_cannot_add_new_lettered_numbers(self):
        source = self.association()
        self.assertTrue(source.is_valid(), source.errors)
        previous = source.submitted_data() | {'pwd_number': 'OLD-ID', 'contact_number': '(02) 1234'}
        revision = SimpleNamespace(data=previous, policy_snapshot=pdf_policy())
        data = association_data() | {'pwd_number': 'OLD-ID', 'contact_number': '(02) 1234', 'version': 0}
        for editable in (True, False):
            editor = RegistrationEditorForm(data, revision=revision, version=0, editable=editable)
            self.assertTrue(editor.is_valid(), editor.errors)
            self.assertEqual(editor.changed_payload(previous), previous)
        corrected = RegistrationEditorForm(data | {'pwd_number': 'NEW-ID'}, revision=revision, version=0)
        self.assertFalse(corrected.is_valid())
        self.assertIn('pwd_number', corrected.errors)
        corrected = RegistrationEditorForm(data | {'pwd_number': '00-001'}, revision=revision, version=0)
        self.assertTrue(corrected.is_valid(), corrected.errors)
        self.assertEqual(corrected.changed_payload(previous)['pwd_number'], '00-001')
        self.assertFalse(self.association(pwd_number='OLD-ID').is_valid())
