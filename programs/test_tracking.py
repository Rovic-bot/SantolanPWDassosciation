from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from django.conf import settings
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from members.tests import create_member
from .models import Program, ProgramApplication, VerificationWindow
from .tests import create_program
from .tracking_services import (SESSION_KEY, VERIFICATION_FAILED, progress_summary,
    reserve_tracking_attempt)


@override_settings(PROGRAM_TRACKING_ENABLED=True, PROGRAM_TRACKING_QR_ENABLED=True,
    PROGRAM_TRACKING_GRANT_SECONDS=900, PROGRAM_VERIFICATION_MEMBER_LIMIT=100,
    PROGRAM_VERIFICATION_ADDRESS_LIMIT=250)
class ApplicationTrackingTests(TestCase):
    def setUp(self):
        self.member = create_member('SYNTHETIC-TRACKING-MEMBER')
        self.member.refresh_from_db()
        self.program = create_program()
        self.application = ProgramApplication.objects.create(program=self.program, member=self.member,
            public_reference='SPA-LEGACY-TRACKING-001', answers={'1': 'PRIVATE-APPLICATION-ANSWER'},
            source_snapshot={'assessment': 'PRIVATE-ASSESSMENT-NOTE'})
        self.verify_url = reverse('programs:tracking')
        self.progress_url = reverse('programs:tracking_progress')
        self.finish_url = reverse('programs:tracking_finish')
        self.qr_url = reverse('programs:tracking_receipt_qr', args=[self.program.pk])
        self.data = {'reference': self.application.public_reference}

    def verify(self, client=None, **overrides):
        return (client or self.client).post(self.verify_url, {**self.data, **overrides})

    def receipt_session(self):
        session = self.client.session
        session['program_receipt'] = str(self.application.pk)
        session.save()

    def assert_private(self, response):
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('private', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')

    def test_reference_qr_parameter_or_legacy_token_alone_does_not_grant_access(self):
        for query in ({'reference': self.application.public_reference},
                {'application': str(self.application.pk)}, {'token': self.application.status_token}):
            response = self.client.get(self.verify_url, query)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(self.client.session.get(SESSION_KEY))
            self.assertNotContains(response, self.program.name)
            self.assertRedirects(self.client.get(self.progress_url, query), self.verify_url)

    def test_verification_returns_only_allowlisted_progress_without_changing_records(self):
        before = ProgramApplication.objects.values().get(pk=self.application.pk)
        member_before = Member.objects.values().get(pk=self.member.pk)
        self.assertRedirects(self.verify(), self.progress_url)
        response = self.client.get(self.progress_url)
        self.assertContains(response, self.application.public_reference)
        self.assertContains(response, 'Received')
        self.assertContains(response, reverse('core:contact'))
        self.assert_private(response)
        self.assertEqual(set(response.context['progress']), {'reference', 'program_name', 'submitted_at',
            'status_label', 'explanation', 'next_steps', 'program_cancelled'})
        for secret in (self.member.full_name, self.member.control_number, self.member.contact_number,
                self.application.status_token, 'PRIVATE-APPLICATION-ANSWER', 'PRIVATE-ASSESSMENT-NOTE'):
            self.assertNotContains(response, secret)
        self.assertEqual(ProgramApplication.objects.values().get(pk=self.application.pk), before)
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), member_before)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_unknown_reference_discloses_no_record_details(self):
        response = self.verify(reference='SPA-NOT-ISSUED')
        self.assertContains(response, VERIFICATION_FAILED)
        self.assertIsNone(self.client.session.get(SESSION_KEY))
        self.assertNotContains(response, self.program.name)

    def test_reference_is_the_only_visible_tracking_input(self):
        response = self.client.get(self.verify_url)
        self.assertEqual(list(response.context['form'].fields), ['reference'])
        self.assertNotContains(response, 'PWD control number')
        self.assertNotContains(response, 'Date of birth')
        self.assertRedirects(self.client.post(self.verify_url, self.data), self.progress_url)
        self.assertRedirects(Client().get(self.progress_url), self.verify_url)

    def test_reference_case_and_surrounding_spaces_are_normalized(self):
        self.assertRedirects(self.verify(reference='  '+self.application.public_reference.lower()+'  '), self.progress_url)

    def test_database_accent_equivalence_does_not_match_a_different_reference(self):
        self.assertContains(self.verify(reference='SP\u00c1-LEGACY-TRACKING-001'), VERIFICATION_FAILED)

    def test_reference_required_and_removed_personal_inputs_are_not_collected(self):
        for data in ({}, {'reference': ''}):
            self.assertEqual(self.client.post(self.verify_url, data).status_code, 200)
            self.assertIsNone(self.client.session.get(SESSION_KEY))
        self.assertRedirects(self.verify(full_name='Ignored', contact_number='invalid', birthdate='invalid'), self.progress_url)

    def test_success_rotates_session_key_and_failed_retry_revokes_prior_access(self):
        session = self.client.session
        session['unrelated-feature'] = 'retained'
        session.save()
        old_key = session.session_key
        self.verify()
        self.assertNotEqual(self.client.session.session_key, old_key)
        stale = Client()
        stale.cookies[settings.SESSION_COOKIE_NAME] = old_key
        self.assertRedirects(stale.get(self.progress_url), self.verify_url)
        self.verify(reference='SPA-NOT-ISSUED')
        self.assertRedirects(self.client.get(self.progress_url), self.verify_url)
        self.assertEqual(self.client.session['unrelated-feature'], 'retained')

    def test_expired_or_malformed_grants_are_cleared(self):
        self.verify()
        good = self.client.session[SESSION_KEY]
        malformed = [None, 'not-a-grant', {}, {**good, 'application': 'not-a-uuid'},
            {**good, 'expires': 0}, {**good, 'expires': 'NaN'}, {**good, 'expires': 'Infinity'},
            {**good, 'identity': 'wrong'}, {**good, 'identity': {}}, {**good, 'expires': []}]
        for value in malformed:
            session = self.client.session
            session[SESSION_KEY] = value
            session.save()
            self.assertRedirects(self.client.get(self.progress_url), self.verify_url)
            self.assertIsNone(self.client.session.get(SESSION_KEY))

    def test_profile_edits_do_not_break_tracking_but_archiving_revokes_it(self):
        self.verify()
        Member.objects.filter(pk=self.member.pk).update(contact_number='09998887777')
        self.assertContains(self.client.get(self.progress_url), 'Received')
        Member.objects.filter(pk=self.member.pk).update(contact_number=self.member.contact_number)
        self.verify()
        Member.objects.filter(pk=self.member.pk).update(version=self.member.version + 1)
        self.assertContains(self.client.get(self.progress_url), 'Received')
        self.verify()
        Member.objects.filter(pk=self.member.pk).update(is_active=False, archived_at=timezone.now())
        self.assertRedirects(self.client.get(self.progress_url), self.verify_url)
        self.assertContains(self.verify(), VERIFICATION_FAILED)

    def test_grant_cannot_be_transferred_to_another_application(self):
        other = ProgramApplication.objects.create(program=create_program(), member=self.member,
            public_reference='SPA-OTHER-PROGRAM')
        self.verify()
        session = self.client.session
        session[SESSION_KEY] = {**session[SESSION_KEY], 'application': str(other.pk)}
        session.save()
        self.assertRedirects(self.client.get(self.progress_url), self.verify_url)

    def test_all_processing_states_have_safe_messages_and_refresh_without_reverification(self):
        self.verify()
        expected = {'PENDING_PHOTO_VERIFICATION': 'Received', 'NEEDS_INFORMATION': 'Clarification needed',
            'PHOTO_VERIFIED': 'Photo verified', 'ELIGIBILITY_REVIEW': 'Under review', 'ELIGIBLE': 'You are now eligible',
            'EWAF_READY': 'You are now eligible', 'EWAF_PROCESSED': 'You are now eligible', 'RANKED': 'You are now eligible',
            'WAITLISTED': 'You are on the waitlist', 'VERIFICATION_FAILED': 'Verification unsuccessful',
            'INELIGIBLE': 'You are not eligible', 'SELECTED': 'You have been selected',
            'NOT_SELECTED': 'You were not selected', 'COMPLETED': 'Assistance released', 'CLOSED': 'Application closed'}
        self.assertEqual(set(expected), set(ProgramApplication.Status.values))
        for status, label in expected.items():
            ProgramApplication.objects.filter(pk=self.application.pk).update(status=status)
            response = self.client.get(self.progress_url)
            self.assertEqual(response.context['progress']['status_label'], label)
            self.assertContains(response, response.context['progress']['next_steps'])
            self.assertNotContains(response, f'>{status}<')
            self.assertNotContains(response, 'PRIVATE-ASSESSMENT-NOTE')

    def test_tracking_survives_program_deadline_or_archival_and_member_inactivity(self):
        Program.objects.filter(pk=self.program.pk).update(status='archived',
            registration_closes_at=timezone.now() - timedelta(hours=1))
        Member.objects.filter(pk=self.member.pk).update(is_active=False)
        self.assertRedirects(self.verify(), self.progress_url)
        self.assertContains(self.client.get(self.progress_url), 'Received')
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_cancelled_program_has_notice_and_unknown_state_does_not_guess_a_decision(self):
        Program.objects.filter(pk=self.program.pk).update(status='cancelled')
        self.verify()
        response = self.client.get(self.progress_url)
        self.assertContains(response, 'program is marked as cancelled')
        record = {'status': 'FUTURE_UNKNOWN_STATUS', 'public_reference': 'TEST', 'program__name': 'Test',
            'program__status': 'published', 'submitted_at': timezone.now()}
        self.assertEqual(progress_summary(record)['status_label'], 'Contact the Help Desk')

    @override_settings(PROGRAM_VERIFICATION_MEMBER_LIMIT=2)
    def test_attempts_are_limited_across_browser_sessions_and_raw_identifiers_are_not_stored(self):
        for _ in range(2):
            self.assertEqual(self.verify(Client()).status_code, 302)
        response = self.verify(Client())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], str(settings.PROGRAM_VERIFICATION_WINDOW_SECONDS))
        self.assert_private(response)
        for key in VerificationWindow.objects.values_list('key', flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn(self.member.control_number, key)
            self.assertNotIn(self.application.public_reference, key)

    @override_settings(PROGRAM_VERIFICATION_ADDRESS_LIMIT=1)
    def test_malformed_attempts_and_forwarded_header_changes_cannot_bypass_address_limit(self):
        self.client.post(self.verify_url, {})
        response = Client().post(self.verify_url, self.data, HTTP_X_FORWARDED_FOR='192.0.2.9')
        self.assertEqual(response.status_code, 429)

    def test_throttle_storage_failure_fails_closed(self):
        with patch('programs.tracking_services.reserve_windows', side_effect=OperationalError('unavailable')):
            self.assertFalse(reserve_tracking_attempt('TEST', '127.0.0.1'))

    def test_real_csrf_verification_finish_and_method_restrictions(self):
        client = Client(enforce_csrf_checks=True)
        form = client.get(self.verify_url)
        self.assert_private(form)
        self.assertEqual(self.verify(client).status_code, 403)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post(self.verify_url, {**self.data, 'csrfmiddlewaretoken': token},
            HTTP_ORIGIN='http://testserver')
        self.assertRedirects(response, self.progress_url)
        self.assertEqual(client.get(self.finish_url).status_code, 405)
        self.assertEqual(client.post(self.finish_url).status_code, 403)
        self.assertContains(client.get(self.progress_url), 'Received')
        self.assertRedirects(client.post(self.finish_url, {'csrfmiddlewaretoken': token},
            HTTP_ORIGIN='http://testserver'), self.verify_url)
        self.assertRedirects(client.get(self.progress_url), self.verify_url)
        self.assertEqual(client.post(self.progress_url).status_code, 403)
        self.assertEqual(self.client.post(self.progress_url).status_code, 405)

    def test_feature_switch_removes_entry_points_and_revokes_access(self):
        self.verify()
        with override_settings(PROGRAM_TRACKING_ENABLED=False):
            self.assertEqual(self.client.get(self.progress_url).status_code, 503)
            self.assertIsNone(self.client.session.get(SESSION_KEY))
            self.assertEqual(self.verify().status_code, 503)
            self.assertEqual(self.client.get(self.qr_url).status_code, 404)
            for route in ('core:home', 'core:programs', 'core:resources'):
                self.assertNotContains(self.client.get(reverse(route)), f'href="{self.verify_url}"')

    def test_receipt_qr_and_tracking_link_have_reference_but_never_a_secret(self):
        self.receipt_session()
        receipt = self.client.get(reverse('programs:submitted', args=[self.program.pk]))
        self.assertContains(receipt, self.qr_url)
        self.assertContains(receipt, 'Track this application')
        self.assertNotContains(receipt, self.application.status_token)
        import qrcode
        original = qrcode.make
        with patch('programs.tracking_views.qrcode.make', wraps=original) as make:
            response = self.client.get(self.qr_url)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assert_private(response)
        Image.open(BytesIO(response.content)).verify()
        payload = make.call_args.args[0]
        self.assertEqual(urlsplit(payload).path, self.verify_url)
        self.assertEqual(parse_qs(urlsplit(payload).query), {'reference': [self.application.public_reference]})
        self.assertNotIn(self.application.status_token, payload)
        self.assertNotIn(self.member.control_number, payload)
        stranger = Client()
        self.assertEqual(stranger.get(payload).status_code, 200)
        self.assertRedirects(stranger.get(self.progress_url), self.verify_url)

    def test_qr_is_receipt_session_bound_and_cannot_be_requested_by_reference(self):
        self.assertEqual(self.client.get(self.qr_url, {'reference': self.application.public_reference}).status_code, 404)
        self.receipt_session()
        wrong_program = reverse('programs:tracking_receipt_qr', args=[create_program().pk])
        self.assertEqual(self.client.get(wrong_program).status_code, 404)
        session = self.client.session
        session['program_receipt'] = 'malformed'
        session.save()
        self.assertEqual(self.client.get(self.qr_url).status_code, 404)

    def test_qr_can_be_disabled_independently_while_tracking_remains_available(self):
        self.receipt_session()
        with override_settings(PROGRAM_TRACKING_QR_ENABLED=False):
            self.assertEqual(self.client.get(self.qr_url).status_code, 404)
            receipt = self.client.get(reverse('programs:submitted', args=[self.program.pk]))
            self.assertNotContains(receipt, self.qr_url)
            self.assertContains(receipt, 'Track this application')
            self.assertRedirects(self.verify(), self.progress_url)

    def test_portal_shortcuts_link_to_the_verification_step(self):
        # The redesigned Home routes visitors through the Resources section.
        self.assertContains(self.client.get(reverse('core:home')), f'href="{reverse("core:resources")}"')
        for route in ('core:programs', 'core:resources'):
            response = self.client.get(reverse(route))
            self.assertContains(response, f'href="{self.verify_url}" data-tracking-open')
            self.assertContains(response, 'data-tracking-dialog')
        self.assertContains(self.client.get(reverse('programs:detail', args=[self.program.pk])),
            f'href="{self.verify_url}" data-tracking-open')

