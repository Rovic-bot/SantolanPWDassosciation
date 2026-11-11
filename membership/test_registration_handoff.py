"""Fictional onsite acceptance only; never an institutional operating policy."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from documents.models import DocumentType, MembershipDocumentRequirement
from members.models import Member
from .forms import fingerprint, requirements_snapshot
from .models import MembershipSettings, MembershipApplication, MembershipEvent
from .registration_forms import OnsiteForm
from .registration_handoff import HandoffForm, handoff_policy
from .registration_models import RegistrationIntake, RegistrationAction
from .registration_policy import RegistrationUnavailable
from . import registration_services as registration
from . import services
from .test_registration_intake import staff, upload
from .test_registration_prefill import profile_policy, applicant_data


def acceptance_policy():
    return profile_policy(onsite_enabled=True, handoff_enabled=True,
        identity_procedure_reference='FICTIONAL IDENTITY PROCEDURE',
        requirements_procedure_reference='FICTIONAL CHECKLIST ACCEPTANCE',
        assessment_procedure_reference='FICTIONAL ASSESSMENT PROCEDURE',
        identifier_procedure_reference='FICTIONAL ASSIGNED CONTROL NUMBER PROCEDURE',
        decision_authority_reference='FICTIONAL MEMBERSHIP DECISION AUTHORITY',
        membership_requirements_fingerprint=fingerprint(requirements_snapshot()))


class HandoffHelpers:
    def setup_handoff(self, actor=None):
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        self.requirement = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Synthetic approved private scan'))
        self.policy = acceptance_policy()
        override = override_settings(ASSOCIATION_REGISTRATION_POLICY=self.policy)
        override.enable()
        self.addCleanup(override.disable)
        self.actor = actor or staff('synthetic_handoff_staff', 'membership.encode_registrationintake',
            'membership.encode_membershipapplication', 'membership.review_registrationintake',
            'membership.onsite_registrationintake', 'membership.correct_registrationintake',
            'membership.view_registration_documents', 'documents.view_membershipapplicationdocument',
            'membership.verify_membershipapplication', 'membership.decide_membershipapplication',
            'members.view_member', 'documents.verify_document')

    def make(self, channel='online'):
        binding = registration.binding_for('synthetic-handoff-' + channel)
        actor = None if channel == 'online' else self.actor
        context = registration.issue_context(binding, channel=channel, user=actor)
        intake = registration.submit_registration(context.pk, binding, applicant_data(), user=actor, channel=channel)
        registration.review_registration(intake.reference, user=self.actor, version=0,
            action='begin_review', reason='Fictional onsite visit')
        self.observe(intake)
        intake.refresh_from_db()
        return intake

    def observe(self, intake, **changes):
        intake.refresh_from_db()
        data = {'version': intake.version, 'reason': 'Fictional observations', 'civil_alternative': 'birth'}
        for key in OnsiteForm.keys:
            data['finding_' + key] = 'sighted'
            data['method_' + key] = self.policy['onsite_methods'][0]
        registration.record_onsite(intake.reference, user=self.actor, data=data | changes)

    def form(self, intake, data=None, **changes):
        intake.refresh_from_db()
        initial = HandoffForm(intake=intake, policy=handoff_policy())
        values = data or {'submission_token': initial.initial['submission_token'],
            'control_number': 'SYNTHETIC-' + str(intake.pk)[:8],
            'identity_basis': 'Fictional approved identity checks complete',
            'requirements_basis': 'Fictional five-item acceptance, envelope physically reviewed',
            'assessor': 'Fictional authorized assessor', 'assessed_on': timezone.localdate().isoformat(),
            'assessment_basis': 'Fictional completed assessment record TEST-ASSESSMENT-1',
            'control_number_basis': 'Fictional authorized assignment record TEST-NUMBER-1',
            'duplicate_review': 'Fictional existing-person review: no unresolved match', 'accepted': 'on'}
        form = HandoffForm(values | changes, MultiValueDict({f'document_{self.requirement.pk}': [upload()]}),
            intake=intake, policy=handoff_policy())
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def prepare(self, intake, **options):
        return registration.handoff_registration(intake.reference, user=self.actor,
            form=options.pop('form', None) or self.form(intake), **options)

    def verify(self, application, **options):
        return services.record_verification(application.reference, user=self.actor, version=application.version,
            verified=True, notes='Fictional actual manual check', **options)

    def approve(self, application, **options):
        return services.decide_application(application.reference, user=self.actor, version=application.version,
            decision='approved', notes='Fictional authorized membership decision', **options)


class RegistrationHandoffTests(HandoffHelpers, TestCase):
    def make(self, channel='walk_in'):
        # This retained direct-decision path now applies to onsite intake.
        return super().make(channel)

    def setUp(self):
        self.setup_handoff()

    def test_onsite_channels_approve_but_online_cannot_bypass_office_review(self):
        for channel in ('online', 'printed', 'walk_in'):
            intake = self.make(channel)
            original = intake.revisions.get(number=1).data
            application = self.prepare(intake)
            self.assertFalse(Member.objects.filter(application=application).exists())
            self.assertIsNone(application.prpwd_verified)
            if channel == 'online':
                application = self.verify(application)
                with self.assertRaisesMessage(ValidationError, 'Association membership review'):
                    self.approve(application)
                with self.assertRaisesMessage(ValidationError, 'Association membership review'):
                    services.approve_checked_application(application.reference, user=self.actor,
                        version=application.version, verified=True)
                self.assertFalse(Member.objects.filter(application=application).exists())
                continue
            self.approve(self.verify(application))
            intake.refresh_from_db()
            self.assertEqual(intake.membership_application_id, application.pk)
            self.assertEqual(intake.reference[:4], 'AMR-')
            self.assertEqual(intake.revisions.get(number=1).data, original)
            self.assertEqual(Member.objects.filter(application=application).count(), 1)
            self.assertEqual(list(intake.actions.filter(action__startswith='membership_').values_list('action', flat=True)),
                ['membership_handoff', 'membership_verification', 'membership_approved'])

    def test_identical_retry_reuses_link_without_duplicate_native_events_or_files(self):
        intake = self.make()
        form = self.form(intake)
        application = self.prepare(intake, form=form)
        files_before = {str(p) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()}
        self.assertEqual(self.prepare(intake, form=form).pk, application.pk)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 1)
        self.assertEqual(intake.actions.filter(action='membership_handoff').count(), 1)
        self.assertEqual(files_before, {str(p) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()})
        with self.assertRaises(ValidationError):
            self.prepare(intake, form=self.form(intake, dict(form.data.items()), identity_basis='Changed replay'))

    def test_changed_file_retry_is_not_accepted_as_identical(self):
        intake = self.make()
        form = self.form(intake)
        self.prepare(intake, form=form)
        retry = self.form(intake, dict(form.data.items()))
        retry.files[f'document_{self.requirement.pk}'].file.write(b'changed')
        with self.assertRaises(ValidationError):
            self.prepare(intake, form=retry)

    def test_stale_correction_and_missing_onsite_findings_block_handoff(self):
        intake = self.make()
        form = self.form(intake)
        registration.correct_registration(intake.reference, user=self.actor, version=intake.version,
            reason='Fictional corrected address', data=applicant_data() | {'house_number': '99'})
        with self.assertRaises(ValidationError):
            self.prepare(intake, form=form)
        with self.assertRaises(ValidationError):
            self.prepare(intake)
        self.observe(intake, finding_envelope='missing')
        with self.assertRaises(ValidationError):
            self.prepare(intake)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_linked_correction_and_repeat_decision_do_not_create_second_member(self):
        intake = self.make()
        application = self.prepare(intake)
        intake.refresh_from_db()
        with self.assertRaises(ValidationError):
            registration.correct_registration(intake.reference, user=self.actor, version=intake.version,
                reason='Disallowed linked correction', data=applicant_data())
        application = self.verify(application)
        self.approve(application)
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertEqual(Member.objects.count(), 1)

    def test_approval_requires_real_verification_and_rejection_creates_no_member(self):
        application = self.prepare(self.make())
        with self.assertRaises(ValidationError):
            self.approve(application)
        services.decide_application(application.reference, user=self.actor, version=application.version,
            decision='rejected', notes='Fictional reasoned rejection')
        self.assertFalse(Member.objects.exists())

    def test_handoff_audit_failure_rolls_back_link_application_uploads(self):
        intake = self.make()
        files_before = {str(p) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()}
        with patch.object(registration, 'record_action', side_effect=RuntimeError('synthetic audit outage')):
            with self.assertRaises(RuntimeError):
                self.prepare(intake)
        intake.refresh_from_db()
        self.assertIsNone(intake.membership_application_id)
        self.assertEqual(intake.state, 'onsite_review')
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())
        self.assertEqual(files_before, {str(p) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()})

    def test_decision_audit_failure_rolls_back_member_and_both_histories(self):
        intake = self.make()
        application = self.verify(self.prepare(intake))
        counts = (MembershipEvent.objects.count(), RegistrationAction.objects.count())
        with patch.object(registration, 'record_action', side_effect=RuntimeError('synthetic audit outage')):
            with self.assertRaises(RuntimeError):
                self.approve(application)
        application.refresh_from_db()
        self.assertEqual(application.status, 'pending')
        self.assertFalse(Member.objects.exists())
        self.assertEqual(counts, (MembershipEvent.objects.count(), RegistrationAction.objects.count()))

    def test_current_policy_required_on_original_decision_endpoint_and_service(self):
        application = self.verify(self.prepare(self.make()))
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=self.policy | {'handoff_enabled': False}):
            with self.assertRaises(RegistrationUnavailable):
                self.approve(application)
            self.client.force_login(self.actor)
            self.assertEqual(self.client.post(reverse('membership:detail', args=[application.reference]),
                {'action': 'decide', 'decision': 'approved', 'version': application.version, 'notes': 'Fictional'}).status_code, 403)
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=self.policy | {'identity_procedure_reference': 'Changed'}):
            with self.assertRaises(ValidationError):
                self.approve(application)

    def test_permissions_and_csrf_on_prepare_private_detail_and_both_download_routes(self):
        intake = self.make()
        application = self.verify(self.prepare(intake))
        self.approve(application)
        document = application.documents.get()
        urls = [reverse('membership:registration_handoff', args=[intake.reference]),
            reverse('membership:registration_detail', args=[intake.reference]),
            reverse('membership:detail', args=[application.reference]),
            reverse('membership:document', args=[document.pk]),
            reverse('members:document', args=[application.member.pk, document.pk]),
            reverse('documents:review', args=[document.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        viewer = staff('synthetic_legacy_only', 'documents.view_membershipapplicationdocument', 'members.view_member',
            'documents.verify_document')
        viewer.user_permissions.remove(Permission.objects.get(codename='view_registrationintake'))
        self.client.force_login(viewer)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(reverse('membership:list'), {'reference': application.reference}, follow=True), application.full_name)
        self.client.force_login(self.actor)
        response = self.client.get(reverse('membership:document', args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        # Consume through the test client's closing iterator so it releases the
        # file without closing MySQL inside TestCase's enclosing transaction.
        self.assertTrue(b''.join(response.streaming_content))
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.actor)
        self.assertEqual(csrf.post(urls[1], {'action': 'decide_membership'}).status_code, 403)

    def test_permission_revocation_denies_even_previously_cached_decider(self):
        application = self.verify(self.prepare(self.make()))
        self.assertTrue(self.actor.has_perm('membership.decide_membershipapplication'))
        self.actor.user_permissions.remove(Permission.objects.get(codename='decide_membershipapplication'))
        with self.assertRaises(PermissionDenied):
            self.approve(application)
        self.assertFalse(Member.objects.exists())

    def test_public_pause_does_not_strand_accepted_staff_review(self):
        application = self.verify(self.prepare(self.make()))
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=self.policy | {'public_enabled': False,
                'address_attempt_limit': self.policy['address_attempt_limit'] + 1}):
            self.approve(application)
        self.assertEqual(Member.objects.filter(application=application).count(), 1)

    def test_pending_page_uses_existing_review_and_displays_official_member(self):
        intake = self.make()
        application = self.prepare(intake)
        self.client.force_login(self.actor)
        url = reverse('membership:registration_detail', args=[intake.reference])
        self.assertContains(self.client.get(url), 'Approve membership')
        self.assertEqual(self.client.post(url, {'action': 'verify_membership', 'version': 0,
            'verified': 'yes', 'notes': 'Fictional actual check'}).status_code, 302)
        self.assertEqual(self.client.post(url, {'action': 'decide_membership', 'version': 1,
            'decision': 'approved', 'notes': 'Fictional approved acceptance'}).status_code, 302)
        self.assertContains(self.client.get(url), 'Open member record')
        completed = self.client.get(reverse('membership:registration_inbox'), {'tab': 'completed'})
        self.assertContains(completed, 'Approved')
        self.assertContains(completed, intake.reference)

    def test_tampered_applicant_fields_do_not_replace_submitted_profile(self):
        intake = self.make()
        application = self.prepare(intake, form=self.form(intake, first_name='Forged', dependents='999'))
        original = intake.revisions.get(number=1).data
        self.assertEqual(application.first_name, original['first_name'])
        self.assertEqual(application.dependents, original['dependents'])

    def test_handoff_token_cannot_be_replayed_into_unlinked_legacy_submission(self):
        from .forms import ApplicationForm
        from .tests import onsite_profile
        intake = self.make()
        token = self.form(intake).data['submission_token']
        form = ApplicationForm(onsite_profile() | {'submission_token': token},
            MultiValueDict({f'document_{self.requirement.pk}': [upload()]}))
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(ValidationError):
            services.submit_application(form, user=self.actor)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_amr_control_missing_acceptance_future_assessment_and_missing_upload_are_invalid(self):
        intake = self.make()
        template = self.form(intake)
        for changes in ({'control_number': intake.reference}, {'accepted': ''}, {'assessed_on': '2999-01-01'}):
            form = HandoffForm(dict(template.data.items()) | changes, template.files, intake=intake, policy=self.policy)
            self.assertFalse(form.is_valid())
        self.assertFalse(HandoffForm(dict(template.data.items()), intake=intake, policy=self.policy).is_valid())

    def test_duplicate_member_and_duplicate_pending_number_are_blocked(self):
        intake = self.make()
        application = self.prepare(intake)
        other = self.make('printed')
        with self.assertRaises(ValidationError):
            self.prepare(other, form=self.form(other, control_number=application.control_number))
        self.approve(self.verify(application))
        with self.assertRaises(ValidationError):
            self.prepare(other, form=self.form(other, control_number=application.control_number))


class RegistrationHandoffConcurrencyTests(HandoffHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_handoff()

    def test_concurrent_identical_handoffs_and_decisions_create_one_member(self):
        intake = self.make('walk_in')
        data = dict(self.form(intake).data.items())
        def prepare():
            close_old_connections()
            try:
                current = RegistrationIntake.objects.get(pk=intake.pk)
                return self.prepare(current, form=self.form(current, data)).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: prepare(), range(2)))
        self.assertEqual(results[0], results[1])
        application = self.verify(MembershipApplication.objects.get(pk=results[0]))
        def approve():
            close_old_connections()
            try:
                try:
                    return self.approve(application).status
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: approve(), range(2)))
        self.assertEqual(sorted(results), ['approved', 'stale'])
        self.assertEqual(Member.objects.count(), 1)


from ewaf.test_source_writers import SourceHelpers


class RegistrationHandoffEnlistedTests(HandoffHelpers, SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        self.setup_handoff(actor=self.officer)
        self.register()

    def test_existing_top_level_writer_keeps_zero_program_scope_and_native_audits(self):
        from ewaf.generation_models import SourceMutationBatch
        from ewaf import generation_services
        intake = self.make('walk_in')
        form = self.form(intake)
        application = self.prepare(intake, form=form, source_expected={})
        self.assertEqual(self.prepare(intake, form=form, source_expected={}).pk, application.pk)
        self.approve(self.verify(application, source_expected={}), source_expected={})
        rows = SourceMutationBatch.objects.filter(source_kind='membership')
        self.assertEqual(rows.count(), 3)
        for row in rows:
            self.assertEqual(row.scope_count, 0)
            self.assertEqual(len(row.source_audits), 1)
            generation_services._validate_batch(row)
        self.assert_transition(1)

    def test_outer_writer_failure_rolls_back_registration_link_and_files(self):
        from ewaf import generation_services
        intake = self.make()
        before = MembershipApplication.objects.count()
        files = {str(p) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()}
        with patch.object(generation_services, '_invalidate', side_effect=ValidationError('Synthetic late failure')):
            with self.assertRaises(ValidationError):
                self.prepare(intake, source_expected={})
        intake.refresh_from_db()
        self.assertIsNone(intake.membership_application_id)
        self.assertEqual(MembershipApplication.objects.count(), before)
        self.assertEqual(files, {str(p) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()})
