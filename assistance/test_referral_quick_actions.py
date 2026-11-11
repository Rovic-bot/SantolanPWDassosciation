"""Direct staff actions retain access controls, history and email separation."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.http import QueryDict
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from membership.tests import grant, pdf
from programs.models import ProgramApplication
from .models import AssistanceCase, AssistanceRelease
from . import referral_services as service
from .referral_models import ReferralEmailAttempt, ReferralTicket
from .test_referrals import Fixtures


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class QuickReferralTests(Fixtures, TestCase):
    def act(self, ticket, action, version=0, user=None, **extra):
        return service.quick_update_ticket(ticket.pk, user=user or self.admin,
            data={'action': action, 'version': version, **extra})

    def test_opening_starts_review_and_closing_needs_no_extra_fields_or_email(self):
        ticket = self.submit()
        original = (ticket.reference, ticket.subject, ticket.concern, ticket.member_snapshot)
        with patch('assistance.referral_services.queue_email') as queue:
            self.act(ticket, 'begin_review')
            self.act(ticket, 'closed', version=1)
        queue.assert_not_called()
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version), ('closed', 2))
        self.assertEqual((ticket.reference, ticket.subject, ticket.concern, ticket.member_snapshot), original)
        self.assertEqual(ticket.emails.count(), 1)
        events = list(ticket.actions.filter(action__in=['review_started', 'quick_status_updated']))
        self.assertEqual([(e.status_before, e.status_after) for e in events],
            [('received', 'in_review'), ('in_review', 'closed')])
        self.assertTrue(all(e.actor_id == self.admin.pk and e.notes for e in events))
        self.assertEqual((AssistanceCase.objects.count(), AssistanceRelease.objects.count(),
            ProgramApplication.objects.count()), (0, 0, 0))

    def test_record_reply_needs_only_one_action_and_does_not_claim_delivery(self):
        ticket = self.submit()
        attempts = ReferralEmailAttempt.objects.count()
        with patch('assistance.referral_services.queue_email') as queue:
            self.act(ticket, 'begin_review')
            self.act(ticket, 'record_reply', version=1)
            self.act(ticket, 'record_reply', version=1)
        queue.assert_not_called()
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version), ('in_review', 2))
        event = ticket.actions.get(action='quick_gmail_reply_recorded')
        self.assertEqual((event.actor_id, event.channel, event.member_message), (self.admin.pk, 'email', ''))
        self.assertEqual(ticket.emails.count(), 1)
        self.assertEqual(ReferralEmailAttempt.objects.count(), attempts)

    def test_exact_retry_is_idempotent_but_changed_stale_action_is_rejected(self):
        ticket = self.submit()
        self.act(ticket, 'begin_review')
        self.act(ticket, 'begin_review')
        for action in ('closed', 'record_reply', 'in_review'):
            with self.assertRaises(ValidationError):
                self.act(ticket, action)
        grant(self.viewer, 'assistance.review_referralticket')
        self.act(ticket, 'begin_review', user=self.viewer)
        self.assertEqual(ticket.actions.count(), 2)

    def test_closed_ticket_cannot_be_reopened_but_duplicate_close_is_safe(self):
        ticket = self.submit()
        self.act(ticket, 'closed')
        self.act(ticket, 'closed')
        self.act(ticket, 'begin_review')
        for action in ('in_review', 'needs_information', 'referred', 'record_reply'):
            with self.assertRaises(ValidationError):
                self.act(ticket, action, version=1)
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version), ('closed', 1))
        self.assertEqual(ticket.actions.count(), 2)

    def test_review_and_reply_permissions_are_separate_and_rechecked(self):
        ticket = self.submit()
        with self.assertRaises(PermissionDenied):
            self.act(ticket, 'begin_review', user=self.viewer)
        grant(self.viewer, 'assistance.review_referralticket')
        self.act(ticket, 'begin_review', user=self.viewer)
        with self.assertRaises(PermissionDenied):
            self.act(ticket, 'record_reply', version=1, user=self.viewer)
        grant(self.viewer, 'assistance.send_referral_email')
        self.assertTrue(self.viewer.has_perm('assistance.send_referral_email'))
        self.viewer.user_permissions.clear()
        grant(self.viewer, 'accounts.access_dashboard', 'assistance.view_referralticket', 'assistance.review_referralticket')
        with self.assertRaises(PermissionDenied):
            self.act(ticket, 'record_reply', version=1, user=self.viewer)

    def test_unknown_actions_duplicate_values_and_extra_fields_do_not_mutate(self):
        ticket = self.submit()
        for data in ({'action': 'approved', 'version': 0},
                     {'action': 'closed', 'version': -1},
                     {'action': 'closed', 'version': 0, 'email': 'injected@example.invalid'},
                     {'action': 'record_reply'},
                     QueryDict('action=closed&action=record_reply&version=0')):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                service.quick_update_ticket(ticket.pk, user=self.admin, data=data)
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version, ticket.actions.count()), ('received', 0, 1))

    def test_history_failure_rolls_back_direct_status_and_reply_actions(self):
        ticket = self.submit()
        for action in ('begin_review', 'record_reply'):
            with patch('assistance.referral_services.record_action', side_effect=RuntimeError('Synthetic audit failure')):
                with self.assertRaises(RuntimeError):
                    self.act(ticket, action)
            ticket.refresh_from_db()
            self.assertEqual((ticket.status, ticket.version, ticket.actions.count()), ('received', 0, 1))
            self.assertEqual(ticket.emails.count(), 1)

    def test_detail_composer_and_direct_posts_require_csrf(self):
        ticket = self.submit()
        url = reverse('assistance:referral_detail', args=[ticket.pk])
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        inbox = browser.get(reverse('assistance:referral_inbox'))
        self.assertNotContains(inbox, 'data-record-full-page')
        self.assertContains(inbox, 'View ticket')
        response = browser.get(url)
        for field in ('name="notes"', 'name="member_message"',
                    'name="channel"', 'name="sender_version"'):
            self.assertContains(response, field)
        self.assertContains(response, 'Reply to this concern')
        self.assertContains(response, 'data-referral-open')
        self.assertContains(response, 'data-referral-reply')
        self.assertEqual(browser.post(url, {'action': 'begin_review', 'version': 0}).status_code, 403)
        response = browser.post(url, {'action': 'begin_review', 'version': 0,
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'in_review')
        response = browser.get(url)
        self.assertNotContains(response, 'data-referral-open')
        self.assertContains(response, 'value="closed"')
        self.assertEqual(browser.post(url, {'action': 'closed', 'version': 1,
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value}).status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'closed')
        browser.force_login(self.viewer)
        self.assertNotContains(browser.get(url), 'name="action"')
        self.assertEqual(browser.post(url, {'action': 'closed', 'version': 2,
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value}).status_code, 403)

    def test_view_ticket_opens_for_review_and_read_only_views_do_not_write(self):
        ticket = self.submit()
        detail = reverse('assistance:referral_detail', args=[ticket.pk])
        inbox = reverse('assistance:referral_inbox')
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(inbox), 'value="begin_review"')
        self.assertNotContains(self.client.get(detail), 'data-referral-open')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(inbox), 'data-record-dialog=')
        self.assertContains(self.client.get(detail), 'data-referral-open')
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version), ('received', 0))
        response = self.client.post(detail, {'action': 'begin_review', 'version': 0}, follow=True)
        self.assertContains(response, 'In review')
        self.assertNotContains(response, 'data-referral-open')
        self.client.post(detail, {'action': 'begin_review', 'version': 0})
        self.assertEqual(ticket.actions.filter(action='review_started').count(), 1)
        self.assertEqual(ticket.emails.count(), 1)

    def test_opening_retains_historical_processing_status_and_invalid_manual_buttons_fail(self):
        ticket = self.submit()
        self.review(ticket, channel='onsite')
        self.review(ticket, version=1, status='needs_information', channel='onsite')
        count = ticket.actions.count()
        self.act(ticket, 'begin_review')
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version, ticket.actions.count()), ('needs_information', 2, count))
        for action in ('in_review', 'needs_information', 'referred'):
            with self.assertRaises(ValidationError):
                self.act(ticket, action, version=2)

    def test_inbox_totals_and_reference_subject_member_type_status_filters(self):
        medical = self.submit()
        self.data.update(subject='School transport guidance', assistance_type='educational')
        school = self.submit()
        self.act(school, 'closed')
        self.client.force_login(self.viewer)
        url = reverse('assistance:referral_inbox')
        response = self.client.get(url)
        self.assertEqual(response.context['totals'], {'total': 2, 'received': 1, 'closed': 1})
        for parameters, expected in (({'q': 'school'}, [school]),
                ({'q': medical.reference.lower()}, [medical]),
                ({'q': medical.full_name, 'type': 'medical'}, [medical]),
                ({'status': 'closed', 'type': 'educational'}, [school]),
                ({'status': 'received', 'type': 'educational'}, [])):
            with self.subTest(parameters=parameters):
                self.assertEqual(list(self.client.get(url, parameters).context['page']), expected)
        self.assertContains(response, 'View ticket')
        self.assertNotContains(response, 'Record reply / update status')
        self.assertNotContains(response, 'https://mail.google.com/mail/')

    def test_inline_evidence_preserves_permission_checks_audit_and_private_headers(self):
        ticket = self.submit(files=MultiValueDict({'evidence_1': [pdf()]}))
        item = ticket.attachments.get()
        url = reverse('assistance:referral_attachment', args=[item.pk])
        self.assertEqual(self.client.get(url, {'view': 'inline'}).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url, {'view': 'inline'}).status_code, 403)
        page = self.client.get(reverse('assistance:referral_detail', args=[ticket.pk]))
        self.assertNotContains(page, url)
        grant(self.viewer, 'assistance.view_referral_documents')
        for params, disposition in (({'view': 'inline'}, 'inline'), ({}, 'attachment')):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response['Content-Disposition'].startswith(disposition))
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertIn('sandbox', response['Content-Security-Policy'])
            b''.join(response.streaming_content)
        self.assertEqual(ticket.actions.filter(action='evidence_viewed').count(), 2)
        page = self.client.get(reverse('assistance:referral_detail', args=[ticket.pk]))
        self.assertContains(page, url + '?view=inline')
        self.assertNotContains(page, item.file.name)


@override_settings(REFERRAL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class QuickReferralConcurrencyTests(Fixtures, TransactionTestCase):
    def parallel_actions(self, ticket, actions, version=0):
        barrier = Barrier(2)
        def worker(action):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                try:
                    result = service.quick_update_ticket(ticket.pk, user=self.admin,
                        data={'action': action, 'version': version})
                    return result.version
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker, actions))

    def test_double_click_creates_one_update(self):
        ticket = self.submit()
        service.quick_update_ticket(ticket.pk, user=self.admin, data={'action': 'begin_review', 'version': 0})
        self.assertEqual(self.parallel_actions(ticket, ['record_reply', 'record_reply'], version=1), [2, 2])
        ticket.refresh_from_db()
        self.assertEqual(ticket.version, 2)
        self.assertEqual(ticket.actions.filter(action='quick_gmail_reply_recorded').count(), 1)
        self.assertEqual(ticket.emails.count(), 1)

    def test_competing_status_buttons_cannot_overwrite_each_other(self):
        ticket = self.submit()
        service.quick_update_ticket(ticket.pk, user=self.admin, data={'action': 'begin_review', 'version': 0})
        results = self.parallel_actions(ticket, ['record_reply', 'closed'], version=1)
        self.assertCountEqual(results, [2, 'stale'])
        ticket.refresh_from_db()
        self.assertEqual(ticket.version, 2)
        self.assertEqual(ticket.actions.filter(action__in=['quick_status_updated', 'quick_gmail_reply_recorded']).count(), 1)

    def test_simultaneous_opens_start_review_once(self):
        ticket = self.submit()
        self.assertEqual(self.parallel_actions(ticket, ['begin_review', 'begin_review']), [1, 1])
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.version), ('in_review', 1))
        self.assertEqual(ticket.actions.filter(action='review_started').count(), 1)
