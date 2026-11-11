"""Finish security regression: synthetic data in verified disposable MySQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from tempfile import TemporaryDirectory
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.management.base import CommandError
from django.db import close_old_connections, connections
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from core.management.commands.runlocal import validate_plan
from membership.models import MembershipApplication, SubmissionWindow
from members.models import Member
from scripts.durable_test_runner import require_disposable
from . import registration_services as services
from .registration_models import RegistrationAction, RegistrationIntake, RegistrationSubmissionContext
from .registration_views import CONTEXT_KEY, CONFIRMATION_KEY
from .test_registration_intake import synthetic_policy, submitted, upload, staff


class RegistrationFinishTests(TestCase):
    def setUp(self):
        require_disposable()
        self.media = TemporaryDirectory(prefix='finish-private-', dir=settings.MEDIA_ROOT)
        self.addCleanup(self.media.cleanup)
        self.policy = synthetic_policy()
        self.override = override_settings(MEDIA_ROOT=self.media.name, ASSOCIATION_REGISTRATION_POLICY=self.policy)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.apply_url = reverse('membership:registration_apply')
        self.receipt_url = reverse('membership:registration_receipt')
        self.finish_url = reverse('membership:registration_finish')

    def submit(self, browser=None, with_file=False):
        browser = browser or self.client
        response = browser.get(self.apply_url)
        self.assertEqual(response.status_code, 200)
        context_id = response.context['context_id']
        data = {**submitted(), 'context_id': context_id,
                'csrfmiddlewaretoken': browser.cookies['csrftoken'].value}
        if with_file:
            data['voter_certificate'] = upload()
        self.assertEqual(browser.post(self.apply_url, data).status_code, 302)
        return RegistrationIntake.objects.get(context_id=context_id)

    def counters(self):
        return list(SubmissionWindow.objects.order_by('key').values())

    def assert_closed_once(self, intake):
        intake.context.refresh_from_db()
        self.assertIsNotNone(intake.context.revoked_at)
        self.assertEqual(intake.actions.filter(action='submission_context_closed').count(), 1)
        self.assertEqual(Member.objects.count(), 0)
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def exhausted_budget(self, **limits):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(**limits)):
            intake = self.submit()
            session_key = self.client.session.session_key
            counters = self.counters()
            self.assertRedirects(self.client.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)
            self.assertEqual(self.client.post(self.finish_url).status_code, 200)
            self.assert_closed_once(intake)
            self.assertEqual(self.client.session.session_key, session_key)
            self.assertNotIn(CONTEXT_KEY, self.client.session)
            self.assertEqual(self.counters(), counters)
            self.assertEqual(self.client.post(self.finish_url).status_code, 200)
            self.assertEqual(self.client.get(self.apply_url).status_code, 403)
            self.assertRedirects(self.client.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)
            self.assertEqual(self.client.post(self.apply_url,
                {**submitted(), 'context_id': str(intake.context_id)}).status_code, 403)
            self.assertEqual(self.counters(), counters)
            self.assertEqual(RegistrationSubmissionContext.objects.count(), 1)
            self.assertEqual(RegistrationIntake.objects.count(), 1)

    def test_finish_succeeds_with_exhausted_session_budget_without_resetting_it(self):
        self.exhausted_budget(session_attempt_limit=2)

    def test_finish_succeeds_with_exhausted_address_budget_without_resetting_it(self):
        self.exhausted_budget(address_attempt_limit=2)

    def test_finish_keeps_only_issued_reference_and_barangay_instructions(self):
        intake = self.submit()
        receipt = self.client.get(self.receipt_url)
        self.assertContains(receipt, 'Registration submitted')
        self.assertContains(receipt, intake.reference)
        self.assertContains(receipt, 'Barangay Santolan office')
        self.assertContains(receipt, 'Bring your PWD ID Card')
        for _ in range(2):
            response = self.client.post(self.finish_url)
            self.assertContains(response, 'Registration submitted')
            self.assertContains(response, intake.reference)
            self.assertContains(response, 'Barangay Santolan PWD Association Help Desk')
            self.assertNotContains(response, 'Form access closed')
            self.assertNotContains(response, 'Synthetic Applicant')
            self.assertNotContains(response, '1990-01-02')
            self.assertNotContains(response, 'Synthetic address only')
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.session[CONFIRMATION_KEY], intake.reference)
        self.assertNotIn(CONTEXT_KEY, self.client.session)
        self.assertRedirects(self.client.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)
        self.assert_closed_once(intake)

    def test_another_browser_cannot_get_confirmation_by_posting_reference(self):
        intake = self.submit()
        self.client.post(self.finish_url)
        stranger = Client()
        response = stranger.post(self.finish_url, {'reference': intake.reference})
        self.assertNotContains(response, intake.reference)
        self.assertNotContains(response, 'Registration submitted')
        self.assertNotIn(CONFIRMATION_KEY, stranger.session)

    def test_repeated_finish_and_service_retries_preserve_timestamp_and_one_audit(self):
        intake = self.submit()
        binding = services.binding_for(self.client.session.session_key)
        before = self.counters()
        self.assertEqual(self.client.post(self.finish_url).status_code, 200)
        intake.context.refresh_from_db()
        revoked = intake.context.revoked_at
        for _ in range(3):
            self.assertEqual(self.client.post(self.finish_url).status_code, 200)
            services.revoke_context(intake.context_id, binding)
        self.assert_closed_once(intake)
        self.assertEqual(intake.context.revoked_at, revoked)
        self.assertEqual(self.counters(), before)
        self.assertEqual(RegistrationSubmissionContext.objects.count(), 1)

    def test_finish_is_csrf_protected_and_post_only_even_when_exhausted(self):
        browser = Client(enforce_csrf_checks=True)
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(session_attempt_limit=2)):
            intake = self.submit(browser)
            self.assertEqual(browser.post(self.finish_url).status_code, 403)
            self.assertEqual(browser.post(self.finish_url, {'csrfmiddlewaretoken': 'invalid'}).status_code, 403)
            self.assertEqual(browser.get(self.finish_url).status_code, 405)
            intake.context.refresh_from_db()
            self.assertIsNone(intake.context.revoked_at)
            response = browser.post(self.finish_url,
                {'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            self.assert_closed_once(intake)

    def test_finish_reduces_access_when_collection_paused_policy_removed_or_changed(self):
        for policy in (None, synthetic_policy(public_enabled=False),
                       synthetic_policy(form_version='SYNTHETIC-CHANGED')):
            with self.subTest(policy=policy):
                browser = Client()
                intake = self.submit(browser)
                with override_settings(ASSOCIATION_REGISTRATION_POLICY=policy):
                    self.assertEqual(browser.post(self.finish_url).status_code, 200)
                    self.assert_closed_once(intake)
                    self.assertEqual(browser.post(self.finish_url).status_code, 200)
                self.assertRedirects(browser.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)

    def test_expired_owned_context_can_be_revoked_without_extending_access(self):
        intake = self.submit()
        expires = intake.context.expires_at
        binding = services.binding_for(self.client.session.session_key)
        with patch('membership.registration_services.timezone.now', return_value=expires + timedelta(seconds=1)):
            self.assertEqual(self.client.post(self.finish_url).status_code, 200)
        self.assert_closed_once(intake)
        self.assertEqual(intake.context.expires_at, expires)
        with self.assertRaises(PermissionDenied):
            services.receipt_for(intake.context_id, binding)

    def test_no_context_finish_is_generic_and_creates_no_context_or_attempts(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=None), \
                patch('membership.registration_services.revoke_context') as revoke:
            response = self.client.post(self.finish_url, {'reference': 'AMR-' + str(uuid4())})
            self.assertContains(response, 'No submitted registration reference is available in this session.')
            revoke.assert_not_called()
        self.assertEqual(RegistrationSubmissionContext.objects.count(), 0)
        self.assertEqual(SubmissionWindow.objects.count(), 0)
        self.assertEqual(RegistrationAction.objects.count(), 0)

    def test_posted_identifier_cannot_select_another_session_or_reveal_its_record(self):
        victim = Client()
        victim_intake = self.submit(victim)
        own = self.submit()
        response = self.client.post(self.finish_url,
            {'context_id': str(victim_intake.context_id), 'reference': victim_intake.reference})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, victim_intake.reference)
        self.assertNotContains(response, 'Synthetic Applicant')
        self.assert_closed_once(own)
        victim_intake.context.refresh_from_db()
        self.assertIsNone(victim_intake.context.revoked_at)
        self.assertEqual(victim.get(self.receipt_url).status_code, 200)

    def test_foreign_or_malformed_context_denied_even_after_revocation(self):
        intake = self.submit()
        binding = services.binding_for(self.client.session.session_key)
        for revoked in (False, True):
            if revoked:
                services.revoke_context(intake.context_id, binding)
            for key, other_binding in ((intake.context_id, 'different-session'), (uuid4(), binding),
                                       ('not-a-context', binding), (intake.context_id, ''),
                                       (intake.reference, binding)):
                with self.subTest(revoked=revoked, key=key), self.assertRaises(PermissionDenied):
                    services.revoke_context(key, other_binding)
        self.assert_closed_once(intake)

    def test_tampered_server_session_cannot_revoke_a_foreign_context(self):
        victim = Client()
        intake = self.submit(victim)
        other_session = self.client.session
        other_session[CONTEXT_KEY] = str(intake.context_id)
        other_session.save()
        self.assertEqual(self.client.post(self.finish_url).status_code, 403)
        intake.context.refresh_from_db()
        self.assertIsNone(intake.context.revoked_at)

    def test_public_finish_cannot_revoke_staff_assisted_context(self):
        actor = staff('finish_assisted_staff', 'membership.encode_registrationintake')
        context = services.issue_context(services.binding_for('staff-session'), channel='walk_in', user=actor)
        with self.assertRaises(PermissionDenied):
            services.revoke_context(context.pk, services.binding_for('staff-session'))
        context.refresh_from_db()
        self.assertIsNone(context.revoked_at)

    def test_shared_device_and_saved_context_cannot_reopen_previous_form_or_files(self):
        intake = self.submit(with_file=True)
        binding = services.binding_for(self.client.session.session_key)
        document = intake.revisions.get().attachments.get()
        self.assertEqual(self.client.post(self.finish_url).status_code, 200)
        self.assertRedirects(self.client.get(self.receipt_url, {'reference': intake.reference}), reverse('core:membership'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('membership:registration_form',
            args=[intake.reference, 1])).status_code, 302)
        self.assertEqual(self.client.get(reverse('membership:registration_document', args=[document.pk])).status_code, 302)
        self.assertEqual(self.client.get('/media/' + document.file.name).status_code, 404)
        with self.assertRaises(PermissionDenied):
            services.receipt_for(intake.context_id, binding)
        with self.assertRaises(PermissionDenied):
            services.submit_registration(intake.context_id, binding, submitted())
        # The same browser may start a distinct form only through normal gates and
        # budgets. Its new context cannot retrieve the previous person's receipt.
        response = self.client.get(self.apply_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.context['context_id'], str(intake.context_id))
        self.assertNotIn(CONFIRMATION_KEY, self.client.session)
        self.assertRedirects(self.client.get(self.receipt_url), reverse('core:membership'), fetch_redirect_response=False)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertTrue(document.file.storage.exists(document.file.name))

    def test_finish_audit_failure_rolls_back_and_does_not_report_success(self):
        intake = self.submit()
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.finish_url)
        intake.context.refresh_from_db()
        self.assertIsNone(intake.context.revoked_at)
        self.assertIn(CONTEXT_KEY, self.client.session)
        self.assertNotIn(CONFIRMATION_KEY, self.client.session)
        self.assertFalse(intake.actions.filter(action='submission_context_closed').exists())
        self.assertEqual(self.client.post(self.finish_url).status_code, 200)
        self.assert_closed_once(intake)

    def test_unsubmitted_context_can_be_closed_without_creating_intake(self):
        response = self.client.get(self.apply_url)
        key = response.context['context_id']
        response = self.client.post(self.finish_url)
        self.assertContains(response, 'No submitted registration reference is available in this session.')
        self.assertNotContains(response, 'Registration submitted')
        self.assertNotIn(CONFIRMATION_KEY, self.client.session)
        self.assertIsNotNone(RegistrationSubmissionContext.objects.get(pk=key).revoked_at)
        self.assertEqual(RegistrationIntake.objects.count(), 0)
        self.assertEqual(RegistrationAction.objects.count(), 0)


class ConcurrentRegistrationFinishTests(TransactionTestCase):
    def test_concurrent_finish_commits_one_revocation_and_one_audit(self):
        require_disposable()
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            binding = services.binding_for('synthetic-concurrent-finish')
            context = services.issue_context(binding)
            intake = services.submit_registration(context.pk, binding, submitted())
            ready = Barrier(2)

            def finish():
                close_old_connections()
                try:
                    ready.wait(timeout=10)
                    services.revoke_context(context.pk, binding)
                    return True
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(lambda _: finish(), range(2))), [True, True])
            context.refresh_from_db()
            self.assertIsNotNone(context.revoked_at)
            self.assertEqual(intake.actions.filter(action='submission_context_closed').count(), 1)
            self.assertEqual(RegistrationIntake.objects.count(), 1)


class RegistrationStartupDiagnosisTests(SimpleTestCase):
    """Actual guard function; no working DB, migration loader or server invoked."""
    def test_pending_registration_migration_stops_startup(self):
        migration = SimpleNamespace(app_label='membership', name='0006_association_pending_intake')
        with self.assertRaisesMessage(CommandError, 'membership.0006_association_pending_intake'):
            validate_plan([(migration, False)])

    def test_feature_disabled_does_not_defer_registration_schema(self):
        migration = SimpleNamespace(app_label='membership', name='0006_association_pending_intake')
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=None):
            with self.assertRaisesMessage(CommandError, 'No migrations were applied.'):
                validate_plan([(migration, False)])

    def test_existing_reviewed_deferrals_and_empty_plan_are_preserved(self):
        from core.management.commands import runlocal
        plan = [(SimpleNamespace(app_label=app, name=name), False) for app, name in (
            runlocal.DEFERRED, runlocal.FOUNDATION_DEFERRED, runlocal.OBSERVANCE_DEFERRED,
            runlocal.DECISION_DEFERRED, runlocal.OPERATIONAL_DEFERRED)]
        self.assertTrue(validate_plan(plan))
        self.assertFalse(validate_plan([]))
