"""Information-change follow-up on the session-bound program receipt."""
import os
from pathlib import Path

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from members.models import Member
from .models import ProgramApplication
from . import test_application_workflow as application_tests
from .application_workflow import CONTRACT


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   PROGRAM_TRACKING_ENABLED=True, PROGRAM_TRACKING_QR_ENABLED=True)
class InformationChangeReceiptTests(TestCase):
    identity = application_tests.ConfirmedApplicationTests.identity
    data = application_tests.ConfirmedApplicationTests.data

    def setUp(self):
        application_tests.ConfirmedApplicationTests.setUp(self)
        # The current form fills a blank member email at submission. Use a
        # retained address here so this test isolates the change-report notice.
        self.member.email = 'registered@example.invalid'
        self.member.save(update_fields=['email'])

    def receipt(self, report):
        self.client.post(self.verify_url, self.identity())
        # This fixture has no published document requirements; an unsolicited
        # calendar upload is rejected by the current application form.
        response = self.client.post(self.apply_url, self.data(), follow=True)
        # Retained historical declarations still receive their original notice.
        application = ProgramApplication.objects.get()
        declaration = application.source_snapshot['application_confirmation']
        declaration.pop('information_basis')
        declaration.update(current_information=report,
            change_details='PRIVATE reported employment change' if report != 'unchanged' else '')
        application.save(update_fields=['source_snapshot'])
        response = self.client.get(reverse('programs:submitted', args=[self.program.pk]))
        self.assertTemplateUsed(response, 'programs/submitted.html')
        return response

    def test_changed_receipt_shows_office_notice_reference_and_private_qr_without_changing_member(self):
        before = Member.objects.values().get(pk=self.member.pk)
        response = self.receipt('changed')
        application = ProgramApplication.objects.get()
        self.assertContains(response, 'Confirm your information at the barangay office')
        self.assertContains(response, 'Please visit the Barangay Santolan office')
        self.assertContains(response, 'Bring your application reference number or saved receipt.')
        self.assertContains(response, application.short_reference)
        self.assertNotContains(response, 'PRIVATE reported employment change')
        self.assertNotContains(response, 'different@example.invalid')
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        qr_url = reverse('programs:tracking_receipt_qr', args=[self.program.pk])
        self.assertContains(response, qr_url)
        qr = self.client.get(qr_url)
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr['Content-Type'], 'image/png')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(Client().get(qr_url).status_code, 404)
        self.assertRedirects(Client().get(reverse('programs:submitted', args=[self.program.pk])),
                             reverse('programs:detail', args=[self.program.pk]))
        if os.environ.get('G12_ARTIFACT_DIR'):
            directory = Path(os.environ['G12_ARTIFACT_DIR'])
            (directory / 'change-receipt.html').write_bytes(response.content)
            (directory / 'change-receipt-qr.png').write_bytes(qr.content)

    def test_historical_uncertain_information_keeps_office_confirmation_guidance(self):
        # New submissions do not ask for changes, but retained uncertain
        # declarations must continue to show the office-visit instruction.
        application = ProgramApplication.objects.create(program=self.program, member=self.member,
            public_reference='SYNTHETIC-HISTORICAL-UNCERTAIN', source_snapshot={
                'application_confirmation': {'contract': CONTRACT, 'current_information': 'uncertain',
                    'confirm_information': True, 'change_details': 'PRIVATE historical uncertainty'}})
        session = self.client.session
        session['program_receipt'] = str(application.pk)
        session.save()
        response = self.client.get(reverse('programs:submitted', args=[self.program.pk]))
        self.assertContains(response, 'id="information-change-notice"')
        self.assertNotContains(response, 'PRIVATE historical uncertainty')

    def test_unchanged_information_does_not_get_a_change_confirmation_instruction(self):
        response = self.receipt('unchanged')
        self.assertNotContains(response, 'id="information-change-notice"')
        self.assertContains(response, 'Track this application')

    @override_settings(PROGRAM_TRACKING_QR_ENABLED=False)
    def test_office_notice_remains_available_when_qr_is_disabled(self):
        response = self.receipt('changed')
        self.assertContains(response, 'id="information-change-notice"')
        self.assertContains(response, 'Track this application')
        self.assertNotContains(response, reverse('programs:tracking_receipt_qr', args=[self.program.pk]))
