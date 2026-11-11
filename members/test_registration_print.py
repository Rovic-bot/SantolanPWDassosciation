"""Synthetic private print access and original-registration preservation."""
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from membership.models import MembershipApplication
from membership.registration_models import RegistrationAction
from membership.test_registration_decisions import DecisionHelpers
from membership.tests import grant
from .models import Member
from .printing import registration_print_data
from .tests import create_member


class MemberRegistrationPrintTests(DecisionHelpers, TestCase):
    def setUp(self):
        self.setup_decisions()
        self.intake = self.make()
        self.decide(self.intake)
        self.member = Member.objects.select_related('application').get()
        self.url = reverse('members:registration_print', args=[self.member.pk])
        self.document_url = self.url + '?preview=1'
        self.client.force_login(self.actor)

    def test_approved_print_uses_retained_template_fields_and_excludes_assessment(self):
        before = deepcopy(self.member.application.registration_profile)
        popup = self.client.get(self.url)
        self.assertContains(popup, 'data-membership-preview-auto-open')
        self.assertContains(popup, 'Print / Save PDF')
        self.assertNotContains(popup, 'Fictional')
        self.assertIn('no-store', popup['Cache-Control'])
        response = self.client.get(self.document_url)
        for text in ('MEMBERSHIP FORM', 'Fictional', '00-0000-000-0000001',
                     'SIGNATURE OVER PRINTED NAME', 'Approved member registration', self.intake.reference):
            self.assertContains(response, text)
        for text in ('14500.50', 'household_monthly_income', 'Employment Status',
                     'Membership approval requires authorized onsite review.'):
            self.assertNotContains(response, text)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertNotContains(response, '<nav')
        self.assertNotContains(response, '<button')
        self.assertTemplateUsed(response, 'membership/registration/association_print.html')
        self.member.application.refresh_from_db()
        self.assertEqual(self.member.application.registration_profile, before)
        self.assertTrue(RegistrationAction.objects.filter(intake=self.intake,
            action='staff_completed_form_viewed', actor=self.actor).exists())

    def test_later_member_profile_edits_do_not_replace_original_registration(self):
        Member.objects.filter(pk=self.member.pk).update(first_name='Later profile change', full_name='Later profile change')
        response = self.client.get(self.document_url)
        self.assertEqual(response.context['submitted']['first_name'], 'Fictional')
        self.assertNotContains(response, 'Later profile change')

    def test_public_and_staff_without_each_required_permission_cannot_print(self):
        for url in (self.url, self.document_url):
            self.assertEqual(Client().get(url).status_code, 302)
        permissions = ['accounts.access_dashboard', 'members.view_member',
            'membership.view_membershipapplication', 'membership.view_registrationintake']
        for missing in permissions:
            with self.subTest(missing=missing):
                actor = get_user_model().objects.create_user('missing_' + missing.replace('.', '_'), is_staff=True)
                grant(actor, *(name for name in permissions if name != missing))
                client = Client()
                client.force_login(actor)
                for url in (self.url, self.document_url):
                    self.assertEqual(client.get(url).status_code, 403)

    def test_linked_registration_policy_gate_remains_enforced(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=None):
            for url in (self.url, self.document_url):
                self.assertEqual(self.client.get(url).status_code, 503)

    def test_access_audit_failure_prevents_private_response(self):
        before = RegistrationAction.objects.count()
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('Synthetic audit failure')):
            for url in (self.url, self.document_url):
                with self.assertRaisesMessage(RuntimeError, 'Synthetic audit failure'):
                    self.client.get(url)
        self.assertEqual(RegistrationAction.objects.count(), before)

    def test_missing_member_and_mutation_requests_are_rejected(self):
        self.assertEqual(self.client.get(reverse('members:registration_print', args=[self.member.pk + 1000])).status_code, 404)
        for url in (self.url, self.document_url):
            self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(Member.objects.count(), 1)

    def test_member_record_offers_print_action_with_original_application_permission(self):
        detail = reverse('members:detail', args=[self.member.pk])
        response = self.client.get(detail)
        self.assertContains(response, self.url)
        self.assertContains(response, 'data-membership-form-preview')
        viewer = get_user_model().objects.create_user('synthetic_member_only', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'members.view_member')
        self.client.force_login(viewer)
        response = self.client.get(detail)
        self.assertNotContains(response, self.url)
        self.assertNotContains(response, 'id="membership-form-dialog"')

    def test_approved_staff_submission_print_identifies_approval(self):
        self.intake.refresh_from_db()
        response = self.client.get(reverse('membership:registration_form', args=[self.intake.reference, self.intake.current_revision]))
        self.assertContains(response, 'Approved member registration')
        self.assertContains(response, '00-0000-000-0000001')
        self.assertContains(response, 'association-print-preview')
        self.assertNotContains(response, 'Pending intake is not membership approval')

    def test_print_projection_preserves_zero_dates_and_escapes_entered_text(self):
        source = deepcopy(self.member.application.registration_profile)
        source.update(family_members=0, last_name='<script>synthetic()</script>', date_issued='2025-03-04')
        MembershipApplication.objects.filter(pk=self.member.application_id).update(registration_profile=source)
        response = self.client.get(self.document_url)
        self.assertEqual(response.context['submitted']['family_members'], 0)
        self.assertContains(response, '03/04/25')
        self.assertContains(response, '&lt;script&gt;synthetic()&lt;/script&gt;')
        self.assertNotContains(response, '<script>synthetic()</script>')

    def test_older_revision_is_not_labeled_as_the_approved_registration(self):
        intake = self.make()
        self.decide(intake, data=self.data(intake, first_name='Corrected',
            pwd_number='00-0000-000-0000002'))
        intake.refresh_from_db()
        self.assertEqual(intake.current_revision, 2)
        response = self.client.get(reverse('membership:registration_form', args=[intake.reference, 1]))
        self.assertContains(response, 'Fictional')
        self.assertNotContains(response, 'Approved member registration')
        self.assertEqual(response.context['member_number'], '')


class OlderMemberRegistrationPrintTests(TestCase):
    def setUp(self):
        self.member = create_member('SYNTHETIC-OLDER-PRINT')
        self.member.application.refresh_from_db()
        self.actor = get_user_model().objects.create_user('synthetic_older_print_staff', is_staff=True)
        grant(self.actor, 'accounts.access_dashboard', 'members.view_member', 'membership.view_membershipapplication')
        self.client.force_login(self.actor)

    def test_older_registration_preserves_unsplit_name_address_and_blank_unknowns(self):
        data = registration_print_data(self.member.application)
        self.assertEqual(data['name_as_recorded'], 'Sample Applicant')
        self.assertEqual(data['address_as_recorded'], 'Test address, Santolan')
        self.assertEqual(data['last_name'], '')
        self.assertEqual(data['family_members'], '')
        self.assertEqual(data['pwd_number'], '')
        response = self.client.get(reverse('members:registration_print', args=[self.member.pk]) + '?preview=1')
        self.assertContains(response, 'NAME AS RECORDED')
        self.assertContains(response, 'ADDRESS AS RECORDED')
        self.assertIn('no-store', response['Cache-Control'])

    def test_older_education_and_civil_status_are_not_reclassified_to_fit_choices(self):
        application = self.member.application
        application.education = 'college'
        application.civil_status = 'widowed'
        data = registration_print_data(application)
        self.assertEqual(data['education'], '')
        self.assertEqual(data['education_as_recorded'], 'College')
        self.assertEqual(data['civil_status'], '')
        self.assertEqual(data['civil_status_as_recorded'], 'Widowed')
