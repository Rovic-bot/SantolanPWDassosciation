"""Synthetic acceptance for the single-screen onsite membership decision."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from members.models import Member
from ewaf.generation_models import SourceMutationBatch
from ewaf.test_source_writers import SourceHelpers
from .models import MembershipApplication, MembershipEvent, MembershipSettings
from . import registration_services as registration
from .registration_decisions import decide_registration
from .registration_models import RegistrationIntake, RegistrationRevision
from .test_pdf_registration import association_data, pdf_policy
from .test_registration_handoff import HandoffHelpers
from .test_registration_intake import staff, upload
from .test_registration_prefill import applicant_data


def accepted_office_invitation(intake, actor):
    """Synthetic prerequisite for existing decision tests; no external delivery.

    The office-verification suite exercises actual queue/transport/audit behavior.
    """
    from django.utils import timezone
    from .approval_email_models import approval_email_write
    from .pending_email_models import MembershipPendingEmail, MembershipPendingEmailAttempt
    from .office_verification import INVITATION_ACTION, INVITATION_REASON
    from .registration_models import registration_write
    revision = intake.revisions.get(number=intake.current_revision)
    with approval_email_write(), registration_write():
        job = MembershipPendingEmail.objects.create(intake=intake, revision=revision,
            expected_version=intake.version, reason=INVITATION_REASON,
            recipient=revision.data['email'], sender='association@example.invalid',
            subject='Synthetic office invitation', body='Synthetic invitation evidence',
            requested_by=actor, requested_by_label=actor.get_username(), state='sent',
            accepted_at=timezone.now(), attempt_count=1, backend='django.core.mail.backends.locmem.EmailBackend')
        MembershipPendingEmailAttempt.objects.create(email=job, number=1, outcome='accepted')
        registration.record_action(intake, INVITATION_ACTION, revision, actor=actor,
            reason=INVITATION_REASON, payload={'email_id': str(job.pk), 'status': 'pending'})
    return job


class DecisionHelpers:
    invited_by_default = True
    def setup_decisions(self):
        self.override = override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy())
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.actor = staff('synthetic_simple_decision', 'membership.decide_membershipapplication',
            'membership.correct_registrationintake', 'membership.verify_membershipapplication', 'members.view_member')
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})

    def make(self, *, files=None, data=None, invited=None):
        binding = registration.binding_for('synthetic-direct-decision')
        context = registration.issue_context(binding)
        intake = registration.submit_registration(context.pk, binding,
            association_data() | {'pwd_number': '00-0000-000-0000001'} | (data or {}), files)
        if self.invited_by_default if invited is None else invited:
            accepted_office_invitation(intake, self.actor)
        return intake

    def data(self, intake, **changes):
        values = association_data() | {'version': intake.version,
            'action': 'approve_registration',
            'pwd_number': intake.revisions.get(number=intake.current_revision).data.get('pwd_number', '')} | changes
        if intake.channel == 'online':
            values.setdefault('office_verification_confirmed', 'on')
        return {'prpwd_lookup_number': values.get('pwd_number', '')} | values

    def decide(self, intake, data=None, actor=None, **options):
        data = data if data is not None else self.data(intake)
        return decide_registration(intake.reference, user=actor or self.actor,
            data=data, action=data['action'], **options)


class RegistrationDecisionTests(DecisionHelpers, TestCase):
    def setUp(self):
        self.setup_decisions()

    @override_settings(SHORT_REFERENCES_ENABLED=True)
    def test_approved_reference_lookup_opens_full_member_record(self):
        from core.reference_services import allocate

        intake = self.make()
        self.decide(intake)
        member = Member.objects.get()
        code = allocate(intake)
        self.client.force_login(self.actor)
        for reference in (intake.reference, code, code.split('-')[1]):
            response = self.client.get(reverse('membership:registration_lookup'),
                                       {'reference': reference}, follow=True)
            self.assertEqual(response.redirect_chain, [(reverse('members:detail', args=[member.pk]), 302)])
            self.assertTemplateUsed(response, 'members/detail.html')
            self.assertContains(response, 'class="member-record-shell"')
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.filter(action='approved').count(), 1)

    def test_admin_form_uses_submitted_pwd_number_without_separate_assignment(self):
        intake = self.make()
        self.client.force_login(self.actor)
        response = self.client.get(reverse('membership:registration_lookup'), {'reference': intake.reference}, follow=True)
        self.assertContains(response, 'Approve membership')
        self.assertContains(response, 'Not approved')
        self.assertContains(response, 'PWD No.')
        self.assertNotContains(response, 'name="assigned_member_number"')
        for text in ('Processing review', 'Begin review', 'Reason / private review note',
                     'Save manual verification', 'Prepare membership approval', 'Record onsite observations'):
            self.assertNotContains(response, text)
        form = response.context['editor_form']
        self.assertFalse(form.fields['first_name'].disabled)
        self.assertEqual(form.initial['first_name'], 'Fictional')
        self.assertEqual(form.initial['pwd_number'], '00-0000-000-0000001')
        self.assertNotIn('reason', form.fields)
        self.assertNotIn('verified', form.fields)

    def test_correction_and_approval_create_one_member_and_retain_source_and_private_files(self):
        intake = self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        original = intake.revisions.get()
        attachment = original.attachments.get()
        data = self.data(intake, first_name='Corrected')
        self.client.force_login(self.actor)
        response = self.client.post(reverse('membership:registration_detail', args=[intake.reference]), data, follow=True)
        self.assertContains(response, 'Registration approved. The applicant is now a member.')
        self.assertContains(response, '00-0000-000-0000001')
        intake.refresh_from_db()
        member = Member.objects.get()
        self.assertEqual(response.redirect_chain, [(reverse('members:detail', args=[member.pk]), 302)])
        self.assertTemplateUsed(response, 'members/detail.html')
        self.assertEqual(response.context['member'], member)
        self.assertEqual(member.full_name, 'Corrected Example')
        self.assertEqual(member.control_number, '00-0000-000-0000001')
        self.assertEqual(member.registration_profile['pwd_number'], member.control_number)
        self.assertEqual(member.household_members, 5)
        self.assertEqual(str(member.household_monthly_income), '14500.50')
        self.assertEqual(member.registration_profile['family_members'], 6)
        self.assertEqual(member.registration_profile['four_ps_member'], 'Yes')
        self.assertEqual(intake.current_revision, 2)
        original.refresh_from_db()
        self.assertEqual(original.data['first_name'], 'Fictional')
        revised = intake.revisions.get(number=2)
        self.assertEqual(list(registration.active_attachments(revised)), [attachment])
        self.assertTrue(attachment.file.storage.exists(attachment.file.name))
        application = intake.membership_application
        self.assertTrue(application.prpwd_verified)
        self.assertEqual(application.prpwd_verified_by, self.actor)
        self.assertIsNotNone(application.prpwd_verified_at)
        self.assertEqual(application.decided_by, self.actor)
        self.assertEqual(application.member, member)
        self.assertEqual(MembershipEvent.objects.filter(action='approved').count(), 1)
        self.assertEqual(intake.actions.filter(action='correction_recorded').count(), 1)
        self.assertEqual(intake.actions.filter(action='registration_approved').count(), 1)
        self.assertNotContains(response, 'name="action" value="approve_registration"')

        # Retrying the same approval opens the same record without a second
        # membership or approval event.
        response = self.client.post(reverse('membership:registration_detail', args=[intake.reference]), data)
        self.assertRedirects(response, reverse('members:detail', args=[member.pk]))
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.filter(action='approved').count(), 1)

    def test_approval_without_member_view_access_keeps_permitted_confirmation(self):
        from django.contrib.auth.models import Permission

        intake = self.make()
        self.actor.user_permissions.remove(Permission.objects.get(
            content_type__app_label='members', codename='view_member'))
        self.client.force_login(self.actor)
        url = reverse('membership:registration_detail', args=[intake.reference])
        response = self.client.post(url, self.data(intake), follow=True)
        self.assertEqual(response.redirect_chain, [(url, 302)])
        self.assertContains(response, 'This applicant is now a member.')
        self.assertNotContains(response, 'Open member record')
        self.assertRedirects(self.client.get(reverse('membership:registration_lookup'),
                             {'reference': intake.reference}), url)
        self.assertEqual(self.client.get(reverse('members:detail', args=[Member.objects.get().pk])).status_code, 403)

    def test_decline_returns_to_registration_without_member_redirect(self):
        intake = self.make()
        self.client.force_login(self.actor)
        url = reverse('membership:registration_detail', args=[intake.reference])
        response = self.client.post(url, self.data(intake, action='decline_registration'), follow=True)
        self.assertEqual(response.redirect_chain, [(url, 302)])
        self.assertContains(response, 'This registration did not create a member.')
        self.assertFalse(Member.objects.exists())
        self.assertRedirects(self.client.get(reverse('membership:registration_lookup'),
                             {'reference': intake.reference}), url)

    def test_decline_needs_no_member_number_or_reason_and_creates_no_member(self):
        intake = self.make()
        data = self.data(intake, action='decline_registration', pwd_number='', first_name='Corrected')
        self.decide(intake, data)
        intake.refresh_from_db()
        self.assertEqual(intake.membership_application.status, 'rejected')
        self.assertEqual(intake.revisions.get(number=2).data['first_name'], 'Corrected')
        self.assertFalse(Member.objects.exists())
        self.assertEqual(self.decide(intake, data).pk, intake.pk)
        with self.assertRaises(ValidationError):
            self.decide(intake)
        self.assertEqual(MembershipEvent.objects.count(), 1)

    def test_approval_requires_pwd_number_and_never_uses_registration_reference(self):
        intake = self.make()
        self.client.force_login(self.actor)
        for number in ('', intake.reference):
            with self.subTest(number=number):
                response = self.client.post(reverse('membership:registration_detail', args=[intake.reference]),
                    self.data(intake, pwd_number=number))
                self.assertEqual(response.status_code, 400)
                self.assertIn('pwd_number', response.context['editor_form'].errors)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())

    def test_duplicate_number_blocks_entire_correction_and_decision(self):
        first = self.make()
        self.decide(first)
        second = self.make()
        with self.assertRaisesMessage(ValidationError, 'already in use'):
            self.decide(second, self.data(second, first_name='Must not save'))
        second.refresh_from_db()
        self.assertIsNone(second.membership_application_id)
        self.assertEqual(second.current_revision, 1)
        self.assertEqual(Member.objects.count(), 1)

    def test_different_hyphen_format_cannot_create_a_second_member_with_the_same_pwd(self):
        first = self.make()
        self.decide(first)
        second = self.make(data={'pwd_number': '0000000000000001'})
        self.assertEqual('00-0000-000-0000001'.replace('-', ''), '0000000000000001')
        with self.assertRaisesMessage(ValidationError, 'PWD No. is already in use'):
            self.decide(second)
        self.assertEqual(Member.objects.count(), 1)
        second.refresh_from_db()
        self.assertIsNone(second.membership_application_id)

    def test_pwd_correction_updates_member_and_retains_original_declaration(self):
        intake = self.make()
        original = intake.revisions.get(number=1)
        self.decide(intake, self.data(intake, pwd_number='00-0000-000-0000099'))
        member = Member.objects.get()
        self.assertEqual(member.control_number, '00-0000-000-0000099')
        self.assertEqual(member.registration_profile['pwd_number'], member.control_number)
        original.refresh_from_db()
        self.assertEqual(original.data['pwd_number'], '00-0000-000-0000001')
        self.assertEqual(intake.actions.get(action='registration_approved').payload['member_number_source'], 'pwd_number')

    def test_decision_only_actor_cannot_replace_submitted_pwd_or_supply_an_unsubmitted_one(self):
        decision_only = staff('synthetic_pwd_decider', 'membership.decide_membershipapplication', 'membership.verify_membershipapplication')
        intake = self.make()
        with self.assertRaises(ValidationError):
            self.decide(intake, self.data(intake, pwd_number='00-0000-000-0000099'), actor=decision_only)
        self.decide(intake, actor=decision_only)
        self.assertEqual(Member.objects.get().control_number, '00-0000-000-0000001')
        # Retained pre-requirement submission; new online intakes require the ID.
        from .registration_forms import RegistrationForm
        with patch('membership.registration_services.OnlineRegistrationForm', RegistrationForm):
            blank = self.make(data={'pwd_number': ''})
        with self.assertRaises(ValidationError):
            self.decide(blank, self.data(blank, pwd_number='00-0000-000-0000099'), actor=decision_only)
        self.assertEqual(Member.objects.count(), 1)

    def test_an_independently_posted_member_number_is_rejected(self):
        intake = self.make()
        with self.assertRaises(ValidationError):
            self.decide(intake, self.data(intake, assigned_member_number='00-0000-000-0000099'))
        self.assertFalse(Member.objects.exists())

    def test_preexisting_approved_member_keeps_its_original_number_and_label(self):
        from members.tests import create_member
        from .registration_models import registration_write
        intake = self.make()
        member = create_member('SYNTHETIC-LEGACY-001')
        with registration_write():
            intake.membership_application = member.application
            intake.state = 'membership_review'
            intake.save(update_fields=['membership_application', 'state'])
        self.client.force_login(self.actor)
        url = reverse('membership:registration_detail', args=[intake.reference])
        response = self.client.get(url)
        self.assertContains(response, 'Assigned member number:')
        self.assertContains(response, 'SYNTHETIC-LEGACY-001')
        self.assertFalse(response.context['approved_with_pwd_number'])
        self.assertEqual(self.client.post(url, self.data(intake)).status_code, 400)
        member.refresh_from_db()
        self.assertEqual(member.control_number, 'SYNTHETIC-LEGACY-001')
        self.assertEqual(Member.objects.count(), 1)

    def test_stale_version_and_unsupported_verification_fields_cannot_mutate(self):
        intake = self.make()
        for changes in ({'version': 999}, {'prpwd_verified': 'true'}, {'status': 'approved'}, {'household_members': '0'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.decide(intake, self.data(intake, **changes))
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertFalse(Member.objects.exists())

    def test_exact_retry_is_idempotent_but_changed_retry_cannot_overwrite_member(self):
        intake = self.make()
        data = self.data(intake, first_name='Corrected')
        self.decide(intake, data)
        self.decide(intake, data)
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 2)
        self.assertEqual(RegistrationRevision.objects.count(), 2)
        with self.assertRaises(ValidationError):
            self.decide(intake, data | {'first_name': 'Overwrite'})
        self.assertEqual(Member.objects.get().first_name, 'Corrected')

    def test_decision_permission_required_and_edit_permission_cannot_be_forged(self):
        intake = self.make()
        viewer = staff('synthetic_simple_viewer')
        with self.assertRaises(PermissionDenied):
            self.decide(intake, actor=viewer)
        decision_only = staff('synthetic_decision_only', 'membership.decide_membershipapplication', 'membership.verify_membershipapplication')
        self.decide(intake, self.data(intake, first_name='Unauthorized correction'), actor=decision_only)
        self.assertEqual(Member.objects.get().first_name, 'Fictional')
        self.assertEqual(RegistrationRevision.objects.count(), 1)

    def test_audit_failure_rolls_back_correction_member_decision_and_link(self):
        intake = self.make()
        original = registration.record_action

        def fail_decision(*args, **kwargs):
            if args[1] == 'registration_approved':
                raise RuntimeError('Synthetic audit failure')
            return original(*args, **kwargs)

        with patch.object(registration, 'record_action', side_effect=fail_decision), self.assertRaises(RuntimeError):
            self.decide(intake, self.data(intake, first_name='Corrected'))
        intake.refresh_from_db()
        self.assertIsNone(intake.membership_application_id)
        self.assertEqual(intake.version, 0)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())
        self.assertEqual(intake.actions.count(), 2)

    def test_public_or_csrf_less_requests_cannot_decide(self):
        intake = self.make()
        url = reverse('membership:registration_detail', args=[intake.reference])
        self.assertEqual(self.client.post(url, self.data(intake)).status_code, 302)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.actor)
        self.assertEqual(browser.post(url, self.data(intake)).status_code, 403)
        self.assertFalse(Member.objects.exists())


class ConcurrentRegistrationDecisions(DecisionHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_decisions()

    def test_concurrent_identical_approvals_create_one_member(self):
        intake = self.make()
        data = self.data(intake)
        ready = Barrier(2)

        def approve():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return self.decide(intake, data).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _: approve(), range(2))), [intake.pk, intake.pk])
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 2)

    def test_concurrent_formatted_pwd_duplicates_create_one_member(self):
        intakes = [self.make(), self.make(data={'pwd_number': '0000000000000001'})]
        payloads = [self.data(intake) for intake in intakes]
        ready = Barrier(2)

        def approve(index):
            close_old_connections()
            try:
                ready.wait(timeout=10)
                try:
                    self.decide(intakes[index], payloads[index])
                    return 'approved'
                except ValidationError as error:
                    self.assertIn('already in use', str(error))
                    return 'duplicate'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(approve, range(2))), ['approved', 'duplicate'])
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.filter(action='approved').count(), 1)


class ExistingLinkedRegistrationDecisionTests(HandoffHelpers, TestCase):
    def test_linked_pending_registration_can_be_corrected_and_decided_without_new_verification(self):
        self.setup_handoff()
        intake = self.make('walk_in')
        application = self.prepare(intake)
        self.verify(application)
        intake.refresh_from_db()
        application.refresh_from_db()
        old_note = application.verification_notes
        data = applicant_data() | {'version': intake.version, 'action': 'approve_registration',
            'assigned_member_number': application.control_number, 'first_name': 'Corrected'}
        result = decide_registration(intake.reference, user=self.actor, data=data, action=data['action'])
        application.refresh_from_db()
        self.assertEqual(result.membership_application_id, application.pk)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        self.assertEqual(Member.objects.get().first_name, 'Corrected')
        self.assertIsNone(application.prpwd_verified)
        proof = intake.actions.get(action='registration_approved')
        self.assertEqual(proof.payload['prior_verification']['notes'], old_note)
        self.assertTrue(proof.payload['prior_verification']['verified'])
        self.assertEqual(intake.actions.filter(action='membership_handoff').count(), 1)
        self.assertEqual(intake.actions.filter(action='membership_verification').count(), 1)


class RegistrationDecisionSourceTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        override = override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy())
        override.enable()
        self.addCleanup(override.disable)
        binding = registration.binding_for('synthetic-direct-source')
        context = registration.issue_context(binding)
        self.intake = registration.submit_registration(context.pk, binding,
            association_data() | {'pwd_number': '00-0000-000-0000007'})
        self.data = association_data() | {'version': self.intake.version, 'action': 'approve_registration',
            'pwd_number': '00-0000-000-0000007', 'prpwd_lookup_number': '00-0000-000-0000007', 'office_verification_confirmed': 'on'}
        accepted_office_invitation(self.intake, self.officer)
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        self.register()

    def decide(self, **changes):
        return decide_registration(self.intake.reference, user=self.officer, data=self.data,
            action=self.data['action'], **({'source_expected': {}} | changes))

    def test_direct_approval_and_retry_have_one_zero_program_source_batch(self):
        self.decide()
        self.decide()
        batch = SourceMutationBatch.objects.get(source_kind='membership')
        self.assertEqual(batch.scope_count, 0)
        self.assertEqual(len(batch.source_audits), 2)
        self.assertEqual(Member.objects.count(), 1)
        self.assert_transition(1)

    def test_fabricated_scope_and_missing_expected_tokens_fail_without_member(self):
        for expected in (None, self.expected()):
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                self.decide(source_expected=expected)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())

    def test_late_source_audit_failure_rolls_back_member_and_registration_decision(self):
        with patch('ewaf.shared_invalidation.finish', side_effect=ValidationError('Synthetic batch failure')):
            with self.assertRaises(ValidationError):
                self.decide()
        self.intake.refresh_from_db()
        self.assertIsNone(self.intake.membership_application_id)
        self.assertEqual(self.intake.version, 0)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())
