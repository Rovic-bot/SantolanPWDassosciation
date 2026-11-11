"""Synthetic contracts only. These parameter values are NOT Association policy."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from unittest.mock import patch
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections, transaction, IntegrityError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from members.models import Member
from membership.models import MembershipApplication, SubmissionWindow
from membership.tests import grant, profile
from .registration_models import (RegistrationIntake, RegistrationRevision, RegistrationAttachment,
    RegistrationSubmissionContext, RegistrationAction, registration_write)
from .registration_policy import available, policy_for, RegistrationUnavailable
from . import registration_services as services


def synthetic_policy(**changes):
    return {'version': 'SYNTHETIC-NOT-POLICY-v1', 'form_version': 'SYNTHETIC-FORM-v1',
        'field_contract_reference': 'FICTIONAL FIELD REVIEW', 'authority_reference': 'FICTIONAL COLLECTION AUTHORITY',
        'privacy_version': 'FICTIONAL-v1', 'privacy_notice': 'Synthetic test records only; no real applicants.',
        'retention_reference': 'FICTIONAL TEST RETENTION ONLY', 'staff_assignments_reference': 'FICTIONAL TEST STAFF',
        'upload_policy_reference': 'FICTIONAL OPTIONAL UPLOADS',
        'onsite_instructions': 'Synthetic demonstration: bring the five Association requirements to the Help Desk.',
        'security_review_reference': 'FICTIONAL TEST SECURITY PARAMETERS',
        'public_enabled': True, 'staff_enabled': True, 'onsite_enabled': False, 'correction_enabled': True,
        'correction_procedure_reference': 'FICTIONAL ASSISTED CORRECTION PROCEDURE',
        'context_seconds': 600, 'attempt_window_seconds': 60, 'address_attempt_limit': 1000,
        'session_attempt_limit': 1000, 'reference_attempt_limit': 3,
        'file_max_bytes': 1048576, 'total_max_bytes': 2097152, 'body_max_bytes': 3145728, 'file_count_limit': 3,
        'upload_slots': ['photo_2x2', 'civil_document', 'voter_certificate'],
        'onsite_procedure_reference': 'FICTIONAL ONSITE METHOD', 'onsite_methods': ['Synthetic observed original'], **changes}


def submitted(**changes):
    return {'full_name': 'Synthetic Applicant', 'birthdate': '1990-01-02',
        'address': 'Synthetic address only', 'contact_number': '', 'acknowledgement': 'on', **changes}


def upload():
    return SimpleUploadedFile('synthetic-proof.pdf', b'%PDF-1.4\nSynthetic evidence only\n', content_type='application/pdf')


def staff(username='synthetic_registration_staff', *permissions):
    actor = get_user_model().objects.create_user(username, is_staff=True)
    grant(actor, 'accounts.access_dashboard', 'membership.view_membershipapplication',
        'membership.view_registrationintake', *permissions)
    return actor


class PendingRegistrationTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory(prefix='phase2b-synthetic-')
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name,
            ASSOCIATION_REGISTRATION_POLICY=synthetic_policy())
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.actor = staff('synthetic_full_staff', 'membership.encode_registrationintake',
            'membership.review_registrationintake', 'membership.correct_registrationintake',
            'membership.onsite_registrationintake', 'membership.view_registration_documents')
        self.viewer = staff('synthetic_view_staff')
        self.binding = services.binding_for('synthetic-browser-session')
        self.apply_url = reverse('membership:registration_apply')
        self.receipt_url = reverse('membership:registration_receipt')

    def make(self, *, data=None, files=None):
        context = services.issue_context(self.binding)
        intake = services.submit_registration(context.pk, self.binding, data or submitted(), files)
        return intake, context

    def detail_url(self, intake):
        return reverse('membership:registration_detail', args=[intake.reference])

    def browser_submit(self, client=None):
        client = client or self.client
        response = client.get(self.apply_url)
        self.assertEqual(response.status_code, 200)
        context = response.context['context_id']
        response = client.post(self.apply_url, {**submitted(), 'context_id': context})
        self.assertRedirects(response, self.receipt_url, fetch_redirect_response=False)
        return RegistrationIntake.objects.get(context_id=context), context

    def test_missing_configuration_keeps_public_and_new_staff_routes_unavailable_without_new_table_query(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=None):
            with patch.object(RegistrationIntake.objects, 'filter', side_effect=AssertionError('Unexpected table access')):
                self.assertEqual(self.client.get(self.apply_url).status_code, 503)
                self.assertEqual(self.client.post(self.apply_url, submitted()).status_code, 503)
                self.assertEqual(self.client.get(self.receipt_url).status_code, 503)
            self.client.force_login(self.actor)
            self.assertEqual(self.client.get(reverse('membership:registration_inbox')).status_code, 503)

    def test_every_required_security_and_institutional_parameter_is_fail_closed(self):
        keys = ['context_seconds', 'address_attempt_limit', 'session_attempt_limit', 'attempt_window_seconds',
                'reference_attempt_limit', 'file_max_bytes', 'total_max_bytes', 'body_max_bytes', 'file_count_limit',
                'privacy_notice', 'retention_reference', 'staff_assignments_reference', 'authority_reference',
                'field_contract_reference', 'upload_policy_reference', 'security_review_reference']
        for key in keys:
            with self.subTest(key=key), override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(**{key: None})):
                self.assertFalse(available('public'))
                with self.assertRaises(RegistrationUnavailable):
                    services.issue_context(self.binding)
        self.assertEqual(RegistrationSubmissionContext.objects.count(), 0)

    def test_guidance_reflects_gate_with_resources_appended_to_public_navigation(self):
        response = self.client.get(reverse('core:membership'))
        self.assertContains(response, 'id="online-registration-heading"', count=1)
        self.assertContains(response, 'Start online membership registration', count=1)
        self.assertContains(response, f'href="{self.apply_url}"', count=1)
        self.assertContains(response, 'Online submission is not membership approval or PWD ID issuance.')
        self.assertContains(response, 'Bring your reference number and PWD ID Card.')
        self.assertContains(response, 'Visit the Association Help Desk to verify your information and complete the membership review.')
        self.assertNotContains(response, 'Membership applications are not accepted online.')
        self.assertEqual(self.client.get(self.apply_url).status_code, 200)
        self.assertEqual(len(response.context['public_navigation']), 7)
        self.assertEqual(response.context['public_navigation'][-1], ('core:resources', 'Resources & Help'))
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=None):
            response = self.client.get(reverse('core:membership'))
            self.assertContains(response, 'id="online-registration-heading"', count=1)
            self.assertContains(response, 'Online membership registration is currently unavailable.')
            self.assertNotContains(response, 'Start online membership registration')
            self.assertContains(response, 'Download the form or visit the Help Desk.')
            self.assertNotContains(response, reverse('membership:registration_apply'))
        self.assertEqual(RegistrationIntake.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)

    def test_pending_submission_is_separate_and_has_unique_nonidentifying_reference(self):
        with patch('membership.services.submit_application', side_effect=AssertionError('No membership handoff')):
            first, _ = self.make()
            second, _ = self.make(data=submitted(full_name='Another Synthetic Person'))
        self.assertRegex(first.reference, r'^AMR-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
        self.assertNotEqual(first.reference, second.reference)
        self.assertEqual(first.state, 'received')
        self.assertEqual(first.revisions.get().data['contact_number'], '')
        self.assertEqual(first.actions.get().action, 'received')
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(Member.objects.count(), 0)

    def test_identical_retry_returns_same_intake_and_does_not_add_history(self):
        intake, context = self.make()
        again = services.submit_registration(context.pk, self.binding, submitted())
        self.assertEqual(again.pk, intake.pk)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 1)
        self.assertEqual(RegistrationAction.objects.count(), 1)

    def test_changed_retry_conflicts_and_other_session_cannot_replay(self):
        intake, context = self.make()
        with self.assertRaises(ValidationError):
            services.submit_registration(context.pk, self.binding, submitted(address='Different synthetic address'))
        with self.assertRaises(PermissionDenied):
            services.submit_registration(context.pk, services.binding_for('another-browser'), submitted())
        self.assertEqual(intake.revisions.get().data, submitted() | {'acknowledgement': True})

    def test_identical_upload_retry_does_not_store_second_file(self):
        data = submitted(civil_alternative='birth')
        intake, context = self.make(data=data, files=MultiValueDict({'civil_document': [upload()]}))
        again = services.submit_registration(context.pk, self.binding, data, MultiValueDict({'civil_document': [upload()]}))
        self.assertEqual(again.pk, intake.pk)
        self.assertEqual(RegistrationAttachment.objects.count(), 1)
        self.assertEqual(len([p for p in Path(self.media.name).rglob('*') if p.is_file()]), 1)

    def test_reference_collision_is_retried_without_altering_old_reference(self):
        intake, _ = self.make()
        with patch('membership.registration_services.uuid4', side_effect=[UUID(intake.reference[4:]), uuid4()]):
            other, _ = self.make()
        self.assertNotEqual(intake.reference, other.reference)
        intake.refresh_from_db()
        self.assertEqual(RegistrationIntake.objects.count(), 2)

    def test_reference_collision_budget_exhaustion_never_accepts_request(self):
        intake, _ = self.make()
        with patch('membership.registration_services.uuid4', return_value=UUID(intake.reference[4:])):
            with self.assertRaises(ValidationError):
                self.make()
        self.assertEqual(RegistrationIntake.objects.count(), 1)

    def test_shared_name_or_contact_does_not_automatically_merge_people(self):
        first, _ = self.make(data=submitted(contact_number='SYNTHETIC-CONTACT'))
        second, _ = self.make(data=submitted(contact_number='SYNTHETIC-CONTACT'))
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Member.objects.count(), 0)

    def test_unknown_fields_files_and_unapproved_alternatives_are_rejected(self):
        for extra in ({'control_number': 'FAKE'}, {'category': 'pdao'}, {'state': 'approved'}, {'monthly_income': '100'}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                self.make(data=submitted(**extra))
        for slot in ('envelope', 'national_id', 'photo_1x1'):
            with self.subTest(slot=slot), self.assertRaises(ValidationError):
                self.make(files=MultiValueDict({slot: [upload()]}))
        self.assertEqual(RegistrationIntake.objects.count(), 0)

    def test_malformed_empty_oversize_and_repeated_uploads_are_rejected(self):
        invalid = [SimpleUploadedFile('proof.pdf', b'not a pdf', content_type='application/pdf'),
            SimpleUploadedFile('proof.pdf', b'', content_type='application/pdf'),
            SimpleUploadedFile('proof.pdf', b'%PDF-' + b'x' * 1048576, content_type='application/pdf'),
            SimpleUploadedFile('proof.exe', b'%PDF-1.4', content_type='application/pdf')]
        for file in invalid:
            with self.subTest(name=file.name, size=file.size), self.assertRaises(ValidationError):
                self.make(files=MultiValueDict({'voter_certificate': [file]}))
        with self.assertRaises(ValidationError):
            self.make(files=MultiValueDict({'voter_certificate': [upload(), upload()]}))
        self.assertEqual(RegistrationAttachment.objects.count(), 0)

    def test_civil_document_requires_exactly_one_permitted_alternative(self):
        with self.assertRaises(ValidationError):
            self.make(files=MultiValueDict({'civil_document': [upload()]}))
        for choice in ('birth', 'marriage'):
            intake, _ = self.make(data=submitted(civil_alternative=choice), files=MultiValueDict({'civil_document': [upload()]}))
            self.assertEqual(intake.revisions.get().attachments.get().alternative, choice)

    def test_audit_failure_rolls_back_record_and_private_upload(self):
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        self.assertEqual(RegistrationIntake.objects.count(), 0)
        self.assertEqual(RegistrationAttachment.objects.count(), 0)
        self.assertEqual([p for p in Path(self.media.name).rglob('*') if p.is_file()], [])

    def test_storage_failure_never_returns_receipt_or_pending_record(self):
        storage = RegistrationAttachment._meta.get_field('file').storage
        with patch.object(storage, 'save', side_effect=OSError('synthetic storage failure')):
            with self.assertRaises(OSError):
                self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        self.assertEqual(RegistrationIntake.objects.count(), 0)

    def test_cleanup_failure_reports_opaque_orphan_without_acceptance(self):
        storage = RegistrationAttachment._meta.get_field('file').storage
        with patch.object(storage, 'delete', side_effect=OSError('synthetic cleanup failure')), \
             patch('membership.registration_services.record_action', side_effect=RuntimeError('audit unavailable')):
            with self.assertLogs('membership.registration_services', level='ERROR') as logs:
                with self.assertRaises(RuntimeError):
                    self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        self.assertNotIn('Synthetic Applicant', str(logs.output))
        self.assertNotIn('synthetic-proof.pdf', str(logs.output))
        self.assertEqual(RegistrationIntake.objects.count(), 0)

    def test_unavailable_receipt_redirects_to_fresh_public_membership_page(self):
        from .registration_views import CONTEXT_KEY
        target = reverse('core:membership')
        for context_id in (None, 'malformed-context', str(uuid4())):
            browser = Client()
            if context_id is not None:
                session = browser.session
                session[CONTEXT_KEY] = context_id
                session.save()
            response = browser.get(self.receipt_url, {'next': 'https://example.invalid/'})
            self.assertRedirects(response, target)
            self.assertIn('no-store', response['Cache-Control'])
            fresh = browser.get(target)
            self.assertEqual(fresh.status_code, 200)
            self.assertIn('no-store', fresh['Cache-Control'])
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_expired_receipt_redirect_keeps_saved_submission_private(self):
        intake, context_id = self.browser_submit()
        context = RegistrationSubmissionContext.objects.get(pk=context_id)
        with patch('membership.registration_services.timezone.now', return_value=context.expires_at + timedelta(seconds=1)):
            response = self.client.get(self.receipt_url)
        self.assertRedirects(response, reverse('core:membership'), fetch_redirect_response=False)
        self.assertNotContains(response, intake.reference, status_code=302)
        self.assertTrue(RegistrationIntake.objects.filter(pk=intake.pk).exists())
        self.assertFalse(Member.objects.exists())

    def test_browser_receipt_uses_session_and_projects_original_form_only(self):
        intake, _ = self.browser_submit()
        services.correct_registration(intake.reference, user=self.actor, version=0,
            reason='PRIVATE synthetic correction reason', data=submitted(full_name='Changed Synthetic Name'))
        response = self.client.get(self.receipt_url, {'reference': intake.reference})
        self.assertContains(response, 'Synthetic Applicant')
        self.assertNotContains(response, 'Changed Synthetic Name')
        self.assertNotContains(response, 'PRIVATE synthetic correction reason')
        self.assertNotContains(response, 'under_review')
        self.assertIn('no-store', response['Cache-Control'])
        other = Client()
        self.assertRedirects(other.get(self.receipt_url, {'reference': intake.reference}), reverse('core:membership'), fetch_redirect_response=False)
        self.assertEqual(other.get(f'/membership/registration/receipt/{intake.reference}/').status_code, 404)

    def test_expired_and_finished_contexts_cannot_reopen_forms(self):
        intake, context = self.make()
        with patch('membership.registration_services.timezone.now', return_value=context.expires_at + timedelta(seconds=1)):
            with self.assertRaises(PermissionDenied):
                services.receipt_for(context.pk, self.binding)
        services.revoke_context(context.pk, self.binding)
        with self.assertRaises(PermissionDenied):
            services.receipt_for(context.pk, self.binding)
        self.assertTrue(RegistrationIntake.objects.filter(pk=intake.pk).exists())

    def test_finish_button_revokes_only_form_access(self):
        intake, _ = self.browser_submit()
        response = self.client.post(reverse('membership:registration_finish'))
        self.assertContains(response, 'Registration submitted')
        self.assertContains(response, intake.reference)
        self.assertContains(response, 'Barangay Santolan office')
        self.assertContains(response, 'Bring your PWD ID Card')
        self.assertRedirects(self.client.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)
        self.assertTrue(RegistrationIntake.objects.filter(pk=intake.pk).exists())

    def test_csrf_is_enforced_inside_public_upload_wrapper(self):
        browser = Client(enforce_csrf_checks=True)
        response = browser.get(self.apply_url)
        data = {**submitted(), 'context_id': response.context['context_id']}
        self.assertEqual(browser.post(self.apply_url, data).status_code, 403)
        token = browser.cookies['csrftoken'].value
        self.assertEqual(browser.post(self.apply_url, {**data, 'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertEqual(browser.post(reverse('membership:registration_finish')).status_code, 403)

    def test_attempt_budgets_are_explicit_and_bounded(self):
        policy = synthetic_policy(address_attempt_limit=1, session_attempt_limit=1)
        self.assertTrue(services.reserve_attempt(self.binding, '192.0.2.1', policy))
        self.assertFalse(services.reserve_attempt(self.binding, '192.0.2.1', policy))
        self.assertTrue(all(row.attempts == 1 for row in SubmissionWindow.objects.all()))
        self.assertFalse(any('192.0.2.1' in row.key for row in SubmissionWindow.objects.all()))

    def test_configuration_change_invalidates_old_submission_context(self):
        context = services.issue_context(self.binding)
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(form_version='SYNTHETIC-v2')):
            with self.assertRaises(PermissionDenied):
                services.submit_registration(context.pk, self.binding, submitted())

    def test_staff_exact_reference_retrieval_and_permission_denial(self):
        intake, _ = self.make()
        url = reverse('membership:registration_inbox')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.viewer)
        response = self.client.get(url, {'reference': intake.reference.upper()})
        self.assertContains(response, intake.reference)
        self.assertContains(self.client.get(self.detail_url(intake)), 'Synthetic Applicant')
        self.assertContains(self.client.get(url, {'reference': 'AMR-'}), 'No accessible registration matches')
        self.assertNotContains(self.client.get(url, {'reference': 'AMR-'}), 'Synthetic Applicant')
        legacy = get_user_model().objects.create_user('synthetic_legacy_only', is_staff=True)
        grant(legacy, 'accounts.access_dashboard', 'membership.view_membershipapplication')
        self.client.force_login(legacy)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(self.detail_url(intake)).status_code, 403)

    def test_private_documents_require_separate_permission_and_audit(self):
        intake, _ = self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        file = intake.revisions.get().attachments.get()
        url = reverse('membership:registration_document', args=[file.pk])
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.actor)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertTrue(intake.actions.filter(action='private_document_downloaded').exists())
        self.assertEqual(self.client.get('/media/' + file.file.name).status_code, 404)

    def test_document_audit_failure_blocks_delivery(self):
        intake, _ = self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        self.client.force_login(self.actor)
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.get(reverse('membership:registration_document', args=[intake.revisions.get().attachments.get().pk]))

    def test_staff_completed_form_excludes_private_history_and_requires_permission(self):
        intake, _ = self.make()
        services.review_registration(intake.reference, user=self.actor, version=0, action='begin_review',
            reason='PRIVATE REVIEW NOT FOR PRINTED FORM')
        url = reverse('membership:registration_form', args=[intake.reference, 1])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.viewer)
        response = self.client.get(url)
        self.assertContains(response, 'Synthetic Applicant')
        self.assertNotContains(response, 'PRIVATE REVIEW NOT FOR PRINTED FORM')
        self.assertNotContains(response, 'Private review history')
        self.assertIn('no-store', response['Cache-Control'])

    def test_revoked_permissions_are_rechecked_even_with_cached_user(self):
        intake, _ = self.make()
        self.assertTrue(self.actor.has_perm('membership.review_registrationintake'))
        self.actor.user_permissions.remove(Permission.objects.get(codename='review_registrationintake'))
        with self.assertRaises(PermissionDenied):
            services.review_registration(intake.reference, user=self.actor, version=0, action='begin_review', reason='Synthetic review')
        intake.refresh_from_db()
        self.assertEqual(intake.state, 'received')

    def test_state_transition_stale_write_and_audit_rollback(self):
        intake, _ = self.make()
        intake = services.review_registration(intake.reference, user=self.actor, version=0, action='begin_review', reason='Synthetic review')
        self.assertEqual(intake.state, 'under_review')
        with self.assertRaises(ValidationError):
            services.review_registration(intake.reference, user=self.actor, version=0, action='request_information', reason='Stale')
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                services.review_registration(intake.reference, user=self.actor, version=1, action='request_information', reason='Synthetic need')
        intake.refresh_from_db()
        self.assertEqual(intake.version, 1)
        self.assertEqual(intake.state, 'under_review')

    def test_correction_preserves_original_and_invalidates_readiness(self):
        intake, _ = self.make(files=MultiValueDict({'voter_certificate': [upload()]}))
        intake = services.review_registration(intake.reference, user=self.actor, version=0, action='begin_review', reason='Synthetic review')
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(onsite_enabled=True)):
            intake = services.review_registration(intake.reference, user=self.actor, version=1, action='ready_for_onsite', reason='Synthetic readiness')
        intake = services.correct_registration(intake.reference, user=self.actor, version=2, reason='Synthetic correction',
            data=submitted(address='Updated synthetic address'))
        self.assertEqual(intake.state, 'under_review')
        self.assertEqual(intake.revisions.get(number=1).data['address'], 'Synthetic address only')
        self.assertEqual(services.active_attachments(intake.revisions.get(number=2)).count(), 1)
        self.assertEqual(intake.revisions.count(), 2)

    def test_onsite_actions_are_gated_and_only_record_observations(self):
        intake, _ = self.make()
        intake = services.review_registration(intake.reference, user=self.actor, version=0, action='begin_review', reason='Synthetic review')
        with self.assertRaises(RegistrationUnavailable):
            services.review_registration(intake.reference, user=self.actor, version=1, action='ready_for_onsite', reason='Not authorized')
        from .registration_forms import OnsiteForm
        data = {'version': 1, 'reason': 'Synthetic observed items', 'civil_alternative': 'birth'}
        for key in OnsiteForm.keys:
            data[f'finding_{key}'] = 'sighted'
            data[f'method_{key}'] = 'Synthetic observed original'
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(onsite_enabled=True)):
            intake = services.record_onsite(intake.reference, user=self.actor, data=data)
        self.assertEqual(intake.state, 'onsite_review')
        self.assertEqual(intake.actions.latest('pk').payload['findings']['envelope']['finding'], 'sighted')
        self.assertEqual(Member.objects.count(), 0)
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_corrections_require_their_own_approved_procedure(self):
        intake, _ = self.make()
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(correction_procedure_reference='')):
            with self.assertRaises(RegistrationUnavailable):
                services.correct_registration(intake.reference, user=self.actor, version=0,
                    reason='Synthetic correction', data=submitted())
            self.client.force_login(self.actor)
            self.assertEqual(self.client.get(reverse('membership:registration_correct', args=[intake.reference])).status_code, 503)
        self.assertEqual(intake.revisions.count(), 1)

    def test_printed_and_walkin_capture_use_same_pending_form_without_official_members(self):
        for channel in ('printed', 'walk_in'):
            context = services.issue_context(self.binding, channel=channel, user=self.actor)
            intake = services.submit_registration(context.pk, self.binding, submitted(), channel=channel, user=self.actor)
            self.assertEqual(intake.channel, channel)
            self.assertEqual(intake.actions.get().actor_id, self.actor.pk)
            with self.assertRaises(PermissionDenied):
                services.submit_registration(context.pk, self.binding, submitted(), channel=channel, user=self.viewer)
        self.assertEqual(Member.objects.count(), 0)

    def test_online_print_presentation_reuses_original_record(self):
        intake, _ = self.make()
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(onsite_enabled=True)):
            result = services.review_registration(intake.reference, user=self.actor, version=0,
                action='presented_printout', reason='Synthetic identity process followed for presented printout')
        self.assertEqual(result.pk, intake.pk)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(result.channel, 'online')

    def test_handoff_is_unavailable_and_database_prohibits_linking(self):
        intake, _ = self.make()
        with self.assertRaises(RegistrationUnavailable):
            services.handoff_registration(intake.reference, user=self.actor)
        existing = MembershipApplication.objects.create(**profile(), submission_key=uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic(), registration_write():
            intake.membership_application = existing
            intake.save()
        self.assertEqual(Member.objects.count(), 0)

    def test_history_and_direct_model_mutation_are_protected(self):
        intake, _ = self.make()
        with self.assertRaises(PermissionDenied):
            intake.save()
        with self.assertRaises(PermissionDenied):
            RegistrationIntake.objects.filter(pk=intake.pk).update(state='onsite_review')
        with self.assertRaises(PermissionDenied), registration_write():
            revision = intake.revisions.get()
            revision.data = submitted()
            revision.save()
        with self.assertRaises(PermissionDenied):
            intake.actions.all().delete()

    def test_pdao_print_preparation_does_not_enable_tracking_recovery_or_public_handoff(self):
        self.assertEqual(self.client.get('/membership/registration/pdao/').status_code, 200)
        for route in ('/membership/registration/tracking/',
                      '/membership/registration/recovery/', '/membership/registration/handoff/'):
            self.assertEqual(self.client.get(route).status_code, 404)
        self.assertEqual(Member.objects.count(), 0)


class RegistrationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.override = override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy())
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.binding = services.binding_for('synthetic-concurrent-session')
        self.context = services.issue_context(self.binding)

    def test_concurrent_identical_submissions_accept_exactly_one_record(self):
        barrier = Barrier(2)
        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return str(services.submit_registration(self.context.pk, self.binding, submitted()).pk)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationAction.objects.count(), 1)

    def test_concurrent_review_keeps_one_current_version(self):
        intake = services.submit_registration(self.context.pk, self.binding, submitted())
        actor = staff('synthetic_concurrent_staff', 'membership.review_registrationintake')
        barrier = Barrier(2)
        def attempt():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    services.review_registration(intake.reference, user=actor, version=0,
                        action='begin_review', reason='Synthetic concurrent review')
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ['saved', 'stale'])
        intake.refresh_from_db()
        self.assertEqual(intake.version, 1)

    def test_permission_revocation_during_review_rolls_back_before_audit(self):
        intake = services.submit_registration(self.context.pk, self.binding, submitted())
        actor = staff('synthetic_revoke_during_review', 'membership.review_registrationintake')
        before_audit, continue_review = Event(), Event()
        original = services.record_action

        def paused_audit(*args, **kwargs):
            before_audit.set()
            if not continue_review.wait(timeout=10):
                raise RuntimeError('Synthetic concurrency coordination timed out.')
            return original(*args, **kwargs)

        def attempt():
            close_old_connections()
            try:
                try:
                    services.review_registration(intake.reference, user=actor, version=0,
                        action='begin_review', reason='Synthetic pending revocation')
                    return 'unexpected save'
                except PermissionDenied:
                    return 'denied'
            finally:
                connections.close_all()

        with patch('membership.registration_services.record_action', side_effect=paused_audit):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(attempt)
                try:
                    self.assertTrue(before_audit.wait(timeout=10))
                    actor.user_permissions.remove(Permission.objects.get(codename='review_registrationintake'))
                finally:
                    continue_review.set()
                self.assertEqual(future.result(timeout=15), 'denied')
        intake.refresh_from_db()
        self.assertEqual(intake.version, 0)
        self.assertEqual(intake.state, 'received')
        self.assertEqual(intake.actions.count(), 1)
