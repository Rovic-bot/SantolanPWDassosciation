from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from documents.models import DocumentType, MembershipApplicationDocument, MembershipDocumentRequirement
from members.models import Member, DisabilityType
from .forms import ApplicationForm
from .models import MembershipApplication, MembershipEvent, MembershipSettings, SubmissionWindow
from .services import decide_application, record_verification, submit_application


def pdf():
    return SimpleUploadedFile('proof.pdf', b'%PDF-1.4\nTest fixture only\n%%EOF', content_type='application/pdf')


def profile():
    return {'full_name': 'Sample Applicant', 'birthdate': '1995-01-02',
            'address': 'Test address, Santolan', 'contact_number': '09170000000', 'email': '',
            'control_number': ' test-001 ', 'disability_information': 'Test disability description',
            'employment_information': 'Test employment description', 'monthly_income': '0.00', 'dependents': '0'}


def onsite_profile():
    classification = DisabilityType.objects.get_or_create(name='Visual Disability')[0]
    return {**profile(), 'municipality': 'Pasig City', 'barangay': 'Santolan', 'house_number': '12',
            'street': 'Test Street', 'purok_zone': 'Zone 1', 'first_name': 'Sample',
            'middle_name': '', 'no_middle_name': True, 'last_name': 'Applicant', 'suffix': '',
            'sex': 'female', 'civil_status': 'single', 'disability_types': [classification.pk],
            'disability_cause': 'congenital', 'disability_visibility': 'non_apparent',
            'education': 'college', 'employment_status': 'student', 'income_category': 'income_0_5000'}


def grant(user, *codenames):
    for codename in codenames:
        app, name = codename.split('.')
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=name))


class MembershipTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.policy, _ = MembershipSettings.objects.update_or_create(pk=1, defaults={
            'registration_open': True, 'prpwd_url': 'https://registry.example.test/verify'})
        self.requirement = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Test document'))
        self.admin = get_user_model().objects.create_superuser('review_admin')
        self.viewer = get_user_model().objects.create_user('viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'membership.view_membershipapplication')

    def data(self, **changes):
        result = {**onsite_profile(), 'submission_token': ApplicationForm().initial['submission_token']}
        if 'full_name' in changes:
            changes['first_name'] = changes.pop('full_name')
        result.update(changes)
        return result

    def form(self, **changes):
        return ApplicationForm(self.data(**changes), MultiValueDict({f'document_{self.requirement.pk}': [pdf()]}))

    def application(self, **changes):
        form = self.form(**changes)
        self.assertTrue(form.is_valid(), form.errors)
        return submit_application(form, user=self.admin)

    def verify(self, application, **changes):
        args = {'user': self.admin, 'version': application.version, 'verified': True, 'notes': 'Checked manually.'}
        args.update(changes)
        return record_verification(application.reference, **args)

    def decide(self, application, **changes):
        args = {'user': self.admin, 'version': application.version, 'decision': 'approved', 'notes': 'Reviewed.'}
        args.update(changes)
        return decide_application(application.reference, **args)

    def test_public_registration_is_disabled_regardless_of_legacy_setting(self):
        for opened in (True, False):
            self.policy.registration_open = opened
            self.policy.save()
            self.assertEqual(self.client.post(reverse('core:membership'), self.data()).status_code, 405)
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_admin_encoding_creates_pending_record_without_forged_approval(self):
        self.client.force_login(self.admin)
        data = self.data(status='approved', prpwd_verified='true', decided_by=self.admin.pk)
        data[f'document_{self.requirement.pk}'] = pdf()
        response = self.client.post(reverse('membership:encode'), data)
        application = MembershipApplication.objects.get()
        self.assertRedirects(response, reverse('membership:detail', args=[application.reference]))
        self.assertEqual(application.status, 'pending')
        self.assertIsNone(application.prpwd_verified)
        self.assertEqual(application.control_number, 'TEST-001')
        self.assertEqual(Member.objects.count(), 0)
        self.assertEqual(application.events.get().action, 'onsite_encoded')
        self.assertEqual(application.events.get().actor, self.admin)
        self.assertEqual(application.documents.count(), 1)

    def test_guidelines_show_confirmed_requirements_without_publishing_upload_configuration(self):
        self.requirement.instructions = 'Bring the original for onsite review.'
        self.requirement.save()
        optional = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Optional supporting evidence'),
            is_required=False)
        MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Retired requirement'), is_active=False)
        for opened in (True, False):
            with self.subTest(legacy_flag=opened):
                self.policy.registration_open = opened
                self.policy.save()
                response = self.client.get(reverse('core:membership'))
                self.assertContains(response, 'Membership &amp; PWD ID')
                self.assertContains(response, 'Birth Certificate OR Marriage Certificate')
                self.assertContains(response, 'One (1) long brown envelope')
                self.assertNotContains(response, self.requirement.instructions)
                self.assertNotContains(response, str(optional))
                self.assertNotContains(response, 'Retired requirement')
                self.assertNotContains(response, 'type="file"')
                self.assertNotContains(response, 'name="submission_token"')
                self.assertIn('no-store', response['Cache-Control'])
                self.assertEqual(self.client.post(reverse('core:membership'), self.data()).status_code, 405)
        self.assertFalse(MembershipApplication.objects.exists())
        self.requirement.refresh_from_db()
        self.assertEqual(self.requirement.instructions, 'Bring the original for onsite review.')
        self.assertTrue(MembershipDocumentRequirement.objects.filter(pk=optional.pk).exists())

    def test_onsite_encoding_requires_separate_permission_for_get_post_and_service(self):
        route = reverse('membership:encode')
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(route).status_code, 302)
        self.client.force_login(self.viewer)
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(route).status_code, 403)
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(PermissionDenied):
            submit_application(form, user=self.viewer)
        grant(self.viewer, 'membership.encode_membershipapplication')
        self.viewer = get_user_model().objects.get(pk=self.viewer.pk)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(route).status_code, 200)
        application = submit_application(form, user=self.viewer)
        self.assertEqual(application.events.get().actor, self.viewer)
        self.assertFalse(Member.objects.exists())
        for service in (self.verify, self.decide):
            with self.assertRaises(PermissionDenied):
                service(application, user=self.viewer)

    def test_ordinary_staff_complete_onsite_review_with_legacy_public_intake_closed(self):
        self.policy.registration_open = False
        self.policy.save()
        grant(self.viewer, 'membership.encode_membershipapplication',
              'membership.verify_membershipapplication', 'membership.decide_membershipapplication')
        self.viewer = get_user_model().objects.get(pk=self.viewer.pk)
        self.client.force_login(self.viewer)
        account_count = get_user_model().objects.count()
        data = self.data()
        data[f'document_{self.requirement.pk}'] = pdf()
        response = self.client.post(reverse('membership:encode'), data)
        application = MembershipApplication.objects.get()
        detail = reverse('membership:detail', args=[application.reference])
        self.assertRedirects(response, detail)
        self.assertEqual(application.status, 'pending')
        self.assertFalse(Member.objects.exists())
        self.assertContains(self.client.post(detail, {'action': 'decide', 'version': 0,
            'decision': 'approved', 'notes': 'Reviewed supplied documents.'}),
            'Approval requires a recorded successful manual PRPWD verification.')
        self.assertRedirects(self.client.post(detail, {'action': 'verify', 'version': 0,
            'verified': 'yes', 'notes': 'Synthetic manual verification.'}), detail)
        self.assertContains(self.client.post(detail, {'action': 'decide', 'version': 0,
            'decision': 'approved', 'notes': 'Stale decision.'}), 'Another review changed')
        self.assertRedirects(self.client.post(detail, {'action': 'decide', 'version': 1,
            'decision': 'approved', 'notes': 'Documents and verification reviewed.'}), detail)
        application.refresh_from_db()
        self.assertEqual(Member.objects.get().application, application)
        self.assertEqual(application.prpwd_verified_by, self.viewer)
        self.assertEqual(application.decided_by, self.viewer)
        self.assertEqual(application.documents.get().label, 'Test document')
        self.assertEqual(list(application.events.values_list('action', flat=True)),
                         ['onsite_encoded', 'prpwd_verified', 'approved'])
        self.assertEqual(get_user_model().objects.count(), account_count)

    def test_retired_public_receipt_redirects_to_guidelines_and_never_accepts_posts(self):
        route = reverse('membership:submitted')
        self.assertRedirects(self.client.get(route), reverse('core:membership'))
        self.assertEqual(self.client.post(route, self.data()).status_code, 405)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_repeated_submission_token_is_idempotent(self):
        form = self.form()
        self.assertTrue(form.is_valid())
        first = submit_application(form, user=self.admin)
        second = submit_application(form, user=self.admin)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        self.assertEqual(MembershipApplicationDocument.objects.count(), 1)

    def test_invalid_or_expired_token_is_rejected(self):
        self.assertFalse(self.form(submission_token='forged').is_valid())
        form = self.form()
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 90000):
            self.assertFalse(form.is_valid())

    def test_changed_requirements_invalidate_old_form(self):
        data = self.data()
        self.requirement.instructions = 'New requirement instructions'
        self.requirement.save()
        form = ApplicationForm(data, MultiValueDict({f'document_{self.requirement.pk}': [pdf()]}))
        self.assertFalse(form.is_valid())
        self.assertIn('requirements changed', str(form.errors))

    def test_fields_validate_future_birthdate_income_category_and_dependents(self):
        for change in ({'birthdate': (timezone.localdate() + timedelta(days=1)).isoformat()},
                       {'income_category': 'invalid'}, {'dependents': '-1'}, {'full_name': '   '},
                       {'contact_number': ' '}, {'email': 'not-email'}):
            with self.subTest(change=change):
                self.assertFalse(self.form(**change).is_valid())

    def test_required_optional_and_inactive_documents(self):
        self.assertFalse(ApplicationForm(self.data()).is_valid())
        self.requirement.is_required = False
        self.requirement.save()
        self.assertTrue(ApplicationForm(self.data()).is_valid())
        self.requirement.is_active = False
        self.requirement.save()
        form = ApplicationForm(self.data())
        self.assertTrue(form.is_valid())
        self.assertTrue(all(item.get('capture_key') and not item['required'] for item in form.snapshot))
        self.assertNotIn(self.requirement.pk, [item['id'] for item in form.snapshot])

    def test_extension_mime_signature_empty_and_oversized_uploads_rejected(self):
        samples = [('run.exe', b'%PDF-', 'application/pdf'), ('fake.pdf', b'<script>', 'application/pdf'),
                   ('proof.pdf', b'%PDF-', 'text/html'), ('empty.pdf', b'', 'application/pdf'),
                   ('large.pdf', b'%PDF-' + b'x' * 100, 'application/pdf')]
        with override_settings(MEMBERSHIP_FILE_MAX_BYTES=100):
            for name, content, mime in samples:
                with self.subTest(name=name):
                    form = ApplicationForm(self.data(), MultiValueDict({f'document_{self.requirement.pk}': [
                        SimpleUploadedFile(name, content, content_type=mime)]}))
                    self.assertFalse(form.is_valid())

    def test_unexpected_or_multiple_uploads_rejected(self):
        for uploads in ({'unexpected': [pdf()]}, {f'document_{self.requirement.pk}': [pdf(), pdf()]}):
            form = ApplicationForm(self.data(), MultiValueDict(uploads))
            self.assertFalse(form.is_valid())

    @override_settings(MEMBERSHIP_TOTAL_MAX_BYTES=10)
    def test_streaming_upload_limit_blocks_partial_submission(self):
        data = self.data()
        data[f'document_{self.requirement.pk}'] = pdf()
        self.client.force_login(self.admin)
        response = self.client.post(reverse('membership:encode'), data)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_retired_intake_never_creates_submission_counters(self):
        for client in (self.client, Client()):
            self.assertEqual(client.post(reverse('core:membership'), {}).status_code, 405)
        self.assertFalse(SubmissionWindow.objects.exists())

    def test_historical_submission_counter_cleanup_is_preserved(self):
        SubmissionWindow.objects.create(key='a'*64, started_at=timezone.now()-timedelta(days=1))
        call_command('purge_submission_windows', stdout=StringIO())
        self.assertFalse(SubmissionWindow.objects.exists())

    def test_public_and_admin_posts_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('core:membership'), self.data()).status_code, 403)
        application = self.application()
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('membership:detail', args=[application.reference]), {
            'action': 'decide', 'decision': 'rejected', 'version': 0, 'notes': 'Test'}).status_code, 403)

    def test_review_and_download_require_separate_permissions(self):
        application = self.application()
        detail = reverse('membership:detail', args=[application.reference])
        download = reverse('membership:document', args=[application.documents.get().pk])
        for url in (reverse('membership:list'), detail, download):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.get(download).status_code, 403)
        self.assertEqual(self.client.post(detail, {'action': 'verify'}).status_code, 403)
        self.assertEqual(self.client.post(detail, {'action': 'decide'}).status_code, 403)
        for service in (self.verify, self.decide):
            with self.assertRaises(PermissionDenied):
                service(application, user=self.viewer)

    def test_private_download_attachment_is_audited_and_uncached(self):
        application = self.application()
        document = application.documents.get()
        grant(self.viewer, 'documents.view_membershipapplicationdocument')
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('membership:document', args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', response['Content-Security-Policy'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertTrue(response.closed)  # Django's test iterator closes the response safely.
        self.assertTrue(application.events.filter(action='document_downloaded', actor=self.viewer).exists())
        self.assertEqual(self.client.get(document.file.url).status_code, 404)

    def test_missing_file_returns_404_and_prevents_approval(self):
        application = self.verify(self.application())
        document = application.documents.get()
        document.file.storage.delete(document.file.name)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('membership:document', args=[document.pk])).status_code, 404)
        with self.assertRaisesMessage(ValidationError, 'required document is missing'):
            self.decide(application)
        self.assertEqual(Member.objects.count(), 0)

    def test_approval_requires_verified_result(self):
        application = self.application()
        with self.assertRaises(ValidationError):
            self.decide(application)
        application = self.verify(application, verified=False)
        with self.assertRaises(ValidationError):
            self.decide(application)
        self.assertEqual(Member.objects.count(), 0)

    def test_verification_records_actor_time_notes_and_link(self):
        application = self.verify(self.application())
        self.assertTrue(application.prpwd_verified)
        self.assertEqual(application.prpwd_verified_by, self.admin)
        self.assertIsNotNone(application.prpwd_verified_at)
        self.assertEqual(application.verification_notes, 'Checked manually.')
        self.assertEqual(application.verification_url, self.policy.prpwd_url)
        self.assertEqual(application.version, 1)

    def test_approval_copies_profile_once_and_preserves_application(self):
        application = self.decide(self.verify(self.application()))
        member = Member.objects.get()
        self.assertEqual(member.application, application)
        self.assertEqual(member.full_name, application.full_name)
        self.assertEqual(member.monthly_income, application.monthly_income)
        self.assertTrue(member.is_active)
        self.assertEqual(application.status, 'approved')
        self.assertEqual(application.events.filter(action='approved').count(), 1)
        for service in (self.decide, self.verify):
            with self.assertRaises(ValidationError):
                service(application)
        self.assertEqual(Member.objects.count(), 1)

    def test_rejection_requires_notes_and_creates_no_member(self):
        application = self.application()
        with self.assertRaises(ValidationError):
            self.decide(application, decision='rejected', notes=' ')
        application = self.decide(application, decision='rejected', notes='Document could not be verified.')
        self.assertEqual(application.status, 'rejected')
        self.assertEqual(Member.objects.count(), 0)
        self.assertTrue(application.events.filter(action='rejected', actor=self.admin).exists())

    def test_stale_review_cannot_override_new_verification(self):
        application = self.application()
        self.verify(application)
        with self.assertRaisesMessage(ValidationError, 'Another review changed'):
            self.decide(application)
        with self.assertRaises(ValidationError):
            self.verify(application, verified=False)

    def test_duplicate_member_control_number_rolls_back_second_approval(self):
        self.decide(self.verify(self.application()))
        second = self.verify(self.application(control_number='TEST-001'))
        with self.assertRaisesMessage(ValidationError, 'already exists'):
            self.decide(second)
        second.refresh_from_db()
        self.assertEqual(second.status, 'pending')
        self.assertEqual(Member.objects.count(), 1)
        self.assertFalse(second.events.filter(action='approved').exists())

    def test_requirement_edits_do_not_rewrite_submitted_history(self):
        application = self.verify(self.application())
        self.requirement.is_active = False
        self.requirement.save()
        self.requirement.document_type.name = 'Renamed document'
        self.requirement.document_type.save()
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(name='New requirement'))
        self.decide(application)
        application.refresh_from_db()
        self.assertEqual(application.requirements_snapshot[0]['label'], 'Test document')
        self.assertEqual(application.documents.get().label, 'Test document')
        self.assertEqual(Member.objects.count(), 1)

    def test_failed_submission_rolls_back_rows_and_saved_files(self):
        form = self.form()
        self.assertTrue(form.is_valid())
        with patch('membership.services.record_event', side_effect=RuntimeError('simulate audit failure')):
            with self.assertRaises(RuntimeError):
                submit_application(form, user=self.admin)
        self.assertEqual(MembershipApplication.objects.count(), 0)
        self.assertEqual(MembershipApplicationDocument.objects.count(), 0)
        self.assertEqual([item for item in Path(self.media.name).rglob('*') if item.is_file()], [])

    def test_failed_approval_audit_rolls_back_member_and_decision(self):
        application = self.verify(self.application())
        with patch('membership.services.record_event', side_effect=RuntimeError('simulate audit failure')):
            with self.assertRaises(RuntimeError):
                self.decide(application)
        application.refresh_from_db()
        self.assertEqual(application.status, 'pending')
        self.assertEqual(Member.objects.count(), 0)

    def test_admin_workflow_records_actions_and_escapes_applicant_content(self):
        application = self.application(full_name='<script>alert(1)</script>')
        self.client.force_login(self.admin)
        url = reverse('membership:detail', args=[application.reference])
        response = self.client.get(url)
        self.assertContains(response, 'id="approve_verified"', count=1)
        self.assertNotContains(response, 'id="verify_notes"')
        self.assertNotContains(response, 'id="decision_notes"')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        response = self.client.post(url, {'action': 'verify', 'version': 0, 'verified': 'yes', 'notes': 'Manual check'})
        self.assertRedirects(response, url)
        response = self.client.post(url, {'action': 'decide', 'version': 1, 'decision': 'approved', 'notes': 'All checked'})
        self.assertRedirects(response, url)
        self.assertContains(self.client.get(url), 'An official member record has been created.')
        self.assertEqual(self.client.post(url, {'action': 'unknown'}).status_code, 400)

    def test_retired_list_redirects_without_forwarding_old_filters(self):
        self.application()
        self.client.force_login(self.viewer)
        url = reverse('membership:list')
        for query in ({'q': 'test-001'}, {'q': 'missing'}, {'status': 'approved'}, {'page': 'invalid'}):
            self.assertRedirects(self.client.get(url, query), reverse('membership:review_home'))

    def test_settings_require_https_and_link_before_opening(self):
        for value in ('http://example.test/', 'javascript:alert(1)', 'https://user:password@example.test/', ''):
            self.policy.prpwd_url = value
            with self.assertRaises(ValidationError):
                self.policy.full_clean()

    def test_application_and_member_have_no_admin_mutation_bypass(self):
        self.client.force_login(self.admin)
        for url in ('/admin/membership/membershipapplication/add/', '/admin/members/member/add/'):
            self.assertEqual(self.client.get(url).status_code, 404)
        application = self.application()
        event = application.events.first()
        response = self.client.get(reverse('admin:membership_membershipevent_change', args=[event.pk]))
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(self.client.post(reverse('admin:membership_membershipevent_delete', args=[event.pk]), {'post': 'yes'}).status_code, 403)


class ConcurrentDecisionTests(TransactionTestCase):
    def test_two_reviewers_create_exactly_one_member(self):
        MembershipSettings.objects.update_or_create(pk=1, defaults={
            'registration_open': True, 'prpwd_url': 'https://registry.example.test/'})
        user = get_user_model().objects.create_superuser('concurrency_admin')
        form = ApplicationForm({**onsite_profile(), 'submission_token': ApplicationForm().initial['submission_token']})
        self.assertTrue(form.is_valid(), form.errors)
        application = submit_application(form, user=user)
        application = record_verification(application.reference, user=user, version=0, verified=True, notes='Test check')

        def worker():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                decide_application(application.reference, user=actor, version=1, decision='approved', notes='Test decision')
                return 'approved'
            except ValidationError:
                return 'blocked'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: worker(), range(2)))
        self.assertCountEqual(outcomes, ['approved', 'blocked'])
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.filter(action='approved').count(), 1)
