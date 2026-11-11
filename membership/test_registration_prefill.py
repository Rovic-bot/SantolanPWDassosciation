"""Synthetic full applicant form -> reference -> same-record staff retrieval."""
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from members.models import Member, DisabilityType
from .models import MembershipApplication
from .registration_forms import RegistrationForm
from .registration_models import RegistrationIntake, RegistrationRevision
from .registration_policy import available
from .registration_profile import INPUT_FIELDS, PROFILE_KIND
from . import registration_services as services
from .tests import onsite_profile
from .test_registration_intake import synthetic_policy, staff, submitted


def profile_policy(**changes):
    return synthetic_policy(**({'applicant_profile': PROFILE_KIND,
        'applicant_profile_reference': 'SYNTHETIC FULL APPLICANT FIELD REVIEW; NOT OPERATING APPROVAL',
        'form_version': 'SYNTHETIC-APPLICANT-PROFILE-v1'} | changes))


def applicant_data():
    source = onsite_profile()
    return {name: source.get(name, '') for name in INPUT_FIELDS} | {
        'first_name': 'Synthetic', 'acknowledgement': 'on'}


class RegistrationPrefillTests(TestCase):
    def setUp(self):
        self.override = override_settings(ASSOCIATION_REGISTRATION_POLICY=profile_policy())
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.data = applicant_data()
        self.actor = staff('synthetic_prefill_staff', 'membership.encode_membershipapplication',
                           'membership.correct_registrationintake')
        self.apply_url = reverse('membership:registration_apply')
        self.lookup_url = reverse('membership:registration_lookup')

    def submit(self):
        response = self.client.get(self.apply_url)
        self.assertEqual(response.status_code, 200)
        context = response.context['context_id']
        response = self.client.post(self.apply_url, self.data | {'context_id': context})
        self.assertRedirects(response, reverse('membership:registration_receipt'), fetch_redirect_response=False)
        return RegistrationIntake.objects.get(), context

    def test_all_applicant_fields_reference_receipt_inbox_and_prefill_use_same_pending_record(self):
        intake, context = self.submit()
        payload = intake.revisions.get(number=1).data
        self.assertEqual(payload['profile_kind'], PROFILE_KIND)
        self.assertEqual(set(INPUT_FIELDS) - set(payload), set())
        self.assertEqual(payload['full_name'], 'Synthetic Applicant')
        self.assertNotIn('control_number', payload)
        self.assertNotIn('monthly_income', payload)
        self.assertNotIn('prpwd_verified', payload)
        receipt = self.client.get(reverse('membership:registration_receipt'))
        self.assertContains(receipt, intake.reference)
        self.assertContains(receipt, 'Synthetic')
        self.assertContains(receipt, 'Test Street')
        self.assertContains(receipt, 'Visual Disability')
        self.client.post(self.apply_url, self.data | {'context_id': context})
        self.client.force_login(self.actor)
        onsite = self.client.get(reverse('membership:encode'))
        self.assertContains(onsite, 'Load online application')
        self.assertContains(onsite, self.lookup_url)
        inbox = self.client.get(reverse('membership:registration_inbox'))
        self.assertContains(inbox, intake.reference)
        self.assertContains(inbox, 'Synthetic Applicant')
        response = self.client.get(self.lookup_url, {'reference': intake.reference}, follow=True)
        self.assertEqual(response.status_code, 200)
        form = response.context['submitted_form']
        for name in INPUT_FIELDS:
            with self.subTest(field=name):
                self.assertEqual(form.initial[name], payload[name])
                self.assertTrue(form.fields[name].disabled)
        self.assertContains(response, 'name="submitted-first_name"')
        self.assertContains(response, 'value="Synthetic"')
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)

    def test_expanded_fieldset_requires_explicit_contract_and_staff_fields_are_rejected(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=profile_policy(applicant_profile_reference='')):
            self.assertFalse(available('public'))
            self.assertEqual(self.client.get(self.apply_url).status_code, 503)
        for name in ('control_number', 'monthly_income', 'household_monthly_income',
                     'prpwd_verified', 'status', 'profile_kind', 'income_category_label'):
            with self.subTest(field=name):
                form = RegistrationForm(self.data | {name: 'forged'}, policy=profile_policy())
                self.assertFalse(form.is_valid())
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            form = RegistrationForm(self.data, policy=synthetic_policy())
            self.assertFalse(form.is_valid())

    def test_shared_onsite_validation_and_no_member_save(self):
        for change in ({'dependents': '-1'}, {'dependents': '1.5'}, {'birthdate': '2999-01-01'},
                       {'no_middle_name': '', 'middle_name': ''}, {'suffix': 'other', 'suffix_other': ''},
                       {'disability_types': ['999999']}, {'income_category': 'made_up'}):
            with self.subTest(change=change):
                self.assertFalse(RegistrationForm(self.data | change, policy=profile_policy()).is_valid())
        form = RegistrationForm(self.data, policy=profile_policy())
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(TypeError):
            form.profile_form.save()
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_private_lookup_denies_anonymous_revoked_permissions_and_other_session_receipt(self):
        intake, context = self.submit()
        stranger = Client()
        self.assertEqual(stranger.get(self.lookup_url, {'reference': intake.reference}).status_code, 302)
        self.assertRedirects(stranger.get(reverse('membership:registration_receipt'), {'reference': intake.reference}), reverse('core:membership'), fetch_redirect_response=False)
        self.client.force_login(self.actor)
        self.actor.user_permissions.clear()
        self.assertEqual(self.client.get(self.lookup_url, {'reference': intake.reference}).status_code, 403)
        self.assertEqual(self.client.get(reverse('membership:registration_detail', args=[intake.reference])).status_code, 403)

    def test_lookup_failures_are_generic_and_read_only(self):
        intake, context = self.submit()
        self.client.force_login(self.actor)
        for value in ('invalid', 'AMR-' + str(uuid4()), intake.reference + 'extra'):
            with self.subTest(value=value):
                response = self.client.get(self.lookup_url, {'reference': value})
                self.assertContains(response, 'No accessible pending application matches', status_code=404)
                self.assertNotContains(response, 'Synthetic Applicant', status_code=404)
        self.assertEqual(self.client.post(self.lookup_url, {'reference': intake.reference}).status_code, 405)
        self.assertEqual(RegistrationIntake.objects.count(), 1)

    def test_corrections_keep_original_profile_and_refuse_silent_fieldset_downgrade(self):
        intake, context = self.submit()
        original = intake.revisions.get().data
        self.client.force_login(self.actor)
        url = reverse('membership:registration_correct', args=[intake.reference])
        response = self.client.get(url)
        self.assertEqual(response.context['form'].initial['street'], 'Test Street')
        response = self.client.post(url, self.data | {'street': 'Corrected synthetic street',
            'version': intake.version, 'reason': 'Synthetic applicant correction'})
        self.assertEqual(response.status_code, 302)
        intake.refresh_from_db()
        self.assertEqual(intake.revisions.get(number=1).data, original)
        self.assertEqual(intake.revisions.get(number=2).data['street'], 'Corrected synthetic street')
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            self.assertEqual(self.client.get(url).status_code, 503)
            with self.assertRaises(ValidationError):
                services.correct_registration(intake.reference, user=self.actor, version=intake.version,
                    reason='Cannot discard structured history', data=submitted())
        self.assertEqual(RegistrationRevision.objects.count(), 2)
        self.assertEqual(Member.objects.count(), 0)

    def test_retained_choices_display_even_if_catalog_changes_and_audit_failure_blocks_delivery(self):
        intake, context = self.submit()
        self.client.force_login(self.actor)
        url = reverse('membership:registration_detail', args=[intake.reference])
        with patch('members.disability_catalog.current_types', return_value=DisabilityType.objects.none()):
            response = self.client.get(url)
            self.assertContains(response, 'Visual Disability')
            self.assertEqual(list(response.context['submitted_form'].fields['disability_types'].choices),
                             [tuple(row) for row in intake.revisions.get().data['disability_choices']])
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.get(url)

    def test_legacy_minimal_pending_forms_remain_retrievable(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            response = self.client.get(self.apply_url)
            self.client.post(self.apply_url, submitted() | {'context_id': response.context['context_id']})
        intake = RegistrationIntake.objects.get()
        self.client.force_login(self.actor)
        response = self.client.get(self.lookup_url, {'reference': intake.reference}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['submitted_form'].initial['full_name'], 'Synthetic Applicant')
        self.assertNotIn('first_name', response.context['submitted_form'].fields)

