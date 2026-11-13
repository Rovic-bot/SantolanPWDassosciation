"""Results publication freezes ranking weights; program notices leave them editable."""
from copy import deepcopy
import json
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from . import operational_services as operations, shared_weights, vault_services as vault
from .dataset_methods import COMPOSITE
from .operational_models import OperationalRun
from .program_cards import configuration_summary
from . import test_rolling_pool as rolling_fixture, test_shared_application as shared_fixture
from .test_synthetic_twelve import proposal


def approve_weights(test, scenario):
    for status in ('DRAFT', 'LOCKED'):
        row = vault.record_ses_weights(user=test.user, expected=vault.token(),
            proposal=proposal(scenario), reason='SYNTHETIC result weight regression',
            status=status, method=COMPOSITE)
    return row


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ResultWeightTests(TransactionTestCase):
    draft = rolling_fixture.RollingPoolTests.draft
    approve = rolling_fixture.RollingPoolTests.approve
    bind = rolling_fixture.RollingPoolTests.bind
    publish = rolling_fixture.RollingPoolTests.publish
    applicant = rolling_fixture.RollingPoolTests.applicant
    pool = rolling_fixture.RollingPoolTests.pool
    generate = rolling_fixture.RollingPoolTests.generate

    def setUp(self):
        # Only legacy fixture setup skips the later automatic fixed-rule binding.
        # Publication, approvals, selections and rankings use real services.
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            rolling_fixture.RollingPoolTests.setUp(self)

    def select(self, run, app):
        from .operational_models import OperationalDecision
        previous = OperationalDecision.objects.filter(application=app).first()
        return operations.record_decision(self.program.pk, user=self.user, run_id=run.pk,
            application_id=app.pk, expected_revision=previous.revision if previous else 0,
            outcome='SELECTED', reason='SYNTHETIC reviewed ranking selection')

    def prepare(self, recorded=True):
        from announcements.models import Announcement
        from announcements.results import prepare_results
        item = Announcement.objects.filter(program=self.program).first()
        return prepare_results(self.program.pk, user=self.user, version=item.version if item else 0,
            reason='SYNTHETIC prepare reviewed results', recorded=recorded,
            selection_reason='SYNTHETIC selected after reviewing the retained EWAF ranking.')

    def publish_results(self, item=None):
        from announcements.results import publish_results
        item = item or self.prepare()
        return publish_results(item.pk, user=self.user, version=item.version)

    def ranked_selection(self):
        a, b = self.pool()
        approved = approve_weights(self, 'hm')
        run = self.generate()
        self.select(run, a)
        return a, b, approved, run

    def test_program_publication_and_program_notice_leave_weights_editable(self):
        from announcements.models import Announcement
        from announcements.services import change_publication
        self.pool()
        notice = Announcement.objects.create(linked_program=self.program,
            title='SYNTHETIC program announcement', content='Program is open.', source_office='SYNTHETIC office')
        with patch('django.utils.timezone.now', return_value=self.open_at):
            change_publication(notice.pk, user=self.user, version=notice.version, action='published')
        original = self.generate()
        saved = deepcopy(original.payload())
        for scenario in ('ses', 'pa', 'hm'):
            old = operations.context(self.program.pk, user=self.user)
            approved = approve_weights(self, scenario)
            self.assertFalse(shared_weights.publication_locked(self.program))
            self.assertNotEqual(old, operations.context(self.program.pk, user=self.user))
            self.assertEqual(self.generate().snapshot[shared_weights.KEY]['id'], approved.pk)
            self.assertFalse(configuration_summary(self.program)['weights_locked'])
        original.refresh_from_db(); original.clean()
        self.assertEqual(original.payload(), saved)

    def test_prepared_results_do_not_lock_weights(self):
        self.ranked_selection()
        self.prepare()
        approved = approve_weights(self, 'ses')
        self.assertFalse(shared_weights.publication_locked(self.program))
        self.assertEqual(self.generate().snapshot[shared_weights.KEY]['id'], approved.pk)

    def test_initial_bound_weights_are_retained_when_published_ranking_has_no_override(self):
        a, b = self.pool()
        original = self.generate()
        self.assertNotIn(shared_weights.KEY, original.snapshot)
        self.select(original, a)
        self.publish_results()
        approve_weights(self, 'hm')
        rerun = self.generate()
        self.assertNotIn(shared_weights.KEY, rerun.snapshot)
        self.assertEqual(rerun.calculations, original.calculations)

    def test_one_results_lock_does_not_lock_another_program(self):
        a, b, frozen, run = self.ranked_selection()
        self.publish_results()
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            other = shared_fixture.SharedApplicationTests.another_program(self, 'SYNTHETIC independent program')
        shared_fixture.SharedApplicationTests.publish_intake(self, other)
        approved = approve_weights(self, 'ses')
        self.assertEqual(shared_weights.current(self.configuration)['id'], frozen.pk)
        self.assertEqual(shared_weights.current(operations.latest_configuration(other))['id'], approved.pk)
        self.assertFalse(shared_weights.publication_locked(other))

    def test_results_with_mixed_selected_weight_versions_require_review(self):
        # Fictional fixture capacity, set before its first scoring binding.
        self.program.slots = 2
        self.program.save(update_fields=['slots'])
        a, b = self.pool()
        first = self.generate()
        self.select(first, a)
        approve_weights(self, 'hm')
        second = self.generate()
        self.select(second, b)
        item = self.prepare()
        with self.assertRaisesMessage(ValidationError, 'different EWAF weight versions'):
            self.publish_results(item)
        self.assertFalse(shared_weights.publication_locked(self.program))

    def test_results_freeze_actual_selected_ranking_and_allow_repeated_ranking(self):
        from announcements.results import results_current
        a, b, approved, original = self.ranked_selection()
        self.assertNotEqual(approved.pk, self.configuration.validation['weight_version'])
        saved = deepcopy(original.payload())
        item = self.publish_results()
        source = deepcopy(item.result_revision.public_payload)
        for scenario in ('ses', 'pa'):
            expected = operations.context(self.program.pk, user=self.user)
            approve_weights(self, scenario)
            self.assertEqual(expected, operations.context(self.program.pk, user=self.user))
            rerun = self.generate()
            rerun.clean()
            self.assertEqual(rerun.calculations, original.calculations)
            self.assertEqual(rerun.snapshot[shared_weights.KEY]['id'], approved.pk)
            card = configuration_summary(self.program)
            self.assertTrue(card['weights_locked'])
            self.assertEqual(card['weight_version'], approved.pk)
            self.assertTrue(results_current(item))
        item.result_revision.refresh_from_db()
        self.assertEqual(item.result_revision.public_payload, source)
        original.refresh_from_db(); original.clean()
        self.assertEqual(original.payload(), saved)

    def test_recorded_results_use_selected_older_ranking_not_latest_vault_or_unselected_run(self):
        a, b, selected_weights, selected = self.ranked_selection()
        newer = approve_weights(self, 'ses')
        unselected = self.generate()
        self.assertEqual(unselected.snapshot[shared_weights.KEY]['id'], newer.pk)
        self.publish_results()
        rerun = self.generate()
        self.assertEqual(rerun.snapshot[shared_weights.KEY]['id'], selected_weights.pk)
        self.assertEqual(rerun.calculations, selected.calculations)
        unselected.clean()

    def test_withdraw_and_republish_results_keep_first_published_weights(self):
        from announcements.services import change_publication
        self.ranked_selection()
        item = self.publish_results()
        locked = shared_weights.current(self.configuration)
        change_publication(item.pk, user=self.user, version=item.version, action='draft')
        approve_weights(self, 'ses')
        self.assertTrue(shared_weights.publication_locked(self.program))
        self.assertEqual(shared_weights.current(self.configuration), locked)
        self.generate()
        self.publish_results()
        self.assertEqual(shared_weights.current(self.configuration), locked)

    def test_failed_result_audit_rolls_back_publication_without_locking(self):
        self.ranked_selection()
        item = self.prepare()
        with patch('announcements.results.record_event', side_effect=ValidationError('SYNTHETIC audit failure')):
            with self.assertRaisesMessage(ValidationError, 'audit failure'):
                self.publish_results(item)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')
        self.assertIsNone(item.published_at)
        self.assertFalse(shared_weights.publication_locked(self.program))
        approved = approve_weights(self, 'ses')
        self.assertEqual(self.generate().snapshot[shared_weights.KEY]['id'], approved.pk)

    def test_results_lock_works_without_current_global_approval(self):
        self.ranked_selection()
        self.publish_results()
        with patch('ewaf.vault_services.active', return_value=None):
            self.generate().clean()

    def test_results_lock_preserves_permissions_and_rejects_rebinding(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        from .revised import live_services
        self.ranked_selection()
        self.publish_results()
        viewer = get_user_model().objects.create_user('SYNTHETIC-LOCK-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operations.VIEW)
        before = OperationalRun.objects.count()
        with self.assertRaises(PermissionDenied):
            operations.generate(self.program.pk, user=viewer,
                expected=operations.context(self.program.pk, user=self.user),
                reason='SYNTHETIC forbidden generation', request_key=uuid4())
        self.assertEqual(OperationalRun.objects.count(), before)
        policy = deepcopy(self.configuration.dataset_policy)
        policy.weight_configuration_id = approve_weights(self, 'ses').pk
        with self.assertRaisesMessage(ValidationError, 'Published program results retain'):
            live_services.binding_preflight(self.program, policy, self.configuration.assessment_cutoff)
        with override_settings(EWAF_VAULT_ENABLED=False):
            with self.assertRaisesMessage(ValidationError, 'Weights are locked after program results'):
                operations.record_configuration(self.program.pk, user=self.user,
                    expected=operations.configuration_token(self.program), proposed={}, judgments={},
                    status='DRAFT', reason='SYNTHETIC rejected edit')

    def test_fixed_scoring_http_ranking_uses_published_result_weights(self):
        from programs.services import change_publication
        from .fixed_scoring import is_fixed
        with patch('django.utils.timezone.now', return_value=self.base):
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='published', notes='SYNTHETIC fixed-scoring program')
        self.program.refresh_from_db()
        self.configuration = operations.latest_configuration(self.program)
        self.assertTrue(is_fixed(self.configuration))
        a = self.applicant('FIXED-RESULT-A', low=True)
        self.applicant('FIXED-RESULT-B')
        approved = approve_weights(self, 'hm')
        original = self.generate()
        self.select(original, a)
        self.publish_results()
        approve_weights(self, 'ses')
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        page = self.client.get(url)
        self.assertTrue(page.context['ready'])
        self.assertTrue(page.context['can_calculate'])
        self.assertContains(page, 'Weights locked after results publication.')
        response = self.client.post(url, {'action': 'GENERATE',
            'expected': json.dumps(operations.context(self.program.pk, user=self.user)),
            'request_key': str(uuid4())})
        self.assertEqual(response.status_code, 302)
        rerun = OperationalRun.objects.filter(program=self.program).first()
        rerun.clean()
        self.assertEqual(rerun.snapshot[shared_weights.KEY]['id'], approved.pk)
        self.assertEqual(rerun.calculations, original.calculations)

    def test_strict_results_publication_retains_current_ranking_weights(self):
        a, b, approved, run = self.ranked_selection()
        operations.record_decision(self.program.pk, user=self.user, run_id=run.pk,
            application_id=b.pk, expected_revision=0, outcome='NOT_SELECTED', reason='SYNTHETIC reviewed nonselection')
        self.publish_results(self.prepare(recorded=False))
        approve_weights(self, 'ses')
        self.assertEqual(self.generate().snapshot[shared_weights.KEY]['id'], approved.pk)

    def test_recorded_results_without_ranking_freeze_approval_at_publication(self):
        self.pool()
        approved = approve_weights(self, 'hm')
        self.publish_results()
        approve_weights(self, 'ses')
        self.assertEqual(self.generate().snapshot[shared_weights.KEY]['id'], approved.pk)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class UnpublishedResultProgramTests(TransactionTestCase):
    publish_intake = shared_fixture.SharedApplicationTests.publish_intake

    def setUp(self):
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            shared_fixture.SharedApplicationTests.setUp(self)

    def test_draft_and_published_program_without_results_follow_new_approvals(self):
        approved = approve_weights(self, 'hm')
        self.assertEqual(operations.latest_configuration(self.program, require_locked=False).vault_revision_id, approved.pk)
        self.publish_intake()
        configuration = operations.latest_configuration(self.program)
        newer = approve_weights(self, 'pa')
        self.assertFalse(shared_weights.publication_locked(self.program))
        self.assertEqual(shared_weights.current(configuration)['id'], newer.pk)
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            fresh = shared_fixture.SharedApplicationTests.another_program(self, 'SYNTHETIC new program')
        self.publish_intake(fresh)
        self.assertEqual(operations.latest_configuration(fresh).validation['weight_version'], newer.pk)
