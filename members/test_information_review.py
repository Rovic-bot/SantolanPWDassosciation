from unittest.mock import patch
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.db import close_old_connections
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from membership.test_registration_intake import synthetic_policy, submitted
from membership import registration_services
from programs.models import ProgramApplication
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable
from .tests import create_member
from .models import Member
from .review_models import InformationReview, InformationReviewAction
from . import review_services as services


def synthetic_review_policy(**changes):
    return {'staff_enabled': True, 'authority': 'SYNTHETIC ONLY', 'identity_procedure': 'SYNTHETIC ONLY',
        'staff_assignment': 'SYNTHETIC ONLY', 'privacy_retention': 'SYNTHETIC ONLY',
        'review_procedure': 'SYNTHETIC ONLY', **changes}


def intake_data(**changes):
    return {'request_key': str(uuid4()), 'kind': 'information', 'trigger': 'reported_change',
        'declaration': 'no_change', 'concern': 'Synthetic concern', 'identity_basis': 'Synthetic onsite check', **changes}


def finding_data(**changes):
    return {'version': 0, 'state': 'findings_recorded', 'reason': 'Synthetic review reason',
        'previous_values': 'Earlier reported value', 'reported_values': 'New reported value',
        'findings': 'Unaccepted synthetic assessment note', 'observed_on': timezone.localdate().isoformat(), **changes}


class InformationReviewTests(TestCase):
    def setUp(self):
        require_disposable()
        setting = override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy())
        setting.enable()
        self.addCleanup(setting.disable)
        self.actor = get_user_model().objects.create_superuser('synthetic_review_admin')
        self.member = create_member('SYNTHETIC-REVIEW')
        self.url = reverse('members:reviews', args=[self.member.pk])
        self.client.force_login(self.actor)

    def make(self, **changes):
        return services.open_review(self.member.pk, user=self.actor, data=intake_data(**changes))

    def application(self, member=None, status='SELECTED'):
        return ProgramApplication.objects.create(member=member or self.member, program=create_program(),
            public_reference='TEST-' + uuid4().hex, status=status)

    def test_disabled_contract_blocks_direct_routes_before_new_record_query(self):
        with override_settings(INFORMATION_REVIEW_POLICY=None), patch.object(InformationReview.objects, 'get', side_effect=AssertionError):
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.client.post(self.url, intake_data()).status_code, 404)
        for key in ('authority', 'identity_procedure', 'staff_assignment', 'privacy_retention', 'review_procedure'):
            with override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy(**{key: ''})):
                with self.assertRaises(Http404):
                    self.make()

    def test_no_change_is_separate_and_identical_retry_creates_one_concern(self):
        before = Member.objects.filter(pk=self.member.pk).values().get()
        original = self.member.application.prpwd_verified_at
        data = intake_data()
        record = services.open_review(self.member.pk, user=self.actor, data=data)
        self.assertEqual(services.open_review(self.member.pk, user=self.actor, data=data).pk, record.pk)
        self.assertEqual(record.actions.count(), 1)
        self.assertEqual(Member.objects.filter(pk=self.member.pk).values().get(), before)
        self.member.application.refresh_from_db()
        self.assertEqual(self.member.application.prpwd_verified_at, original)
        with self.assertRaises(ValidationError):
            services.open_review(self.member.pk, user=self.actor, data={**data, 'concern': 'Changed replay'})

    def test_findings_preserve_original_notes_and_do_not_mutate_sources(self):
        before = list(Member.objects.values())
        record = self.make()
        services.record_findings(record.pk, user=self.actor, data=finding_data())
        record.refresh_from_db()
        self.assertEqual(record.concern, 'Synthetic concern')
        self.assertEqual(record.state, 'findings_recorded')
        self.assertEqual(record.actions.count(), 2)
        self.assertEqual(list(Member.objects.values()), before)
        with self.assertRaises(ValidationError):
            services.record_findings(record.pk, user=self.actor, data=finding_data())
        with self.assertRaises(ValidationError):
            services.record_findings(record.pk, user=self.actor, data=finding_data(version=1, state='approved'))

    def test_selected_nonselected_and_closed_concerns_do_not_change_outcomes(self):
        for status in ('SELECTED', 'NOT_SELECTED', 'CLOSED'):
            app = self.application(status=status)
            before = ProgramApplication.objects.filter(pk=app.pk).values().get()
            record = services.open_review(self.member.pk, user=self.actor, application_id=app.pk,
                data=intake_data(kind='evaluation', trigger='clarification'))
            services.record_findings(record.pk, user=self.actor, data=finding_data())
            self.assertEqual(ProgramApplication.objects.filter(pk=app.pk).values().get(), before)

    def test_mismatched_member_and_missing_application_fail(self):
        other = create_member('SYNTHETIC-OTHER')
        app = self.application(member=other)
        with self.assertRaises(ValidationError):
            services.open_review(self.member.pk, user=self.actor, application_id=app.pk,
                data=intake_data(kind='evaluation', trigger='clarification'))
        with self.assertRaises(ValidationError):
            self.make(kind='evaluation', trigger='clarification')

    def test_routine_checks_need_approved_basis_and_findings_need_dates(self):
        with self.assertRaises(ValidationError):
            self.make(trigger='routine')
        with override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy(routine_basis='   ')):
            with self.assertRaises(ValidationError):
                self.make(trigger='routine')
        for invalid in (True, ['not an approved reference'], None):
            with override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy(routine_basis=invalid)):
                with self.assertRaises(Http404):
                    self.make(trigger='routine')
        with override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy(routine_basis='FICTIONAL selection basis')):
            record = self.make(trigger='routine')
            self.assertEqual(record.policy_snapshot['routine_basis'], 'FICTIONAL selection basis')
            with self.assertRaises(ValidationError):
                services.record_findings(record.pk, user=self.actor, data=finding_data(observed_on=''))

    def test_private_permissions_csrf_and_program_scope(self):
        record = self.make()
        detail = reverse('members:review_detail', args=[record.pk])
        self.assertEqual(Client().get(detail).status_code, 302)
        viewer = get_user_model().objects.create_user('synthetic_review_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'members.view_member', 'members.view_informationreview')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(detail, finding_data()).status_code, 403)
        app = self.application()
        evaluation = services.open_review(self.member.pk, user=self.actor, application_id=app.pk,
            data=intake_data(kind='evaluation', trigger='clarification'))
        self.assertEqual(self.client.get(reverse('members:review_detail', args=[evaluation.pk])).status_code, 403)
        self.assertEqual(self.client.get(self.url).context['page_obj'].paginator.count, 1)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.actor)
        self.assertEqual(strict.post(detail, finding_data()).status_code, 403)

    def test_revoked_permission_and_audit_failure_roll_back(self):
        record = self.make()
        actor = get_user_model().objects.create_user('synthetic_review_writer', is_staff=True)
        grant(actor, 'accounts.access_dashboard', 'members.view_member', 'members.view_informationreview', 'members.record_informationreview')
        self.assertTrue(actor.has_perm('members.record_informationreview'))
        actor.user_permissions.remove(Permission.objects.get(codename='record_informationreview'))
        with self.assertRaises(PermissionDenied):
            services.record_findings(record.pk, user=actor, data=finding_data())
        with patch.object(InformationReviewAction.objects, 'create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                services.record_findings(record.pk, user=self.actor, data=finding_data())
            with self.assertRaises(RuntimeError):
                self.make()
        record.refresh_from_db()
        self.assertEqual(record.version, 0)
        self.assertEqual(InformationReview.objects.count(), 1)

    def test_history_mutation_and_changed_policy_are_denied(self):
        record = self.make()
        with self.assertRaises(PermissionDenied):
            record.actions.first().save()
        with self.assertRaises(PermissionDenied):
            InformationReview.objects.filter(pk=record.pk).update(state='under_review')
        with override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy(review_procedure='Changed synthetic procedure')):
            with self.assertRaises(ValidationError):
                services.record_findings(record.pk, user=self.actor, data=finding_data())

    def test_internal_status_is_minimal_staff_only_and_has_no_pdao_or_public_route(self):
        app = self.application(status='RANKED')
        self.assertEqual(services.staff_status(app.public_reference, user=self.actor, category='program'),
            {'category': 'program', 'state': 'RANKED', 'label': 'Evaluation processed'})
        with self.assertRaises(PermissionDenied):
            services.staff_status(app.public_reference, user=AnonymousUser(), category='program')
        with self.assertRaises(Http404):
            services.staff_status(app.public_reference, user=self.actor, category='pdao')
        self.assertEqual(Client().get(reverse('programs:status', args=[app.status_token])).status_code, 410)
        self.assertEqual(Client().get('/tracking/').status_code, 404)

    def test_association_status_projection_uses_existing_registration_authorization(self):
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            binding = registration_services.binding_for('synthetic-review-browser')
            context = registration_services.issue_context(binding)
            intake = registration_services.submit_registration(context.pk, binding, submitted())
            self.assertEqual(services.staff_status(intake.reference, user=self.actor, category='association'),
                {'category': 'association', 'state': 'received', 'label': 'Received'})
            with self.assertRaises(PermissionDenied):
                services.staff_status(intake.reference, user=AnonymousUser(), category='association')


class InformationReviewConcurrencyTests(TransactionTestCase):
    def test_duplicate_submission_and_stale_findings_serialize(self):
        require_disposable()
        actor = get_user_model().objects.create_superuser('synthetic_concurrent_reviewer')
        member = create_member('SYNTHETIC-CONCURRENT-REVIEW')
        data = intake_data()
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return services.open_review(member.pk, user=actor, data=data).pk
            finally:
                close_old_connections()

        with override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy()):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: submit(), range(2)))
            self.assertEqual(results[0], results[1])
            record = InformationReview.objects.get()
            self.assertEqual(record.actions.count(), 1)
            barrier = Barrier(2)

            def review():
                close_old_connections()
                try:
                    barrier.wait(timeout=10)
                    try:
                        services.record_findings(record.pk, user=actor, data=finding_data())
                        return 'accepted'
                    except ValidationError:
                        return 'stale'
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertCountEqual(list(pool.map(lambda _: review(), range(2))), ['accepted', 'stale'])
            record.refresh_from_db()
            self.assertEqual(record.version, 1)
            self.assertEqual(record.actions.count(), 2)
