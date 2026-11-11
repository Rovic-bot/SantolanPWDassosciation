"""Issued reference QR -> authenticated onsite prefill, on synthetic data only."""
from base64 import b64decode
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

from PIL import Image
import qrcode
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from members.models import Member
from .models import MembershipApplication
from .pdf_registration_forms import AssociationPDFForm
from .registration_models import RegistrationIntake, RegistrationRevision
from .test_pdf_registration import association_data, pdf_policy
from .test_registration_intake import staff


@override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy(upload_slots=[]), SHORT_REFERENCES_ENABLED=True)
class RegistrationReceiptQRTests(TestCase):
    def setUp(self):
        self.apply_url = reverse('membership:registration_apply')
        self.receipt_url = reverse('membership:registration_receipt')
        self.finish_url = reverse('membership:registration_finish')
        self.lookup_url = reverse('membership:registration_lookup')

    def submit(self):
        page = self.client.get(self.apply_url)
        data = association_data() | {'context_id': page.context['context_id'],
            'contact_number': '09170000001', 'email': 'fictional@example.test',
            'spouse_name': 'Fictional Spouse', 'spouse_contact': '09170000002',
            'guardian_name': 'Fictional Guardian', 'guardian_contact': '09170000003',
            'voter_certification_number': '001-002', 'philhealth_number': '003-004', 'zip_code': '01610'}
        self.assertRedirects(self.client.post(self.apply_url, data), self.receipt_url,
                             fetch_redirect_response=False)
        return RegistrationIntake.objects.get()

    def assert_qr(self, response, reference):
        self.assertEqual(response.context['reference_display'], reference)
        self.assertContains(response, 'QR code for membership reference ' + reference)
        self.assertContains(response, 'Bring your PWD ID Card')
        self.assertContains(response, 'Barangay Santolan office')
        self.assertContains(response, 'verify your information')
        self.assertContains(response, 'Print / save reference slip')
        self.assertIn('no-store', response['Cache-Control'])
        uri = response.context['reference_qr']
        self.assertTrue(uri.startswith('data:image/png;base64,'))
        with Image.open(BytesIO(b64decode(uri.split(',', 1)[1]))) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.width, image.height)
            self.assertGreaterEqual(image.width, 192)
            self.assertEqual(image.getpixel((0, 0)), 255)
        return uri

    def test_receipt_and_finished_screen_encode_only_the_same_displayed_reference(self):
        intake = self.submit()
        reference = intake.short_reference
        self.assertRegex(reference, r'^AMR-[0-9]{6,}$')
        with patch('membership.registration_receipt.qrcode.make', wraps=qrcode.make) as make:
            receipt = self.client.get(self.receipt_url, {'reference': 'AMR-999999'})
            first = self.assert_qr(receipt, reference)
            make.assert_called_once_with(reference, box_size=8, border=4)
        with patch('membership.registration_receipt.qrcode.make', wraps=qrcode.make) as make:
            finished = self.client.post(self.finish_url, {'reference': 'AMR-999999'})
            self.assertEqual(self.assert_qr(finished, reference), first)
            make.assert_called_once_with(reference, box_size=8, border=4)
        for private in ('Fictional Example', '1990-01-02', '12 Example Street', '09170000001',
                        'fictional@example.test', '14500.50'):
            self.assertNotContains(finished, private)
        self.assertRedirects(self.client.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)
        self.assertEqual(self.client.post(self.finish_url).context['reference_qr'], first)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertFalse(Member.objects.exists())

    def test_qr_does_not_allow_another_browser_to_retrieve_private_form_or_confirmation(self):
        intake = self.submit()
        self.client.post(self.finish_url)
        stranger = Client()
        self.assertRedirects(stranger.get(self.receipt_url, {'reference': intake.short_reference}), reverse('core:membership'), fetch_redirect_response=False)
        with patch('membership.registration_receipt.qrcode.make') as make:
            response = stranger.post(self.finish_url, {'reference': intake.short_reference})
            self.assertEqual(response.context['reference_qr'], '')
            self.assertNotContains(response, intake.short_reference)
            self.assertNotContains(response, 'data:image/png;base64,')
            make.assert_not_called()
        self.assertEqual(stranger.get(self.lookup_url, {'reference': intake.short_reference}).status_code, 302)

    def test_qr_reference_prefills_saved_fields_before_office_verification_and_approval(self):
        intake = self.submit()
        original = deepcopy(intake.revisions.get(number=1).data)
        with patch('membership.registration_receipt.qrcode.make', wraps=qrcode.make) as make:
            self.client.post(self.finish_url)
            scanned_reference = make.call_args.args[0]
        actor = staff('synthetic_qr_prefill', 'membership.encode_membershipapplication',
                      'membership.encode_registrationintake', 'membership.correct_registrationintake',
                      'membership.decide_membershipapplication', 'membership.verify_membershipapplication')
        from .models import MembershipSettings
        from .test_registration_decisions import accepted_office_invitation
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        accepted_office_invitation(intake, actor)
        admin = Client()
        admin.force_login(actor)
        onsite = admin.get(reverse('membership:encode'))
        self.assertContains(onsite, self.lookup_url)
        response = admin.get(self.lookup_url, {'reference': scanned_reference}, follow=True)
        self.assertContains(response, 'Online application loaded.')
        self.assertContains(response, 'PWD ID Card')
        self.assertEqual(response.context['intake'].pk, intake.pk)
        form = response.context['editor_form']
        for name in AssociationPDFForm.base_fields:
            self.assertEqual(form.initial[name], original[name], name)
        self.assertTrue(form.fields['pwd_number'].required)
        self.assertEqual(form['pwd_number'].value(), original['pwd_number'])
        self.assertEqual([field.name for field in form if not field.is_hidden
                          and field.field.required and not field.value()], [])
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(Member.objects.exists())
        # Retain the prefilled details and explicitly attest completed reviews.
        data = {field.name: '' if field.value() is None else field.value()
                for field in form if not field.field.disabled}
        data.update(pwd_number=original['pwd_number'], prpwd_lookup_number=original['pwd_number'],
                    office_verification_confirmed='on', action='approve_registration')
        detail_url = reverse('membership:registration_detail', args=[intake.reference])
        self.assertRedirects(admin.post(detail_url, data), detail_url)
        intake.refresh_from_db()
        self.assertEqual(intake.revisions.get(number=1).data, original)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        member = Member.objects.get()
        self.assertEqual(member.control_number, data['pwd_number'])
        self.assertEqual(member.registration_profile, intake.revisions.get(number=intake.current_revision).data)
        # Printed labels/values are regenerated for the new PWD number; every
        # other retained value must remain the same as the online declaration.
        self.assertEqual({key: value for key, value in member.registration_profile.items() if key != 'profile_sections'},
                         {key: value for key, value in (original | {'pwd_number': data['pwd_number']}).items()
                          if key != 'profile_sections'})

    def test_starting_another_form_clears_the_previous_reference_and_qr(self):
        intake = self.submit()
        self.client.post(self.finish_url)
        self.client.get(self.apply_url)
        with patch('membership.registration_receipt.qrcode.make') as make:
            response = self.client.post(self.finish_url)
            self.assertEqual(response.context['reference_qr'], '')
            self.assertNotContains(response, intake.short_reference)
            make.assert_not_called()
