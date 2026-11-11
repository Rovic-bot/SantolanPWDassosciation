"""Public form visibility must not activate collection or expose staff fields."""
from django.test import TestCase, override_settings
from django.urls import reverse

from .pdf_registration_forms import AssociationPDFForm
from .test_registration_prefill import profile_policy


class RegistrationEntryTests(TestCase):
    @override_settings(ASSOCIATION_REGISTRATION_POLICY=None)
    def test_closed_form_is_blank_disabled_and_cannot_accept_submission(self):
        url = reverse('core:membership')
        response = self.client.get(url, {'first_name': 'DoNotReflect'})
        self.assertContains(response, 'Association Membership Form fields')
        self.assertContains(response, 'Onsite registration')
        self.assertNotContains(response, 'DoNotReflect')
        fields = [field for title, group in response.context['registration_preview_sections'] for field in group]
        self.assertEqual([field.name for field in fields], [name for title, names in AssociationPDFForm.groups for name in names])
        self.assertTrue(all(field.field.disabled for field in fields))
        self.assertNotContains(response, '<form')
        for excluded in ('type="file"', 'name="preview-control_number"', 'name="preview-monthly_income"', 'name="preview-prpwd_verified"'):
            self.assertNotContains(response, excluded)
        self.assertNotIn('sessionid', response.cookies)
        self.assertEqual(self.client.post(url, {'first_name': 'DoNotSave'}).status_code, 405)
        self.assertEqual(self.client.post(reverse('membership:registration_apply'), {}).status_code, 503)

    def test_open_registration_uses_existing_protected_submission_route(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=profile_policy()):
            response = self.client.get(reverse('core:membership'))
        self.assertContains(response, reverse('membership:registration_apply'))
        self.assertContains(response, 'Start online membership registration')
        self.assertFalse(response.context['registration_preview_sections'])
        self.assertNotContains(response, 'Form preview')
