"""Fictional submissions for the two source-specific public forms."""
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from .models import MembershipApplication
from .pdf_registration_forms import AssociationPDFForm, PDAOForm, ASSOCIATION_PDF_KIND
from .registration_forms import RegistrationForm, OnsiteForm
from .registration_handoff import HandoffForm
from .registration_models import RegistrationIntake, RegistrationRevision
from .registration_profile import readonly_submission
from . import registration_services as services
from .test_registration_prefill import profile_policy
from .test_registration_intake import staff
from .test_registration_handoff import acceptance_policy, HandoffHelpers
from .tests import onsite_profile


def pdf_policy(**changes):
    return profile_policy(**({'applicant_profile': ASSOCIATION_PDF_KIND,
        'form_version': 'SYNTHETIC-ASSOCIATION-PDF-v1'} | changes))


def association_data():
    return {'last_name': 'Example', 'first_name': 'Fictional', 'middle_name': '',
        'birthdate': '1990-01-02', 'house_street': '12 Example Street', 'barangay': 'Santolan',
        'city': 'Pasig', 'region': 'NCR', 'family_members': '6', 'four_ps_member': 'Yes',
        'disability_type': 'Visual Disability', 'education': 'College Undergraduate',
        'household_monthly_income': '14500.50', 'household_members': '5', 'employment_status': 'unemployed',
        'email': 'fictional@example.invalid', 'pwd_number': '00-0000-000-0000001', 'acknowledgement': 'on'}


def pdao_data():
    return {'application_type': 'Renewal', 'date_applied': timezone.localdate().isoformat(),
        'email': 'fictional@example.invalid',
        'last_name': 'Example', 'first_name': 'Fictional', 'birthdate': '1990-01-02',
        'house_street': '12 Example Street', 'barangay': 'Santolan', 'city': 'Pasig',
        'disability_types': ['Visual Disability', 'Physical Disability'],
        'accomplished_by': 'Applicant', 'acknowledgement': 'on'}


@override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy())
class PDFRegistrationTests(TestCase):
    def submit(self):
        url = reverse('membership:registration_apply')
        page = self.client.get(url)
        payload = association_data() | {'context_id': page.context['context_id']}
        response = self.client.post(url, payload)
        self.assertRedirects(response, reverse('membership:registration_receipt'), fetch_redirect_response=False)
        return RegistrationIntake.objects.get(), payload

    def test_association_reference_receipt_immutable_payload_and_repeat_submission(self):
        intake, payload = self.submit()
        source = intake.revisions.get(number=1)
        self.assertTrue(intake.reference.startswith('AMR-'))
        self.assertEqual(source.data['profile_kind'], ASSOCIATION_PDF_KIND)
        self.assertEqual(source.data['family_members'], 6)
        self.assertEqual(source.data['four_ps_member'], 'Yes')
        self.assertEqual(source.data['education'], 'College Undergraduate')
        for absent in ('dependents', 'income_category', 'monthly_income', 'prpwd_verified', 'control_number'):
            self.assertNotIn(absent, source.data)
        receipt = self.client.get(reverse('membership:registration_receipt'))
        self.assertContains(receipt, intake.reference)
        self.assertContains(receipt, 'College Undergraduate')
        self.assertNotContains(receipt, 'Household monthly income')
        self.assertNotContains(receipt, 'Number of Household members')
        self.assertNotContains(receipt, 'Employment Status')
        self.assertNotContains(receipt, '14500.50')
        self.assertContains(receipt, 'SIGNATURE OVER PRINTED NAME')
        self.assertIn('no-store', receipt['Cache-Control'])
        form = readonly_submission(source.data, source.policy_snapshot)
        self.assertTrue(all(field.disabled for field in form.fields.values()))
        self.client.post(reverse('membership:registration_apply'), payload)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)
        self.assertRedirects(Client().get(reverse('membership:registration_receipt')), reverse('core:membership'), fetch_redirect_response=False)
        self.client.post(reverse('membership:registration_finish'))
        self.assertRedirects(self.client.get(reverse('membership:registration_receipt')), reverse('core:membership'), fetch_redirect_response=False)

    def test_association_rollback_if_audit_fails(self):
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertFalse(RegistrationRevision.objects.exists())

    def test_confirmation_reference_loads_same_prefilled_onsite_form_after_finish(self):
        intake, _ = self.submit()
        original = intake.revisions.get(number=1).data
        response = self.client.post(reverse('membership:registration_finish'))
        self.assertContains(response, intake.reference)
        self.assertContains(response, 'Barangay Santolan office')
        self.assertContains(response, 'Bring your PWD ID Card')
        self.assertRedirects(self.client.get(reverse('membership:registration_receipt')), reverse('core:membership'), fetch_redirect_response=False)
        actor = staff('synthetic_confirmed_reference_staff', 'membership.encode_membershipapplication')
        admin = Client()
        admin.force_login(actor)
        onsite = admin.get(reverse('membership:encode'))
        self.assertContains(onsite, 'Load online application')
        response = admin.get(reverse('membership:registration_lookup'),
            {'reference': response.context['reference']}, follow=True)
        self.assertContains(response, 'Association membership review')
        self.assertContains(response, 'Online application loaded.')
        form = response.context['submitted_form']
        for field in AssociationPDFForm.base_fields:
            with self.subTest(field=field):
                self.assertEqual(form.initial[field], original[field])
                self.assertTrue(form.fields[field].disabled)
        self.assertEqual(response.context['intake'].pk, intake.pk)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)
        self.assertTrue(intake.actions.filter(action='staff_form_viewed').exists())
        self.assertEqual(Client().get(reverse('membership:registration_lookup'),
            {'reference': intake.reference}).status_code, 302)

    def test_source_validation_and_pending_intake_allows_onsite_completion(self):
        form = RegistrationForm(association_data() | {'email': '', 'pwd_number': ''}, policy=pdf_policy())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.submitted_data()['pwd_number'], '')
        for changes in ({'birthdate': (timezone.localdate()+timedelta(days=1)).isoformat()},
                        {'family_members': '-1'}, {'status': 'approved'}, {'disability_type': 'unknown'},
                        {'acknowledgement': ''}):
            with self.subTest(changes=changes):
                self.assertFalse(RegistrationForm(association_data() | changes, policy=pdf_policy()).is_valid())

class PDAOPrintingTests(SimpleTestCase):
    # SimpleTestCase prohibits any database query, including session/registration
    # writes. These routes must work without an intake schema or active policy.
    def test_pdao_prints_all_selected_values_without_saving_or_issuing_reference(self):
        response = self.client.post(reverse('membership:pdao_prepare'), pdao_data() | {
            'organization': '<script>alert(1)</script>', 'guardian_name': 'unsupported'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse('membership:pdao_prepare'), pdao_data() | {'organization': '<script>alert(1)</script>'})
        self.assertContains(response, 'Your PDAO form is ready to print')
        # Source-form printing marks individual boxes instead of a prose list.
        self.assertContains(response, 'Selected: </span>Visual Disability')
        self.assertContains(response, 'Selected: </span>Physical Disability')
        self.assertContains(response, 'original old / expired PWD ID')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'AMR-')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)
        self.assertNotContains(self.client.get(reverse('membership:pdao_prepare')), 'alert(1)')

    def test_pdao_csrf_validation_no_query_reflection_and_method_limits(self):
        url = reverse('membership:pdao_prepare')
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, pdao_data()).status_code, 403)
        self.assertEqual(self.client.put(url, {}).status_code, 405)
        self.assertNotContains(self.client.get(url, {'first_name': 'DoNotReflect'}), 'DoNotReflect')
        self.assertEqual(self.client.post(url, pdao_data() | {'acknowledgement': ''}).status_code, 400)
        self.assertEqual(self.client.post(url, pdao_data() | {'first_name': 'x'*70000}).status_code, 413)
        self.assertEqual(self.client.post(url, pdao_data() | {'disability_types': ['Visual Disability']*2}).status_code, 400)
        self.assertFalse(PDAOForm(pdao_data() | {'occupation': 'Other'}).is_valid())

    def test_pdao_same_origin_browser_post_succeeds_with_csrf_checks_enabled(self):
        url = reverse('membership:pdao_prepare')
        for secure in (False, True):
            with self.subTest(secure=secure):
                client = Client(enforce_csrf_checks=True)
                page = client.get(url, secure=secure)
                # This policy lets native HTML forms keep a usable Origin header.
                self.assertEqual(page['Referrer-Policy'], 'same-origin')
                token = client.cookies[settings.CSRF_COOKIE_NAME].value
                origin = ('https' if secure else 'http') + '://testserver'
                response = client.post(url, pdao_data() | {'csrfmiddlewaretoken': token},
                    secure=secure, HTTP_ORIGIN=origin, HTTP_REFERER=origin + url)
                self.assertContains(response, 'Your PDAO form is ready to print')
                self.assertEqual(response['Referrer-Policy'], 'same-origin')
                self.assertIn('no-store', response['Cache-Control'])

    def test_pdao_null_and_foreign_origins_still_fail_even_with_valid_csrf_token(self):
        url = reverse('membership:pdao_prepare')
        client = Client(enforce_csrf_checks=True)
        client.get(url)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        for origin in ('null', 'https://foreign.example', 'http://testserver:9000'):
            with self.subTest(origin=origin):
                response = client.post(url, pdao_data() | {'csrfmiddlewaretoken': token}, HTTP_ORIGIN=origin)
                self.assertEqual(response.status_code, 403)

    def test_pdao_https_referer_fallback_and_missing_token_protection(self):
        url = reverse('membership:pdao_prepare')
        client = Client(enforce_csrf_checks=True)
        client.get(url, secure=True)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post(url, pdao_data() | {'csrfmiddlewaretoken': token},
            secure=True, HTTP_REFERER='https://testserver' + url)
        self.assertContains(response, 'Your PDAO form is ready to print')
        response = client.post(url, pdao_data(), secure=True,
            HTTP_ORIGIN='https://testserver', HTTP_REFERER='https://testserver' + url)
        self.assertEqual(response.status_code, 403)

    def test_blank_downloads_are_exact_sources_and_private_paths_are_unavailable(self):
        for category, filename in (
                ('association', 'Santolan_PWD_Membership_Form_A4_Fixed.pdf'),
                ('pdao', 'PWD ID Application Form (2024-2025) (New And Renewal).pdf')):
            response = self.client.get(reverse('membership:blank_form', args=[category]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertEqual(b''.join(response.streaming_content), (Path(settings.BASE_DIR)/filename).read_bytes())
            response.close()
        self.assertEqual(self.client.get(reverse('membership:blank_form', args=['private'])).status_code, 404)


class PDFRegistrationHandoffTests(HandoffHelpers, TestCase):
    def test_pdf_source_is_retained_while_missing_onsite_assessment_is_completed(self):
        self.setup_handoff()
        policy = acceptance_policy() | {'applicant_profile': ASSOCIATION_PDF_KIND, 'form_version': 'SYNTHETIC-PDF-v1'}
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=policy):
            binding = services.binding_for('synthetic-pdf-handoff')
            context = services.issue_context(binding, channel='walk_in', user=self.actor)
            intake = services.submit_registration(context.pk, binding, association_data(), channel='walk_in', user=self.actor)
            services.review_registration(intake.reference, user=self.actor, version=0,
                action='begin_review', reason='Fictional onsite visit')
            intake.refresh_from_db()
            observations = {'version': intake.version, 'reason': 'Fictional PDF quantity review', 'civil_alternative': 'birth'}
            for key in OnsiteForm.pdf_keys:
                observations['finding_' + key] = 'sighted'
                observations['method_' + key] = policy['onsite_methods'][0]
            incomplete = {key: value for key, value in observations.items() if key != 'finding_pwd_id_copies'}
            with self.assertRaises(ValidationError):
                services.record_onsite(intake.reference, user=self.actor, data=incomplete)
            services.record_onsite(intake.reference, user=self.actor, data=observations)
            intake.refresh_from_db()
            form = HandoffForm(intake=intake, policy=policy)
            self.assertEqual(form.initial['first_name'], 'Fictional')
            self.assertNotIn('first_name', form.fields)
            self.assertNotIn('dependents', form.fields)
            self.assertNotIn('income_category', form.fields)
            source = intake.revisions.get(number=1).data
            # Existing approval workflow still requires its separate assessment.
            prepared = self.form(intake, **{name: value for name, value in onsite_profile().items()
                if name in form.fields and not form.fields[name].disabled and name not in ('control_number', 'submission_token')})
            application = self.prepare(intake, form=prepared)
            self.assertEqual(application.first_name, 'Fictional')
            self.assertFalse(Member.objects.filter(application=application).exists())
            self.assertEqual(intake.revisions.get(number=1).data, source)

            self.assertIsNone(application.dependents)
            self.assertIsNone(application.monthly_income)
            self.assertEqual(application.household_members, 5)
            self.assertEqual(str(application.household_monthly_income), '14500.50')
            self.assertEqual(application.employment_status, 'unemployed')
            self.approve(self.verify(application))
            member = Member.objects.get(application=application)
            self.assertEqual(member.household_members, 5)
            self.assertEqual(str(member.household_monthly_income), '14500.50')
            self.assertEqual(member.registration_profile['four_ps_member'], 'Yes')
            self.assertEqual(member.registration_profile['family_members'], 6)
            self.assertIsNone(member.dependents)
