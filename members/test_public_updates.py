"""Member self-service never accepts a source change before an audited decision."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
import smtplib
import uuid

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.referral_connection import EmailConnectionRequired
from assistance.referral_models import ReferralSettings, referral_write
from membership.models import MembershipApplication
from membership.pdf_registration_forms import AssociationPDFForm
from membership.registration_decisions import member_values
from membership.test_pdf_registration import association_data
from membership.tests import grant
from programs.tests import create_program, verification
from .models import Member, DisabilityType
from .registration_form import MemberRegistrationForm
from .update_forms import PublicMemberUpdateForm
from .update_models import MemberUpdateAccess, MemberUpdateRequest, MemberUpdateAction, MemberUpdateEmail, update_write
from . import update_services as service, update_mail


class UpdateHelpers:
    def setup_update(self):
        self.actor = get_user_model().objects.create_superuser('SYNTHETIC-MEMBER-UPDATE')
        with referral_write():
            ReferralSettings.objects.create(sender_email='association@example.invalid')
        DisabilityType.objects.get_or_create(name='Visual Disability')
        form = AssociationPDFForm(association_data() | {'contact_number': '09170000000', 'guardian_name': 'Original guardian'})
        self.assertTrue(form.is_valid(), form.errors)
        self.source = form.submitted_data()
        values, classifications = member_values(self.source, '00-0000-000-0000001')
        self.application = MembershipApplication.objects.create(**values, submission_key=uuid.uuid4(), status='approved',
            decided_by=self.actor, decided_at=timezone.now())
        self.member = Member.objects.create(application=self.application, **values)
        self.member.disability_types.set(classifications)
        self.member.refresh_from_db()
        self.nonce = 'synthetic-session-nonce'

    def identity(self):
        return {'control_number': self.member.control_number, 'full_name': self.member.full_name}

    def access(self, nonce=None):
        nonce = nonce or self.nonce
        with patch('members.update_services.secrets.randbelow', return_value=123456):
            access = service.start_access(nonce=nonce, **self.identity())
        update_mail.deliver(access.email.pk)
        self.assertTrue(service.verify_code(access.pk, nonce=nonce, code='123456'))
        return access

    def payload(self, access, **changes):
        return service.initial_values(self.member) | {'request_key': str(access.pk), 'acknowledgement': 'on', **changes}

    def request_update(self, **changes):
        access = self.access()
        return service.submit_update(access.pk, nonce=self.nonce,
            data=self.payload(access, **(changes or {'guardian_name': 'Updated guardian'})))

    def invite(self, record):
        record.refresh_from_db()
        self.member.refresh_from_db()
        job = service.invite_member(record.pk, user=self.actor, version=record.version, member_version=self.member.version)
        update_mail.deliver(job.pk)
        job.refresh_from_db()
        record.refresh_from_db()
        return job

    def decide(self, record, decision, **changes):
        record.refresh_from_db()
        self.member.refresh_from_db()
        return service.decide_update(record.pk, user=self.actor, version=record.version,
            member_version=self.member.version, decision=decision, reason='Synthetic interview review.', **changes)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PDAO_ENFORCEMENT_ENABLED=False)
class PublicMemberUpdateTests(UpdateHelpers, TestCase):
    def setUp(self):
        self.setup_update()

    def test_only_pwd_and_name_are_needed_before_saved_email_verification(self):
        response = self.client.get(reverse('members:update_start'))
        self.assertEqual(list(response.context['form'].fields), ['control_number', 'full_name'])
        for name in ('birthdate', 'contact_number', 'email'):
            self.assertNotContains(response, f'name="{name}"')
        with patch('members.update_services.secrets.randbelow', return_value=123456), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('members:update_start'), self.identity())
        self.assertRedirects(response, reverse('members:update_code'), fetch_redirect_response=False)
        access = MemberUpdateAccess.objects.get()
        self.assertEqual(access.member_id, self.member.pk)
        self.assertIsNone(access.verified_at)
        self.assertEqual(mail.outbox[0].to, [self.member.email])
        with self.assertRaises(ValidationError):
            service.verified_access(access.pk, self.client.session[service.SESSION_KEY]['nonce'])
        response = self.client.post(reverse('members:update_code'), {'code': '123456'})
        self.assertRedirects(response, reverse('members:update_information'), fetch_redirect_response=False)
        response = self.client.get(reverse('members:update_information'))
        self.assertEqual(response.context['form'].initial['guardian_name'], 'Original guardian')
        self.assertTrue(response.context['form'].fields['pwd_number'].disabled)

    def test_unverified_and_unmatched_visitors_never_receive_member_details(self):
        self.assertRedirects(self.client.get(reverse('members:update_information')),
            reverse('members:update_start'), fetch_redirect_response=False)
        response = self.client.post(reverse('members:update_start'), self.identity() | {'full_name': 'Wrong name'})
        self.assertRedirects(response, reverse('members:update_code'), fetch_redirect_response=False)
        access = MemberUpdateAccess.objects.get()
        self.assertIsNone(access.member_id)
        self.assertFalse(MemberUpdateEmail.objects.exists())
        response = self.client.get(reverse('members:update_code'))
        self.assertNotContains(response, self.member.email)
        self.assertNotContains(response, self.member.full_name)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('private', response['Cache-Control'])
        self.assertFalse(service.verify_code(access.pk, nonce=self.client.session[service.SESSION_KEY]['nonce'], code='123456'))

    def test_code_attempts_expiry_session_binding_and_replay(self):
        with patch('members.update_services.secrets.randbelow', return_value=123456):
            access = service.start_access(nonce=self.nonce, **self.identity())
        self.assertFalse(service.verify_code(access.pk, nonce='another-session', code='123456'))
        for _ in range(5):
            self.assertFalse(service.verify_code(access.pk, nonce=self.nonce, code='000000'))
        self.assertFalse(service.verify_code(access.pk, nonce=self.nonce, code='123456'))
        with patch('members.update_services.secrets.randbelow', return_value=123456):
            fresh = service.start_access(nonce=self.nonce, **self.identity())
        with patch('members.update_services.timezone.now', return_value=fresh.expires_at):
            self.assertFalse(service.verify_code(fresh.pk, nonce=self.nonce, code='123456'))
        verified = self.access()
        self.assertFalse(service.verify_code(verified.pk, nonce=self.nonce, code='123456'))
        verified.refresh_from_db()
        with patch('members.update_services.timezone.now', return_value=verified.access_expires_at):
            with self.assertRaises(ValidationError):
                service.verified_access(verified.pk, self.nonce)

    def test_verified_form_prefills_current_record_and_locks_pwd(self):
        access = self.access()
        session = self.client.session
        session[service.SESSION_KEY] = {'id': str(access.pk), 'nonce': self.nonce}
        session.save()
        response = self.client.get(reverse('members:update_information'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['guardian_name'], 'Original guardian')
        self.assertTrue(response.context['form'].fields['pwd_number'].disabled)
        self.assertContains(response, 'name="request_key"', count=1)
        self.assertNotContains(response, 'type="file"')
        self.assertNotContains(response, 'name="version"')
        self.assertNotContains(response, 'Earlier recorded information')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('private', response['Cache-Control'])

    def test_pwd_request_scope_and_extra_fields_cannot_be_tampered(self):
        access = self.access()
        for changes in ({'pwd_number': '9999'}, {'request_key': str(uuid.uuid4())},
                        {'is_active': '1'}, {'version': '0'}, {'acknowledgement': ''}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                service.submit_update(access.pk, nonce=self.nonce, data=self.payload(access, guardian_name='Changed', **changes))
        self.assertFalse(MemberUpdateRequest.objects.exists())
        self.member.refresh_from_db()
        self.assertEqual(self.member.control_number, '00-0000-000-0000001')

    def test_submission_is_idempotent_and_does_not_change_approved_sources(self):
        access = self.access()
        payload = self.payload(access, guardian_name='New guardian', email='proposed@example.invalid')
        first = service.submit_update(access.pk, nonce=self.nonce, data=payload)
        second = service.submit_update(access.pk, nonce=self.nonce, data=payload)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(set(first.changed_fields), {'guardian_name', 'email'})
        self.assertEqual(MemberUpdateRequest.objects.count(), 1)
        self.member.refresh_from_db(); self.application.refresh_from_db()
        self.assertEqual(self.member.registration_profile, self.source)
        self.assertEqual(self.application.registration_profile, self.source)
        self.assertEqual(self.member.version, 0)
        self.assertFalse(service.requires_verification(self.member))
        self.assertEqual(self.member.events.get().action, 'member_update_submitted')
        with self.assertRaises(ValidationError):
            service.submit_update(access.pk, nonce=self.nonce, data=payload | {'guardian_name': 'Another value'})

    def test_unchanged_submission_and_second_open_request_are_rejected(self):
        access = self.access()
        with self.assertRaisesMessage(ValidationError, 'No information has changed'):
            service.submit_update(access.pk, nonce=self.nonce, data=self.payload(access))
        self.request_update()
        another = self.access()
        with self.assertRaisesMessage(ValidationError, 'already awaiting'):
            service.submit_update(another.pk, nonce=self.nonce, data=self.payload(another, guardian_name='Another'))

    def test_comparison_shows_only_requested_fields_and_escapes_markup(self):
        record = self.request_update(guardian_name='<script>unsafe()</script>', employment_status='self_employed')
        self.client.force_login(self.actor)
        response = self.client.get(reverse('members:update_review', args=[record.pk]))
        self.assertEqual([row['name'] for row in response.context['comparison']], ['employment_status', 'guardian_name'])
        self.assertContains(response, 'Self-employed')
        self.assertContains(response, 'Original guardian')
        self.assertContains(response, '&lt;script&gt;unsafe()&lt;/script&gt;')
        self.assertNotContains(response, '<script>unsafe()</script>')

    def test_only_staff_with_update_permissions_can_send_or_decide(self):
        record = self.request_update()
        url = reverse('members:update_review', args=[record.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        viewer = get_user_model().objects.create_user('SYNTHETIC-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'members.view_member')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertNotContains(self.client.get(url), '>Verify this information</button>')
        self.assertEqual(self.client.post(url, {'version': 0, 'member_version': 0, 'action': 'invite'}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            service.decide_update(record.pk, user=viewer, version=0, member_version=0,
                decision='approved', reason='Unauthorized', interview_confirmed=True)

    def test_invitation_goes_to_verified_saved_email_and_repeated_send_is_single(self):
        record = self.request_update(email='proposed@example.invalid')
        job = self.invite(record)
        self.assertEqual(job.recipient, self.member.email)
        self.assertTrue(update_mail.accepted(job))
        second = service.invite_member(record.pk, user=self.actor, version=record.version, member_version=0)
        self.assertEqual(job.pk, second.pk)
        self.assertFalse(update_mail.deliver(job.pk))
        self.assertEqual(job.attempts.count(), 1)
        self.assertEqual(len(mail.outbox), 2)  # Identity code and office invitation.
        self.assertFalse(service.requires_verification(self.member))

    def test_approval_requires_invitation_interview_and_reason(self):
        record = self.request_update()
        with self.assertRaisesMessage(ValidationError, 'invitation successfully'):
            self.decide(record, 'approved', interview_confirmed=True)
        self.invite(record)
        with self.assertRaisesMessage(ValidationError, 'Confirm the member attended'):
            self.decide(record, 'approved')
        with self.assertRaisesMessage(ValidationError, 'Record a reason'):
            service.decide_update(record.pk, user=self.actor, version=record.version,
                member_version=0, decision='approved', reason='', interview_confirmed=True)
        self.decide(record, 'approved', interview_confirmed=True)
        self.member.refresh_from_db(); self.application.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(self.member.registration_profile['guardian_name'], 'Updated guardian')
        self.assertEqual(self.application.registration_profile, self.source)
        self.assertEqual(self.member.control_number, '00-0000-000-0000001')
        self.assertEqual(record.state, 'approved')
        self.assertEqual(self.member.version, 1)

    def test_needs_verification_blocks_both_verification_flows_and_old_grant_submission(self):
        from programs import application_workflow as workflow
        from programs.services import verify_member, submit_application
        program = create_program(ewaf_applicable=True)
        record = self.request_update()
        with patch('programs.services.require_open'), patch('programs.application_workflow.require_application_policy'):
            legacy = verify_member(program.pk, **verification(self.member, program))
            modern, _, _ = workflow.verify(program.pk, version=program.version,
                control_number=self.member.control_number, full_name=self.member.full_name)
            self.assertTrue(workflow.secure_grant(modern, program))
            self.decide(record, 'needs_verification')
            self.assertTrue(service.requires_verification(self.member))
            self.assertFalse(workflow.secure_grant(modern, program))
            with self.assertRaises(ValidationError):
                workflow.verify(program.pk, version=program.version, control_number=self.member.control_number, full_name=self.member.full_name)
            with self.assertRaisesMessage(ValidationError, 'needs verification'):
                verify_member(program.pk, **verification(self.member, program))
            with override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=False), self.assertRaisesMessage(ValidationError, 'needs verification'):
                submit_application(program.pk, grant=legacy, data={}, files={})
            self.invite(record)
            self.decide(record, 'approved', interview_confirmed=True)
            self.member.refresh_from_db()
            self.assertFalse(service.requires_verification(self.member))
            self.assertTrue(workflow.confirmed_member(self.member))

    def test_directory_status_filters_and_review_link(self):
        record = self.request_update()
        self.client.force_login(self.actor)
        url = reverse('member_directory')
        response = self.client.get(url, {'status': 'update_needed'})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        row = response.context['directory_members'][0]
        self.assertEqual(row['status_label'], 'Update needed')
        self.assertEqual(row['update_url'], reverse('members:update_review', args=[record.pk]))
        self.assertEqual(self.client.get(url, {'status': 'active'}).context['page_obj'].paginator.count, 1)
        self.decide(record, 'needs_verification')
        response = self.client.get(url, {'status': 'needs_verification'})
        self.assertEqual(response.context['directory_members'][0]['status_label'], 'Needs verification')
        self.assertEqual(self.client.get(url, {'status': 'active'}).context['page_obj'].paginator.count, 0)

    def test_stale_review_is_rejected_and_fresh_review_merges_only_requested_fields(self):
        from .services import update_member
        record = self.request_update()
        self.invite(record)
        update_member(self.member.pk, user=self.actor, version=0,
            data=service.initial_values(self.member) | {'member_profile_format': 'association_pdf_v1', 'acknowledgement': 'on',
                'version': 0, 'notes': 'Unrelated correction', 'spouse_name': 'Staff corrected spouse'}, notes='Unrelated correction')
        with self.assertRaisesMessage(ValidationError, 'record changed'):
            service.decide_update(record.pk, user=self.actor, version=record.version, member_version=0,
                decision='approved', reason='Stale page', interview_confirmed=True)
        self.decide(record, 'approved', interview_confirmed=True)
        self.member.refresh_from_db()
        self.assertEqual(self.member.registration_profile['spouse_name'], 'Staff corrected spouse')
        self.assertEqual(self.member.registration_profile['guardian_name'], 'Updated guardian')

    def test_audit_failure_rolls_back_submission_and_approval(self):
        access = self.access()
        with patch('members.update_services.action', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                service.submit_update(access.pk, nonce=self.nonce, data=self.payload(access, guardian_name='Updated'))
        self.assertFalse(MemberUpdateRequest.objects.exists())
        access.refresh_from_db(); self.assertIsNone(access.submitted_at)
        record = self.request_update(); self.invite(record)
        with patch('members.update_services.action', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.decide(record, 'approved', interview_confirmed=True)
        self.member.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(self.member.registration_profile, self.source)
        self.assertEqual(self.member.version, 0)
        self.assertEqual(record.state, 'invited')
        self.assertFalse(self.member.events.filter(action='profile_updated').exists())

    def test_failed_invitation_can_retry_but_uncertain_delivery_cannot_resend(self):
        record = self.request_update()
        job = service.invite_member(record.pk, user=self.actor, version=0, member_version=0)
        with patch('members.update_mail.transport_for', side_effect=EmailConnectionRequired('Synthetic unavailable')):
            self.assertFalse(update_mail.deliver(job.pk))
        job.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        with self.assertRaises(ValidationError):
            self.decide(record, 'approved', interview_confirmed=True)
        service.retry_invitation(record.pk, user=self.actor, version=record.version, member_version=0)
        with patch('members.update_mail.EmailMessage.send', side_effect=OSError('Synthetic uncertain submission')):
            self.assertFalse(update_mail.deliver(job.pk))
        job.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        with self.assertRaisesMessage(ValidationError, 'unconfirmed'):
            service.retry_invitation(record.pk, user=self.actor, version=record.version, member_version=0)

    def test_connection_failure_before_submission_is_retryable_and_quit_keeps_acceptance(self):
        record = self.request_update()
        job = service.invite_member(record.pk, user=self.actor, version=0, member_version=0)
        with patch('django.core.mail.backends.locmem.EmailBackend.open',
                   side_effect=smtplib.SMTPServerDisconnected('Synthetic connect')):
            self.assertFalse(update_mail.deliver(job.pk))
        job.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempts.get().error_type, 'SMTPServerDisconnected')
        service.retry_invitation(record.pk, user=self.actor, version=record.version, member_version=0)
        with patch('django.core.mail.backends.locmem.EmailBackend.close',
                   side_effect=smtplib.SMTPServerDisconnected('Synthetic QUIT')):
            self.assertTrue(update_mail.deliver(job.pk))
        job.refresh_from_db()
        self.assertTrue(update_mail.accepted(job))
        self.assertFalse(update_mail.deliver(job.pk))

    def test_request_snapshots_actions_and_email_contents_are_protected(self):
        record = self.request_update()
        with self.assertRaises(PermissionDenied):
            MemberUpdateRequest.objects.filter(pk=record.pk).update(proposed_values={})
        with update_write(), self.assertRaises(PermissionDenied):
            record.proposed_values = {}
            record.save(update_fields=['proposed_values'])
        with self.assertRaises(PermissionDenied):
            record.actions.all().delete()

    def test_identity_requests_are_rate_limited_without_storing_raw_identifiers(self):
        from .update_models import MemberUpdateWindow
        for _ in range(5):
            self.assertTrue(service.reserve_access(self.member.control_number, '127.0.0.2'))
        self.assertFalse(service.reserve_access(self.member.control_number, '127.0.0.3'))
        self.assertNotIn(self.member.control_number, str(list(MemberUpdateWindow.objects.values_list('key', flat=True))))

    def test_public_and_admin_post_endpoints_enforce_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post(reverse('members:update_start'), self.identity()).status_code, 403)
        record = self.request_update()
        browser.force_login(self.actor)
        self.assertEqual(browser.post(reverse('members:update_review', args=[record.pk]),
            {'version': 0, 'member_version': 0, 'action': 'invite'}).status_code, 403)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MemberUpdateConcurrencyTests(UpdateHelpers, TransactionTestCase):
    def test_simultaneous_submissions_create_one_open_request(self):
        self.setup_update()
        one, two = self.access('first-session'), self.access('second-session')
        barrier = Barrier(2)
        payloads = [self.payload(one, guardian_name='First change'), self.payload(two, guardian_name='Second change')]

        def submit(args):
            access, nonce, data = args
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return str(service.submit_update(access.pk, nonce=nonce, data=data).pk)
            except ValidationError:
                return 'pending'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [(one, 'first-session', payloads[0]), (two, 'second-session', payloads[1])]))
        self.assertEqual(results.count('pending'), 1)
        self.assertEqual(MemberUpdateRequest.objects.count(), 1)
        self.assertEqual(MemberUpdateAction.objects.filter(action='submitted').count(), 1)
        self.member.refresh_from_db()
        self.assertEqual(self.member.registration_profile, self.source)
