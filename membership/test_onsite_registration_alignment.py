"""Public and onsite Association intake share applicant fields and persistence."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from members.models import Member
from . import registration_services as services
from .models import MembershipApplication, MembershipSettings
from .registration_decisions import decide_registration
from .registration_models import RegistrationIntake
from .test_pdf_registration import association_data, pdf_policy
from .test_registration_intake import staff


@override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy(upload_slots=[]))
class OnsiteRegistrationAlignmentTests(TestCase):
    def setUp(self):
        self.actor = staff('synthetic_aligned_intake',
            'membership.encode_membershipapplication', 'membership.encode_registrationintake',
            'membership.correct_registrationintake', 'membership.decide_membershipapplication',
            'membership.verify_membershipapplication')
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        self.client.force_login(self.actor)
        self.onsite_url = reverse('membership:encode')
        self.public_url = reverse('membership:registration_apply')
        self.data = association_data() | {
            'pwd_number': '00-0000-000-0000001', 'zip_code': '1610',
            'contact_number': '9170000000', 'email': 'fictional@example.test',
            'spouse_name': 'Fictional Spouse', 'spouse_contact': '9170000001',
            'guardian_name': 'Fictional Guardian', 'guardian_contact': '9170000002',
            'voter_certification_number': '001-002', 'philhealth_number': '003-004',
        }

    def test_all_onsite_entry_points_require_email_and_pwd_with_shared_applicant_fields(self):
        public = Client().get(self.public_url).context['form']
        public_sections = [(title, [field.name for field in fields])
                           for title, fields in public.profile_sections]
        urls = [self.onsite_url, reverse('membership:registration_encode', args=['walk_in'])]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'membership/onsite/section.html')
                form = response.context['form']
                self.assertEqual([name for name in form.fields if name != 'prpwd_lookup_number'], list(public.fields))
                self.assertTrue(form['prpwd_lookup_number'].is_hidden)
                self.assertEqual([(title, [field.name for field in fields])
                                  for title, fields in form.profile_sections], public_sections)
                self.assertTrue(form.fields['pwd_number'].required)
                self.assertIn('required', form['pwd_number'].as_widget())
                self.assertTrue(form.fields['email'].required)
                self.assertIn('required', form['email'].as_widget())
                for name, field in public.fields.items():
                    if name not in ('pwd_number', 'email'):
                        self.assertEqual(form.fields[name].required, field.required)
                        self.assertEqual(form.fields[name].label, field.label)
                        # Online example placeholders do not change the shared input contract.
                        self.assertEqual({key: value for key, value in form.fields[name].widget.attrs.items() if key != 'placeholder'},
                                         {key: value for key, value in field.widget.attrs.items() if key != 'placeholder'})
                        self.assertEqual(getattr(form.fields[name], 'choices', None),
                                         getattr(field, 'choices', None))
                for old_field in ('control_number', 'monthly_income', 'dependents', 'disability_information'):
                    self.assertNotContains(response, f'name="{old_field}"')
                self.assertContains(response, 'Load online application')
        self.assertTrue(public.fields['pwd_number'].required)
        self.assertTrue(public.fields['email'].required)

    def test_registration_alias_preserves_canonical_permissions_and_admin_tools(self):
        for url in ('/admin/members/registration', '/admin/members/registration/'):
            self.assertRedirects(self.client.get(url), self.onsite_url)
            anonymous = Client().get(url, follow=True)
            self.assertContains(anonymous, 'name="username"')
            self.assertNotContains(anonymous, 'data-onsite-form')
        self.assertEqual(reverse('admin:index'), '/admin/')

    def test_guided_registration_stays_off_public_pages(self):
        onsite = self.client.get(self.onsite_url)
        self.assertContains(onsite, 'data-onsite-section=', count=7)
        self.assertContains(onsite, 'data-review-application', count=1)
        self.assertContains(onsite, 'data-preference="dark"', count=1)
        for url in (self.public_url, reverse('core:home'), reverse('core:dashboard')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'css/onsite-registration.css')
            self.assertNotContains(response, 'js/onsite-registration.js')

    def test_retired_printed_intake_page_rejects_get_and_post_without_writes(self):
        from .registration_models import RegistrationSubmissionContext, RegistrationAction
        models = (RegistrationSubmissionContext, RegistrationIntake, RegistrationAction, MembershipApplication, Member)
        before = [model.objects.count() for model in models]
        url = reverse('membership:registration_encode', args=['printed'])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.data).status_code, 404)
        self.assertEqual(before, [model.objects.count() for model in models])

    def test_blank_or_invalid_pwd_blocks_onsite_post_without_saving(self):
        page = self.client.get(self.onsite_url)
        for number in ('', '   ', 'AMR-123', '12--34'):
            with self.subTest(number=number):
                response = self.client.post(self.onsite_url, self.data | {
                    'pwd_number': number, 'context_id': page.context['context_id']})
                self.assertEqual(response.status_code, 400)
                self.assertIn('pwd_number', response.context['form'].errors)
                self.assertEqual(response.context['form']['first_name'].value(), 'Fictional')
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(Member.objects.exists())

    def test_required_pwd_is_also_enforced_by_the_staff_submission_service(self):
        binding = services.binding_for('synthetic-onsite-required-id')
        for channel in ('walk_in', 'printed'):
            with self.subTest(channel=channel):
                context = services.issue_context(binding, user=self.actor, channel=channel)
                with self.assertRaises(ValidationError):
                    services.submit_registration(context.pk, binding,
                        self.data | {'pwd_number': ''}, user=self.actor, channel=channel)
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_missing_blank_or_invalid_email_blocks_onsite_post_without_saving(self):
        page = self.client.get(self.onsite_url)
        for email in (None, '', '   ', 'not-an-email'):
            with self.subTest(email=email):
                data = self.data | {'context_id': page.context['context_id']}
                if email is None:
                    data.pop('email')
                else:
                    data['email'] = email
                response = self.client.post(self.onsite_url, data)
                self.assertEqual(response.status_code, 400)
                self.assertIn('email', response.context['form'].errors)
                self.assertEqual(response.context['form']['pwd_number'].value(), self.data['pwd_number'])
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(Member.objects.exists())

    def test_required_email_is_enforced_by_the_staff_submission_service(self):
        binding = services.binding_for('synthetic-onsite-required-email')
        for channel in ('walk_in', 'printed'):
            for email in ('', '   ', 'invalid'):
                with self.subTest(channel=channel, email=email):
                    context = services.issue_context(binding, user=self.actor, channel=channel)
                    with self.assertRaises(ValidationError):
                        services.submit_registration(context.pk, binding,
                            self.data | {'email': email}, user=self.actor, channel=channel)
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_onsite_save_and_approval_retain_shared_fields_and_original_pwd_number(self):
        page = self.client.get(self.onsite_url)
        posted = self.data | {'context_id': page.context['context_id']}
        response = self.client.post(self.onsite_url, posted)
        intake = RegistrationIntake.objects.get()
        self.assertRedirects(response, reverse('membership:registration_detail', args=[intake.reference]))
        self.assertEqual(intake.channel, 'walk_in')
        source = intake.revisions.get(number=1)
        self.assertEqual(source.actor, self.actor)
        canonical = {'city': 'City of Pasig', 'region': 'National Capital Region (NCR)',
                     'contact_number': '+639170000000', 'spouse_contact': '+639170000001',
                     'guardian_contact': '+639170000002'}
        for name, value in self.data.items():
            if name not in ('family_members', 'household_members', 'acknowledgement'):
                self.assertEqual(source.data[name], canonical.get(name, value))
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.client.post(self.onsite_url, posted)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        decide_registration(intake.reference, user=self.actor, action='approve_registration',
            data=self.data | canonical | {'version': intake.version, 'action': 'approve_registration',
                'prpwd_lookup_number': self.data['pwd_number']})
        member = Member.objects.get()
        self.assertEqual(member.control_number, self.data['pwd_number'])
        self.assertEqual(member.email, self.data['email'])
        self.assertEqual(member.registration_profile, source.data)
        self.assertEqual(member.household_members, 5)
        self.assertEqual(str(member.household_monthly_income), '14500.50')

    def test_online_submission_loads_same_fields_for_membership_approval(self):
        public = Client()
        context = public.get(self.public_url).context['context_id']
        response = public.post(self.public_url, association_data() | {'context_id': context})
        self.assertRedirects(response, reverse('membership:registration_receipt'))
        intake = RegistrationIntake.objects.get()
        url = reverse('membership:registration_detail', args=[intake.reference])
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'membership/registration/review_sections.html')
        editor = response.context['editor_form']
        self.assertTrue(editor.fields['pwd_number'].required)
        self.assertEqual(editor.initial['first_name'], 'Fictional')
        self.assertEqual(editor.initial['pwd_number'], association_data()['pwd_number'])
        source = intake.revisions.get()
        self.assertEqual([field.name for _, fields in editor.editor_sections for field in fields],
                         [name for _, names in editor.profile_groups for name in names])
        response = self.client.post(url, association_data() | {
            'version': intake.version, 'action': 'approve_registration', 'pwd_number': ''})
        self.assertEqual(response.status_code, 400)
        self.assertIn('pwd_number', response.context['editor_form'].errors)
        from .test_registration_decisions import accepted_office_invitation
        accepted_office_invitation(intake, self.actor)
        response = self.client.post(url, self.data | {
            'version': intake.version, 'action': 'approve_registration',
            'prpwd_lookup_number': self.data['pwd_number'], 'office_verification_confirmed': 'on',
            'email': association_data()['email']})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Member.objects.get().control_number, self.data['pwd_number'])
        source.refresh_from_db()
        self.assertEqual(source.data['pwd_number'], association_data()['pwd_number'])

    def test_staff_intake_remains_permission_checked(self):
        url = reverse('membership:registration_encode', args=['walk_in'])
        self.assertEqual(Client().get(url).status_code, 302)
        viewer = staff('synthetic_aligned_viewer')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.onsite_url).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            services.issue_context(services.binding_for('synthetic-no-encode'),
                                   user=viewer, channel='walk_in')
