"""Fictional member requests; mail is always captured locally in these tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import smtplib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from members.tests import create_member
from membership.tests import grant, pdf
from programs.models import ProgramApplication
from .models import AssistanceCase, AssistanceRelease
from .referral_models import (ReferralGrant, ReferralTicket, ReferralAttachment, ReferralAction,
    ReferralEmail, ReferralEmailAttempt, ReferralSettings, ReferralSettingsEvent, referral_write)
from .referral_forms import TicketForm
from .referral_mail import deliver_email, retry_email, delivery_label
from . import referral_services as service


class Fixtures:
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.admin = get_user_model().objects.create_superuser('referral_admin')
        self.viewer = get_user_model().objects.create_user('referral_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'assistance.view_referralticket')
        self.member = create_member('REFERRAL-001')
        self.member.refresh_from_db()
        self.binding = service.binding_for('synthetic-session')
        self.verification = dict(control_number=self.member.control_number, full_name=self.member.full_name)
        self.data = dict(email='fictional@example.invalid',
            subject='Help with medical requirements', assistance_type='medical',
            concern='Synthetic concern for tests only.', acknowledgement='on')
        service.set_sender(user=self.admin, data=dict(version=0, sender_email='association@example.invalid', reason='Test configuration'))

    def verified(self, **changes):
        return service.verify_member(binding=self.binding, **(self.verification | changes))

    def submit(self, **kwargs):
        return service.submit_ticket(self.verified().pk, self.binding, data=self.data, **kwargs)

    def review_data(self, **changes):
        return dict(version=0, sender_version=ReferralSettings.objects.get(pk=1).version,
            status='in_review', channel='email', notes='Private staff note',
            member_message='Please bring supporting evidence to the Help Desk.') | changes

    def review(self, ticket, **changes):
        return service.review_ticket(ticket.pk, user=self.admin, data=self.review_data(**changes))


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReferralTests(Fixtures, TestCase):
    def test_quit_failure_keeps_accepted_acknowledgment_and_prevents_resend(self):
        with patch('django.core.mail.backends.locmem.EmailBackend.close',
                   side_effect=smtplib.SMTPServerDisconnected('Synthetic QUIT')), \
                self.captureOnCommitCallbacks(execute=True):
            ticket = self.submit()
        job = ticket.emails.get()
        self.assertEqual((job.state, job.attempt_count), ('sent', 1))
        self.assertEqual(job.attempts.get().outcome, 'accepted')
        self.assertFalse(deliver_email(job.pk))

    def test_interrupted_reply_is_unconfirmed_without_automatic_resend(self):
        ticket = self.submit()
        with patch('assistance.referral_mail.EmailMessage.send',
                   side_effect=smtplib.SMTPServerDisconnected('private diagnostic')), \
                self.captureOnCommitCallbacks(execute=True):
            self.review(ticket)
        job = ticket.emails.order_by('-created_at').first()
        self.assertEqual(job.attempts.get().error_type, 'EmailDeliveryUnconfirmed')
        self.assertEqual(delivery_label(job), 'Email delivery is unconfirmed')
        self.assertFalse(deliver_email(job.pk))
        self.client.force_login(self.admin)
        page = self.client.get(reverse('assistance:referral_detail', args=[ticket.pk]))
        self.assertContains(page, 'another attempt could send a duplicate')
        self.assertNotContains(page, 'private diagnostic')

    def test_verification_failure_is_generic_and_no_grant_for_invalid_details(self):
        errors = []
        for change in ({'control_number': 'UNKNOWN'}, {'full_name': 'Wrong'},
                       {'control_number': ''}, {'full_name': ''}):
            with self.assertRaises(ValidationError) as caught:
                self.verified(**change)
            errors.append(caught.exception.messages)
        self.assertTrue(all(error == errors[0] for error in errors))
        self.assertFalse(ReferralGrant.objects.exists())

    def test_verification_accepts_normalized_control_number_and_full_name_only(self):
        token = self.verified(control_number='  ' + self.member.control_number.lower() + '  ',
            full_name='  ' + '   '.join(self.member.full_name.upper().split()) + '  ')
        self.assertEqual(token.member_id, self.member.pk)

    def test_verification_requires_each_field_before_creating_a_grant(self):
        for field in ('control_number', 'full_name'):
            with self.subTest(field=field):
                response = self.client.post(reverse('assistance:referral_verify'),
                    self.verification | {field: ''})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context['form'].errors)
        self.assertFalse(ReferralGrant.objects.exists())

    def test_active_approved_manually_verified_members_only(self):
        for field, value in [('is_active', False), ('archived_at', timezone.now())]:
            previous = getattr(self.member, field)
            setattr(self.member, field, value)
            if field == 'archived_at':
                self.member.is_active = False
            self.member.save()
            with self.assertRaises(ValidationError):
                self.verified()
            setattr(self.member, field, previous)
            self.member.is_active = True
            self.member.save()
        application = self.member.application
        for field, value in [('status', 'pending'), ('prpwd_verified', False), ('prpwd_verified', None), ('prpwd_verified_at', None), ('decided_at', None)]:
            previous = getattr(application, field)
            setattr(application, field, value)
            application.save()
            with self.assertRaises(ValidationError):
                self.verified()
            setattr(application, field, previous)
            application.save()

    def test_session_expiry_revocation_and_changed_membership_are_rechecked(self):
        token = self.verified()
        with self.assertRaises(PermissionDenied):
            service.submit_ticket(token.pk, service.binding_for('another-session'), data=self.data)
        with patch('assistance.referral_services.timezone.now', return_value=token.expires_at):
            with self.assertRaises(PermissionDenied):
                service.submit_ticket(token.pk, self.binding, data=self.data)
        self.member.version += 1
        self.member.save()
        with self.assertRaises(ValidationError):
            service.submit_ticket(token.pk, self.binding, data=self.data)
        token = self.verified()
        service.finish(token.pk, self.binding)
        with self.assertRaises(PermissionDenied):
            service.get_grant(token.pk, self.binding)
        self.assertFalse(ReferralTicket.objects.exists())

    @override_settings(REFERRAL_MEMBER_LIMIT=2)
    def test_verification_rate_limits_do_not_reveal_membership(self):
        for code in ('UNKNOWN', 'unknown'):
            self.assertTrue(service.reserve_attempt(code, '127.0.0.1', self.binding))
        self.assertFalse(service.reserve_attempt('UNKNOWN', '127.0.0.2', service.binding_for('different')))

    def test_submission_optional_evidence_idempotency_and_program_separation(self):
        counts = [model.objects.count() for model in (ProgramApplication, AssistanceCase, AssistanceRelease)]
        token = self.verified()
        with self.captureOnCommitCallbacks(execute=True):
            ticket = service.submit_ticket(token.pk, self.binding, data=self.data)
        self.assertEqual(ticket.full_name, self.member.full_name)
        self.assertEqual(ticket.address, self.member.address)
        self.assertEqual(ticket.contact_number, self.member.contact_number)
        self.assertEqual(ticket.subject, self.data['subject'])
        self.assertTrue(ticket.reference.startswith('ASR-'))
        self.assertFalse(ticket.attachments.exists())
        self.assertEqual(service.submit_ticket(token.pk, self.binding, data=self.data).pk, ticket.pk)
        self.assertEqual(ReferralTicket.objects.count(), 1)
        self.assertEqual(ReferralAction.objects.count(), 1)
        self.assertEqual(ReferralEmail.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(ticket.reference, mail.outbox[0].body)
        self.assertIn(self.data['concern'], mail.outbox[0].body)
        self.assertIn('Subject: ' + self.data['subject'], mail.outbox[0].body)
        self.assertIn('does not guarantee', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].reply_to, ['association@example.invalid'])
        self.assertEqual([model.objects.count() for model in (ProgramApplication, AssistanceCase, AssistanceRelease)], counts)
        with self.assertRaises(ValidationError):
            service.submit_ticket(token.pk, self.binding, data=self.data | {'concern': 'Changed'})
        with self.assertRaises(ValidationError):
            service.submit_ticket(token.pk, self.binding, data=self.data | {'subject': 'Changed subject'})

    def test_required_email_acknowledgment_and_upload_validation(self):
        for change in ({'email': ''}, {'email': 'invalid'}, {'full_name': 'FORGED'}, {'address': 'FORGED'}, {'contact_number': 'FORGED'},
                       {'subject': ''}, {'subject': '   '}, {'subject': 'x' * 201}, {'subject': 'Title\nAnother line'},
                       {'acknowledgement': ''}, {'assistance_type': 'unrecognized'}, {'status': 'approved'}):
            with self.subTest(change=change):
                self.assertFalse(TicketForm(self.data | change, member=self.member).is_valid())
        bad = pdf()
        bad.name = 'disguised.exe'
        self.assertFalse(TicketForm(self.data, MultiValueDict({'evidence_1': [bad]}), member=self.member).is_valid())
        self.assertFalse(TicketForm(self.data, MultiValueDict({'evidence_1': [pdf(), pdf()]}), member=self.member).is_valid())
        self.assertFalse(TicketForm(self.data, MultiValueDict({'unknown': [pdf()]}), member=self.member).is_valid())
        for key in ('evidence_2', 'evidence_3'):
            with self.subTest(field=key):
                with self.assertRaises(ValidationError):
                    self.submit(files=MultiValueDict({key: [pdf()]}))
        self.assertFalse(ReferralTicket.objects.exists())

    def test_evidence_error_keeps_optional_upload_visible(self):
        # Retained upload route: new concerns now use the combined text form.
        session = self.client.session
        session.save()
        token = service.verify_member(binding=service.binding_for(session.session_key), **self.verification)
        session['referral_grant_v1'] = str(token.pk)
        session.save()
        invalid = pdf()
        invalid.name = 'disguised.exe'
        response = self.client.post(reverse('assistance:referral_apply'), self.data | {'evidence_1': invalid})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'class="collapse show" id="supporting-evidence"', status_code=400)
        self.assertIn('evidence_1', response.context['form'].errors)
        self.assertFalse(ReferralTicket.objects.exists())

    def test_request_email_starts_blank_and_independent_address_receives_all_messages(self):
        self.member.email = 'registered-address@example.invalid'
        self.member.save(update_fields=['email'])
        form = TicketForm(member=self.member)
        self.assertFalse(form['email'].value())
        self.assertNotIn('confirm_email', form.fields)
        self.assertNotEqual(self.data['email'], self.member.email)
        with self.captureOnCommitCallbacks(execute=True):
            ticket = self.submit()
            self.review(ticket)
        self.assertEqual(ticket.email, self.data['email'])
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(message.to == [self.data['email']] for message in mail.outbox))
        self.assertTrue(all(job.recipient == self.data['email'] for job in ticket.emails.all()))
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, 'registered-address@example.invalid')

    def test_audit_failure_rolls_back_ticket_email_and_new_private_files(self):
        with patch('assistance.referral_services.record_action', side_effect=RuntimeError('Test audit failure')):
            with self.assertRaises(RuntimeError):
                self.submit(files=MultiValueDict({'evidence_1': [pdf()]}))
        self.assertFalse(ReferralTicket.objects.exists())
        self.assertFalse(ReferralEmail.objects.exists())
        self.assertFalse(ReferralAttachment.objects.exists())
        self.assertFalse([item for item in Path(self.media.name).rglob('*') if item.is_file()])

    def test_smtp_failure_keeps_ticket_and_staff_retry_records_separate_attempt(self):
        with patch('assistance.referral_mail.get_connection', side_effect=OSError('Private SMTP response')), self.captureOnCommitCallbacks(execute=True):
            ticket = self.submit()
        job = ticket.emails.get()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempts.get().error_type, 'OSError')
        self.assertTrue(ReferralTicket.objects.filter(pk=ticket.pk).exists())
        self.assertFalse(deliver_email(job.pk))
        with self.captureOnCommitCallbacks(execute=True):
            retry_email(job.pk, user=self.admin, reason='Fixed provider configuration', confirmed=True)
        job.refresh_from_db()
        self.assertEqual(job.state, 'sent')
        self.assertEqual(job.attempt_count, 2)
        self.assertEqual(job.attempts.count(), 2)
        self.assertIn('development outbox', delivery_label(job))
        self.assertFalse(deliver_email(job.pk))
        with self.assertRaises(ValidationError):
            retry_email(job.pk, user=self.admin, reason='Duplicate', confirmed=True)

    def test_review_status_history_stale_edits_and_internal_notes_not_emailed(self):
        ticket = self.submit()
        with self.captureOnCommitCallbacks(execute=True):
            self.review(ticket)
        update = ticket.emails.order_by('created_at').last()
        self.assertIn('Please bring', update.body)
        self.assertNotIn('Private staff note', update.body)
        self.review(ticket)  # Same reply request is idempotent.
        self.assertEqual(ticket.emails.count(), 2)
        with self.assertRaises(ValidationError):
            self.review(ticket, member_message='Different stale reply.')
        self.review(ticket, version=1, channel='online')
        self.assertEqual(ticket.emails.count(), 2)
        service.quick_update_ticket(ticket.pk, user=self.admin, data={'version': 2, 'action': 'closed'})
        with self.assertRaises(ValidationError):
            self.review(ticket, version=3)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'closed')
        self.assertEqual(ticket.actions.count(), 4)

    def test_review_audit_failure_is_atomic(self):
        ticket = self.submit()
        with patch('assistance.referral_services.record_action', side_effect=RuntimeError('Synthetic failure')):
            with self.assertRaises(RuntimeError):
                self.review(ticket)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'received')
        self.assertEqual(ticket.version, 0)
        self.assertEqual(ticket.emails.count(), 1)

    def test_reply_composer_uses_settings_sender_without_gmail_link(self):
        self.data.update(email='request+help@example.invalid')
        ticket = self.submit()
        before = (ticket.actions.count(), ticket.emails.count(), ReferralEmailAttempt.objects.count())
        self.client.force_login(self.admin)
        response = self.client.get(reverse('assistance:referral_detail', args=[ticket.pk]))
        self.assertContains(response, 'data-referral-sender>association@example.invalid</strong>')
        self.assertContains(response, 'request+help@example.invalid')
        self.assertNotContains(response, 'mail.google.com')
        self.assertNotContains(response, 'Reply in Gmail')
        self.assertNotContains(response, 'email_app_sent')
        self.assertEqual((ticket.actions.count(), ticket.emails.count(), ReferralEmailAttempt.objects.count()), before)

    def test_external_gmail_channel_is_not_a_new_reply(self):
        ticket = self.submit()
        for data in ({'channel': 'email_app'}, {'channel': 'email_app', 'email_app_sent': 'on'}):
            with self.assertRaises(ValidationError):
                self.review(ticket, **data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.version, 0)
        self.assertEqual(ticket.actions.count(), 1)
        self.assertEqual(ticket.emails.count(), 1)

    def test_email_permissions_default_and_closed_ticket_behavior(self):
        ticket = self.submit()
        url = reverse('assistance:referral_detail', args=[ticket.pk])
        self.client.force_login(self.viewer)
        grant(self.viewer, 'assistance.review_referralticket')
        self.assertEqual(self.client.get(url).context['form'].initial['channel'], 'online')
        self.assertEqual(self.client.post(url, self.review_data()).status_code, 403)
        grant(self.viewer, 'assistance.send_referral_email')
        self.assertEqual(self.client.get(url).context['form'].initial['channel'], 'email')
        response = self.client.post(url, self.review_data(), follow=True)
        self.assertContains(response, 'System email history')
        self.assertEqual(ticket.emails.count(), 2)
        service.quick_update_ticket(ticket.pk, user=self.admin, data={'version': 1, 'action': 'closed'})
        self.assertNotContains(self.client.get(url), 'data-referral-reply')

    def test_editable_sender_keeps_prior_messages_and_requires_version_reason_permission(self):
        ticket = self.submit()
        first = ticket.emails.get()
        data = dict(version=1, sender_email='updated@example.invalid', reason='Association address changed')
        with self.assertRaises(PermissionDenied):
            service.set_sender(user=self.viewer, data=data)
        service.set_sender(user=self.admin, data=data)
        with self.assertRaises(ValidationError):
            service.set_sender(user=self.admin, data=data | {'sender_email': 'third@example.invalid'})
        self.review(ticket)
        first.refresh_from_db()
        self.assertEqual(first.sender, 'association@example.invalid')
        self.assertEqual(ticket.emails.order_by('created_at').last().sender, 'updated@example.invalid')
        self.assertEqual(ReferralSettingsEvent.objects.count(), 2)
        self.assertEqual(ReferralSettings.objects.get().version, 2)
        with patch.object(ReferralSettingsEvent.objects, 'create', side_effect=RuntimeError('Audit failure')):
            with self.assertRaises(RuntimeError):
                service.set_sender(user=self.admin, data=data | {'version': 2, 'sender_email': 'third@example.invalid'})
        self.assertEqual(ReferralSettings.objects.get().sender_email, 'updated@example.invalid')

    def test_submitted_data_references_and_histories_cannot_be_rewritten(self):
        ticket = self.submit()
        ticket.reference = 'FORGED'
        for attempt in (lambda: ticket.save(), lambda: ticket.delete(),
                        lambda: ReferralTicket.objects.filter(pk=ticket.pk).update(reference='FORGED'),
                        lambda: ticket.actions.get().save()):
            with self.assertRaises(PermissionDenied):
                attempt()
        with referral_write():
            with self.assertRaises(PermissionDenied):
                ticket.save(update_fields=['reference'])
            with self.assertRaises(PermissionDenied):
                ticket.save(update_fields=['subject'])
            with self.assertRaises(PermissionDenied):
                ticket.emails.get().save(update_fields=['sender'])
            with self.assertRaises(PermissionDenied):
                ticket.actions.get().save(update_fields=['notes'])

    def test_staff_permissions_separate_view_review_send_evidence_and_configuration(self):
        ticket = self.submit(files=MultiValueDict({'evidence_1': [pdf()]}))
        detail = reverse('assistance:referral_detail', args=[ticket.pk])
        document = reverse('assistance:referral_attachment', args=[ticket.attachments.get().pk])
        settings = reverse('assistance:referral_email_settings')
        self.assertEqual(self.client.get(detail).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(detail).status_code, 200)
        for route in (document, settings):
            self.assertEqual(self.client.get(route).status_code, 403)
        self.assertEqual(self.client.post(detail, self.review_data()).status_code, 403)
        grant(self.viewer, 'assistance.review_referralticket')
        self.assertEqual(self.client.post(detail, self.review_data()).status_code, 403)
        self.assertEqual(self.client.post(detail, self.review_data(channel='online')).status_code, 302)
        self.assertEqual(ticket.emails.count(), 1)
        self.client.force_login(self.admin)
        response = self.client.get(document)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('attachment', response['Content-Disposition'])
        b''.join(response.streaming_content)
        self.assertTrue(ticket.actions.filter(action='evidence_viewed').exists())
        self.assertEqual(self.client.get(settings).status_code, 200)
        response = self.client.post(settings, dict(version=1, sender_email='new@example.invalid', reason='Test UI edit'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReferralSettings.objects.get().sender_email, 'new@example.invalid')

    def test_revoked_staff_permission_is_rechecked_even_for_cached_user(self):
        self.assertTrue(self.admin.has_perm('assistance.configure_referrals'))
        get_user_model().objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            service.set_sender(user=self.admin, data=dict(version=1, sender_email='new@example.invalid', reason='No longer staff'))

    def test_public_new_concern_csrf_private_receipt_and_finish(self):
        client = Client(enforce_csrf_checks=True)
        verify = reverse('assistance:referral_verify')
        apply = reverse('assistance:referral_apply')
        self.assertEqual(client.post(verify, self.verification).status_code, 403)
        page = client.get(verify)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(list(page.context['form'].fields), ['control_number', 'full_name',
            'email', 'subject', 'assistance_type', 'concern', 'request_key'])
        self.assertNotContains(page, 'name="birthdate"')
        self.assertNotContains(page, 'name="contact_number"')
        nav = page.content.decode().split('aria-label="Main navigation"')[1].split('</nav>')[0]
        self.assertEqual(nav.count('aria-current="page"'), 1)
        self.assertRegex(nav, r'<a\b(?=[^>]*href="/resources/")(?=[^>]*aria-current="page")[^>]*>')
        from django.conf import settings
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        headers = dict(HTTP_ORIGIN='http://testserver')
        values = self.verification | {key: value for key, value in self.data.items() if key != 'acknowledgement'}
        values.update(csrfmiddlewaretoken=token, request_key=page.context['form']['request_key'].value())
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(verify, values, **headers)
        self.assertEqual(response.status_code, 302)
        ticket = ReferralTicket.objects.get()
        receipt = reverse('assistance:referral_receipt')
        page = client.get(receipt)
        self.assertContains(page, ticket.short_reference)
        self.assertContains(page, self.data['subject'])
        self.assertContains(page, 'development outbox')
        self.assertIn('no-store', page['Cache-Control'])
        self.assertIn(Client().get(receipt, {'reference': ticket.reference}).status_code, (403, 404))
        self.assertEqual(client.post(reverse('assistance:referral_finish'), {'csrfmiddlewaretoken': token}, **headers).status_code, 302)
        self.assertIn(client.get(receipt).status_code, (403, 404))
        self.assertEqual(client.get(apply).status_code, 302)

    def test_public_guidance_home_and_staff_navigation(self):
        page = self.client.get(reverse('assistance:referral_information'))
        self.assertRedirects(page, reverse('core:resources') + '#referral-support')
        self.assertContains(self.client.get(reverse('core:home')), reverse('core:resources') + '#referral-support')
        resources = self.client.get(reverse('core:resources'))
        self.assertContains(resources, 'Community Assistance Desk')
        self.assertContains(resources, 'New concern')
        self.assertNotContains(resources, 'Online requests are currently unavailable')
        self.assertContains(resources, reverse('assistance:referral_verify'))
        self.assertContains(resources, 'Continue a conversation')
        self.client.force_login(self.admin)
        inbox = self.client.get(reverse('assistance:referral_inbox'))
        self.assertContains(inbox, reverse('assistance:referral_email_settings'))
        self.assertContains(inbox, 'Community Assistance Desk Inbox')

    def test_subject_email_and_concern_reach_private_admin_inbox_and_detail(self):
        self.data['subject'] = 'Medical <script>test</script> concern'
        ticket = self.submit()
        self.client.force_login(self.viewer)
        for url in (reverse('assistance:referral_inbox'), reverse('assistance:referral_detail', args=[ticket.pk])):
            response = self.client.get(url)
            self.assertContains(response, 'Medical &lt;script&gt;test&lt;/script&gt; concern')
            self.assertContains(response, self.data['email'])
            if url == reverse('assistance:referral_detail', args=[ticket.pk]):
                self.assertContains(response, self.data['concern'])
            self.assertNotContains(response, '<script>test</script>')
            self.assertEqual(Client().get(url).status_code, 302)

    @override_settings(REFERRAL_ENABLED=False)
    def test_disabled_public_intake_does_not_write(self):
        self.assertEqual(self.client.get(reverse('assistance:referral_verify')).status_code, 503)
        with self.assertRaises(PermissionDenied):
            self.verified()
        self.assertFalse(ReferralGrant.objects.exists())


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReferralConcurrencyTests(Fixtures, TransactionTestCase):
    def parallel(self, operation):
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(lambda _: worker(), range(2)))

    def test_simultaneous_submission_has_one_ticket_acknowledgment_and_reference(self):
        token = self.verified()
        values = self.parallel(lambda: str(service.submit_ticket(token.pk, self.binding, data=self.data).pk))
        self.assertEqual(values[0], values[1])
        self.assertEqual(ReferralTicket.objects.count(), 1)
        self.assertEqual(ReferralEmail.objects.count(), 1)
        self.assertEqual(ReferralEmailAttempt.objects.count(), 1)

    def test_simultaneous_email_delivery_claims_once(self):
        with patch('assistance.referral_services.transaction.on_commit'):
            ticket = self.submit()
        job = ticket.emails.get()
        results = self.parallel(lambda: deliver_email(job.pk))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(job.attempts.count(), 1)
