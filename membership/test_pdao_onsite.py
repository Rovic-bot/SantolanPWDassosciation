"""Onsite PDAO intake remains private, permission-scoped and separate from membership."""
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from members.models import Member
from .models import MembershipApplication
from . import pdao_services as services
from .pdao_forms import PDAOOnlineForm, PDAOOnsiteForm
from .pdao_models import PDAORegistration
from .registration_models import RegistrationIntake
from .test_pdf_registration import pdao_data
from .test_pdao_registration import actor
from .test_pdao_review import review_data


@override_settings(PDAO_REGISTRATION_ENABLED=True, SHORT_REFERENCES_ENABLED=True)
class PDAOOnsiteTests(TestCase):
    def setUp(self):
        self.staff = actor(services.VIEW, services.ADD, services.CORRECT, services.PRINT)
        self.client.force_login(self.staff)
        self.url = reverse('membership:pdao_onsite')

    def payload(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        return pdao_data() | {'submission_token': page.context['form'].initial['submission_token']}

    def test_same_pdao_fields_and_separate_staff_acknowledgement(self):
        online, onsite = PDAOOnlineForm(), PDAOOnsiteForm()
        self.assertEqual(list(online.fields), list(onsite.fields))
        self.assertEqual(online.groups, onsite.groups)
        for name, field in online.fields.items():
            self.assertEqual(type(field), type(onsite.fields[name]))
            if name == 'email':
                self.assertTrue(field.required)
                self.assertFalse(onsite.fields[name].required)
            else:
                self.assertEqual(field.required, onsite.fields[name].required)
            self.assertEqual(getattr(field, 'choices', None), getattr(onsite.fields[name], 'choices', None))
        self.assertNotEqual(online.fields['acknowledgement'].label, onsite.fields['acknowledgement'].label)
        self.assertContains(self.client.get(self.url), 'Save PDAO application')

    def test_save_retry_and_correction_preserve_onsite_provenance(self):
        data = self.payload()
        response = self.client.post(self.url, data)
        item = PDAORegistration.objects.get()
        self.assertRedirects(response, reverse('membership:pdao_detail', args=[item.pk]))
        original = item.data
        self.assertEqual(item.status, 'received')
        self.assertEqual(original['intake_channel'], 'walk_in')
        self.assertIsNotNone(item.receipt_revoked_at)
        self.assertTrue(item.events.filter(action='onsite_submitted', actor=self.staff).exists())
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(self.client.post(self.url, data | {'first_name': 'Changed'}).status_code, 400)
        self.assertEqual(PDAORegistration.objects.count(), 1)
        services.correct(item.pk, self.staff, review_data(item, first_name='Reviewed'))
        item.refresh_from_db()
        self.assertEqual(item.data, original)
        self.assertEqual(item.current_data['intake_channel'], 'walk_in')
        self.assertEqual(item.current_data['first_name'], 'Reviewed')
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertEqual(self.client.get(reverse('membership:pdao_receipt')).status_code, 404)

    def test_permission_revocation_anonymous_access_and_csrf(self):
        data = self.payload()
        self.assertEqual(Client().get(self.url).status_code, 302)
        self.assertEqual(Client().post(self.url, data).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.staff)
        self.assertEqual(csrf.post(self.url, data).status_code, 403)
        self.staff.has_perm(services.ADD)
        self.staff.user_permissions.remove(Permission.objects.get(codename='add_pdaoregistration'))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.assertFalse(PDAORegistration.objects.exists())

    def test_tokens_cannot_cross_channel_or_session(self):
        onsite = self.payload()
        public = self.client.get(reverse('membership:pdao_apply')).context['form'].initial['submission_token']
        self.assertEqual(self.client.post(self.url, onsite | {'submission_token': public}).status_code, 403)
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), onsite).status_code, 403)
        other = Client()
        other.force_login(self.staff)
        self.assertEqual(other.post(self.url, onsite).status_code, 403)
        self.assertFalse(PDAORegistration.objects.exists())

    def test_invalid_or_tampered_fields_and_audit_failure_do_not_create_records(self):
        data = self.payload()
        for change in ({'first_name': ''}, {'first_name': ['One', 'Two']}, {'intake_channel': 'online'},
                       {'status': 'forwarded'}, {'contact_number': 'not a number'}, {'acknowledgement': ''}):
            self.assertEqual(self.client.post(self.url, data | change).status_code, 400)
        with patch.object(services, 'record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, data)
        self.assertFalse(PDAORegistration.objects.exists())

    @override_settings(PDAO_REGISTRATION_ENABLED=False)
    def test_staff_can_record_onsite_when_public_intake_is_closed(self):
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        self.assertEqual(PDAORegistration.objects.get().data['intake_channel'], 'walk_in')

    def test_private_preview_uses_latest_saved_details_and_no_public_access(self):
        self.client.post(self.url, self.payload())
        item = PDAORegistration.objects.get()
        services.correct(item.pk, self.staff, review_data(item, first_name='Corrected'))
        url = reverse('membership:pdao_print', args=[item.pk])
        preview = self.client.get(url, {'preview': '1'})
        self.assertContains(preview, 'Corrected Example')
        self.assertContains(preview, 'pdao-embedded-preview')
        self.assertNotContains(preview, 'id="pdao-preview-dialog"')
        self.assertEqual(preview['X-Frame-Options'], 'SAMEORIGIN')
        self.assertIn('no-store', preview['Cache-Control'])
        self.assertEqual(Client().get(url, {'preview': '1'}).status_code, 302)
        self.staff.user_permissions.remove(Permission.objects.get(codename='print_pdaoregistration'))
        self.assertEqual(self.client.get(url, {'preview': '1'}).status_code, 403)
