"""One-click manual PRPWD confirmation and approval, using disposable data."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from members.models import Member
from . import services
from .forms import QuickApprovalForm
from .models import MembershipEvent
from . import tests as membership_tests
from .tests import grant
from .test_registration_handoff import HandoffHelpers


class ApprovalFixtures:
    setUp = membership_tests.MembershipTests.setUp
    data = membership_tests.MembershipTests.data
    form = membership_tests.MembershipTests.form
    application = membership_tests.MembershipTests.application

    def approve(self, application, **changes):
        return services.approve_checked_application(application.reference,
            **dict(user=self.admin, version=application.version, verified=True, **changes))


class QuickApprovalTests(ApprovalFixtures, TestCase):
    def test_checked_approval_records_verification_and_member_with_automatic_history(self):
        application = self.application()
        result = self.approve(application)
        self.assertEqual(result.status, 'approved')
        self.assertTrue(result.prpwd_verified)
        self.assertEqual(result.version, 2)
        self.assertEqual(result.prpwd_verified_by, self.admin)
        self.assertEqual(result.verification_url, self.policy.prpwd_url)
        self.assertEqual(Member.objects.get().control_number, application.control_number)
        self.assertEqual(list(result.events.values_list('action', flat=True)),
                         ['onsite_encoded', 'prpwd_verified', 'approved'])
        self.assertIn('Administrator', result.verification_notes)
        self.assertIn('Administrator', result.decision_notes)
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertEqual(Member.objects.count(), 1)

    def test_confirmation_stale_version_and_missing_link_do_not_save_partial_verification(self):
        application = self.application()
        for changes in ({'verified':False}, {'version':100}):
            with self.assertRaises(ValidationError):
                services.approve_checked_application(application.reference,
                    **({'user':self.admin, 'version':0, 'verified':True} | changes))
        self.policy.prpwd_url = ''
        self.policy.save()
        with self.assertRaises(ValidationError):
            self.approve(application)
        application.refresh_from_db()
        self.assertEqual(application.version, 0)
        self.assertIsNone(application.prpwd_verified)
        self.assertEqual(application.events.count(), 1)

    def test_missing_document_rolls_back_verification_and_approval(self):
        application = self.application()
        application.documents.first().file.delete(save=False)
        with self.assertRaises(ValidationError):
            self.approve(application)
        application.refresh_from_db()
        self.assertIsNone(application.prpwd_verified)
        self.assertEqual(application.status, 'pending')
        self.assertFalse(Member.objects.exists())
        self.assertEqual(application.events.count(), 1)

    def test_decision_audit_failure_rolls_back_both_steps(self):
        application = self.application()
        record = services.record_event
        def fail(application, action, *args, **kwargs):
            if action == 'approved':
                raise RuntimeError('Synthetic decision audit failure')
            return record(application, action, *args, **kwargs)
        with patch.object(services, 'record_event', side_effect=fail), self.assertRaises(RuntimeError):
            self.approve(application)
        application.refresh_from_db()
        self.assertEqual(application.version, 0)
        self.assertIsNone(application.prpwd_verified)
        self.assertFalse(Member.objects.exists())
        self.assertEqual(MembershipEvent.objects.count(), 1)

    def test_both_fresh_permissions_are_required(self):
        application = self.application()
        grant(self.viewer, 'membership.verify_membershipapplication', 'membership.decide_membershipapplication')
        self.assertTrue(self.viewer.has_perm('membership.decide_membershipapplication'))
        self.viewer.user_permissions.remove(Permission.objects.get(codename='decide_membershipapplication'))
        with self.assertRaises(PermissionDenied):
            services.approve_checked_application(application.reference, user=self.viewer, version=0, verified=True)
        self.assertFalse(Member.objects.exists())
        application.refresh_from_db()
        self.assertIsNone(application.prpwd_verified)

    def test_http_checkbox_approval_csrf_and_removed_fields(self):
        application = self.application()
        url = reverse('membership:detail', args=[application.reference])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        page = client.get(url)
        self.assertContains(page, 'Approve membership')
        self.assertContains(page, 'type="checkbox"')
        for removed in ('Select a result', 'Verification notes', 'Decision notes', 'Select a decision', 'Save verification'):
            self.assertNotContains(page, removed)
        data = {'action':'approve', 'version':0, 'verified':'on'}
        self.assertEqual(client.post(url, data).status_code, 403)
        token = client.cookies['csrftoken'].value
        response = client.post(url, data | {'csrfmiddlewaretoken':token})
        self.assertRedirects(response, url)
        self.assertEqual(Member.objects.count(), 1)

    def test_form_rejects_injected_notes_and_duplicate_values(self):
        from django.http import QueryDict
        self.assertFalse(QuickApprovalForm({'version':0, 'verified':'on', 'notes':'Override'}).is_valid())
        self.assertFalse(QuickApprovalForm(QueryDict('version=0&version=1&verified=on')).is_valid())
        self.assertFalse(QuickApprovalForm({'version':0}).is_valid())


class LinkedQuickApprovalTests(HandoffHelpers, TestCase):
    def test_linked_intake_retains_both_review_audits(self):
        self.setup_handoff()
        intake = self.make()
        application = self.prepare(intake)
        approved = services.approve_checked_application(application.reference, user=self.actor,
            version=application.version, verified=True)
        self.assertEqual(approved.status, 'approved')
        self.assertEqual(intake.actions.filter(action='membership_verification').count(), 1)
        self.assertEqual(intake.actions.filter(action='membership_approved').count(), 1)


class QuickApprovalConcurrencyTests(ApprovalFixtures, TransactionTestCase):
    def test_simultaneous_clicks_create_one_member_and_one_pair_of_audits(self):
        application = self.application()
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    self.approve(application)
                    return 'approved'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: submit(), range(2))), ['approved','stale'])
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(application.events.filter(action='prpwd_verified').count(), 1)
        self.assertEqual(application.events.filter(action='approved').count(), 1)


from ewaf import test_membership_writers as source_tests
from ewaf.test_source_writers import SourceHelpers


class QuickApprovalSourceTests(SourceHelpers, TransactionTestCase):
    setUp = source_tests.MembershipWriterTests.setUp
    form = source_tests.MembershipWriterTests.form
    submit = source_tests.MembershipWriterTests.submit
    batches = source_tests.MembershipWriterTests.batches

    def test_combined_approval_retains_native_source_batches(self):
        from ewaf.generation_models import SourceMutationBatch
        from ewaf.generation_services import _validate_batch
        application = self.submit()
        services.approve_checked_application(application.reference, user=self.officer,
            version=application.version, verified=True, source_expected={})
        self.assertTrue(Member.objects.filter(application=application).exists())
        batches = list(SourceMutationBatch.objects.filter(source_kind='membership').order_by('pk'))
        self.assertEqual(len(batches), 2)
        self.assertEqual(sorted(len(row.source_audits) for row in batches), [1, 2])
        for row in batches:
            self.assertEqual(row.scope_count, 0)
            _validate_batch(row)
        self.assert_transition(1)

    def test_late_combined_batch_failure_rolls_back_verification_and_decision(self):
        from ewaf import shared_invalidation
        application = self.submit()
        with patch.object(shared_invalidation, 'finish', side_effect=ValidationError('Synthetic combined batch failure')), self.assertRaises(ValidationError):
            services.approve_checked_application(application.reference, user=self.officer,
                version=application.version, verified=True, source_expected={})
        application.refresh_from_db()
        self.assertIsNone(application.prpwd_verified)
        self.assertEqual(application.version, 0)
        self.assertFalse(Member.objects.filter(application=application).exists())
        self.batches(1)
