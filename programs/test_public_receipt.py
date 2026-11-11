"""Results receipt guidance preserves the existing session/reference contract."""
from django.test import Client, TestCase
from django.urls import reverse
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from programs.testsupport import private_media, application_fixture


class PublicReceiptTests(TestCase):
    def setUp(self):
        private_media(self)
        self.program = create_program(eligible_disability_types=[])
        self.member = create_member('SYNTHETIC-RECEIPT-MEMBER')
        self.application = application_fixture(self.program, self.member)
        self.route = reverse('programs:submitted', args=[self.program.pk])

    def authorize_session(self):
        session = self.client.session
        session['program_receipt'] = str(self.application.pk)
        session.save()

    def test_receipt_shows_retained_reference_results_and_accessible_save_copy_print_guidance(self):
        self.authorize_session()
        before = ProgramApplication.objects.values().get(pk=self.application.pk)
        response = self.client.get(self.route)
        self.assertContains(response, self.application.public_reference)
        self.assertContains(response, self.program.name)
        self.assertContains(response, f'href="{reverse("core:announcements")}?category=results"')
        self.assertContains(response, 'Submission does not guarantee eligibility or selection')
        self.assertContains(response, 'results may be published')
        self.assertContains(response, 'not published automatically at the application deadline')
        self.assertContains(response, 'save or print this confirmation using your browser')
        self.assertContains(response, "select its text and use your device's copy command")
        self.assertContains(response, reverse('core:contact'))
        self.assertContains(response, 'only in this browser session')
        self.assertNotContains(response, self.member.full_name)
        self.assertNotContains(response, self.member.control_number)
        self.assertNotContains(response, self.application.status_token)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('private', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')
        self.assertEqual(ProgramApplication.objects.values().get(pk=self.application.pk), before)
        self.assertEqual(self.client.post(self.route).status_code, 405)

    def test_reference_or_application_identifier_alone_cannot_open_a_receipt(self):
        detail = reverse('programs:detail', args=[self.program.pk])
        stranger = Client()
        for query in ({}, {'reference': self.application.public_reference}, {'application': str(self.application.pk)}):
            self.assertRedirects(stranger.get(self.route, query), detail)
        self.authorize_session()
        self.client.get(self.route)
        self.assertRedirects(stranger.get(self.route), detail)

    def test_receipt_session_cannot_be_used_for_another_program(self):
        self.authorize_session()
        other = create_program()
        self.assertRedirects(self.client.get(reverse('programs:submitted', args=[other.pk])),
                             reverse('programs:detail', args=[other.pk]))
        self.assertContains(self.client.get(self.route), self.application.public_reference)

    def test_retired_status_and_qr_routes_remain_unavailable(self):
        for name in ('status', 'qr'):
            response = Client().get(reverse(f'programs:{name}', args=[self.application.status_token]))
            self.assertEqual(response.status_code, 410)
            self.assertNotContains(response, self.application.public_reference, status_code=410)
            self.assertNotContains(response, self.member.control_number, status_code=410)
