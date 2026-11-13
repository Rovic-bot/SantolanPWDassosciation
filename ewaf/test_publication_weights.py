"""Publication freezes weights, while global authoring and ranking stay usable."""
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from . import operational_services as operations, shared_weights, vault_services as vault
from .dataset_methods import COMPOSITE
from .operational_models import OperationalConfiguration, OperationalRun
from .program_cards import configuration_summary
from . import test_rolling_pool as rolling_fixture, test_shared_application as shared_fixture
from .test_synthetic_twelve import proposal


def approve_weights(test, scenario):
    for status in ('DRAFT', 'LOCKED'):
        row = vault.record_ses_weights(user=test.user, expected=vault.token(),
            proposal=proposal(scenario), reason='SYNTHETIC publication weight regression',
            status=status, method=COMPOSITE)
    return row


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class PublishedRankingWeightTests(TransactionTestCase):
    draft = rolling_fixture.RollingPoolTests.draft
    approve = rolling_fixture.RollingPoolTests.approve
    bind = rolling_fixture.RollingPoolTests.bind
    publish = rolling_fixture.RollingPoolTests.publish
    applicant = rolling_fixture.RollingPoolTests.applicant
    pool = rolling_fixture.RollingPoolTests.pool
    generate = rolling_fixture.RollingPoolTests.generate

    def setUp(self):
        # The retained-policy fixture predates automatic fixed-rule binding.
        # Only its setup skips that new side effect; publication, validation,
        # weight approval and ranking below all use the real services.
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            rolling_fixture.RollingPoolTests.setUp(self)

    def test_later_approvals_preserve_weights_scores_tokens_and_allow_repeated_ranking(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            original = self.generate()
            payload = deepcopy(original.payload())
            binding = deepcopy(self.configuration.payload())
            for scenario in ('ses', 'pa', 'hm'):
                expected = operations.context(self.program.pk, user=self.user)
                approved = approve_weights(self, scenario)
                self.assertNotEqual(approved.pk, self.configuration.validation['weight_version'])
                self.assertEqual(expected, operations.context(self.program.pk, user=self.user))
                run = operations.generate(self.program.pk, user=self.user, expected=expected,
                    reason='SYNTHETIC rerank published program', request_key=uuid4())
                run.clean()
                self.assertEqual(run.calculations, original.calculations)
                self.assertEqual(shared_weights.current(run.configuration)['id'], self.configuration.validation['weight_version'])
                self.assertNotIn(shared_weights.KEY, run.snapshot)
                card = configuration_summary(self.program)
                self.assertTrue(card['weights_locked'])
                self.assertEqual(card['weight_version'], self.configuration.validation['weight_version'])
                self.assertEqual(operations.latest_configuration(self.program).payload(), binding)
            original.refresh_from_db(); original.clean()
            self.assertEqual(original.payload(), payload)
            page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
            self.assertTrue(page.context['ready'])

    def test_published_ranking_does_not_depend_on_a_current_global_approval(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            with patch('ewaf.vault_services.active', return_value=None):
                self.generate().clean()

    def test_fixed_scoring_published_program_can_generate_through_http_after_weight_changes(self):
        import json
        from datetime import timedelta
        from django.utils.dateparse import parse_datetime
        from programs.services import change_publication
        from .fixed_scoring import definition, is_fixed
        with patch('django.utils.timezone.now', return_value=self.open_at):
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='published', notes='SYNTHETIC current fixed-scoring publication')
            self.program.refresh_from_db()
            self.configuration = operations.latest_configuration(self.program)
            self.assertTrue(is_fixed(self.configuration))
            self.applicant('FIXED-LOCK-A', low=True)
            self.applicant('FIXED-LOCK-B')
        # The historical fixture may predate the fixed rules' effective date.
        ranking_at = max(self.open_at, parse_datetime(definition()['effective_from']) + timedelta(hours=4))
        with patch('django.utils.timezone.now', return_value=ranking_at):
            original = self.generate()
            approved = approve_weights(self, 'hm')
            self.assertNotEqual(approved.pk, self.configuration.validation['weight_version'])
            url = reverse('ewaf:operational_workspace', args=[self.program.pk])
            page = self.client.get(url)
            self.assertTrue(page.context['ready'])
            self.assertTrue(page.context['can_calculate'])
            self.assertFalse(page.context['can_configure'])
            self.assertContains(page, 'Weights locked after publication.')
            response = self.client.post(url, {'action': 'GENERATE',
                'expected': json.dumps(operations.context(self.program.pk, user=self.user)),
                'request_key': str(uuid4())})
            self.assertEqual(response.status_code, 302)
            rerun = OperationalRun.objects.filter(program=self.program).first()
            rerun.clean()
            self.assertEqual(rerun.previous_id, original.pk)
            self.assertEqual(rerun.calculations, original.calculations)
            self.assertNotIn(shared_weights.KEY, rerun.snapshot)

    def test_published_lock_does_not_bypass_ranking_permission(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import PermissionDenied
        from membership.tests import grant
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            viewer = get_user_model().objects.create_user('SYNTHETIC-LOCK-VIEWER', is_staff=True)
            grant(viewer, 'accounts.access_dashboard', *operations.VIEW)
            expected = operations.context(self.program.pk, user=self.user)
            with self.assertRaises(PermissionDenied):
                operations.generate(self.program.pk, user=viewer, expected=expected,
                    reason='SYNTHETIC forbidden generation', request_key=uuid4())
            self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())

    def test_direct_rebinding_cannot_replace_published_weights(self):
        from .revised import live_services
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            new = approve_weights(self, 'hm')
            policy = deepcopy(self.configuration.dataset_policy)
            policy.weight_configuration_id = new.pk
            with self.assertRaisesMessage(ValidationError, 'Published programs retain'):
                live_services.binding_preflight(self.program, policy, self.configuration.assessment_cutoff)
            with override_settings(EWAF_VAULT_ENABLED=False):
                with self.assertRaisesMessage(ValidationError, 'Weights are locked'):
                    operations.record_configuration(self.program.pk, user=self.user,
                        expected=operations.configuration_token(self.program), proposed={}, judgments={},
                        status='DRAFT', reason='SYNTHETIC direct write rejected')

    def test_preexisting_run_with_old_shared_override_still_replays_unchanged(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            approved = approve_weights(self, 'hm')
            # Build an authentic older-contract run, which selected the active
            # Vault after publication. The fix must preserve its signed history.
            with patch.object(shared_weights, 'publication_locked', return_value=False):
                historic = self.generate()
            self.assertEqual(historic.snapshot[shared_weights.KEY]['id'], approved.pk)
            saved = deepcopy(historic.payload())
            historic.clean()
            new = self.generate()
            self.assertNotIn(shared_weights.KEY, new.snapshot)
            historic.refresh_from_db(); historic.clean()
            self.assertEqual(historic.payload(), saved)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class PublicationBindingWeightTests(TransactionTestCase):
    publish_intake = shared_fixture.SharedApplicationTests.publish_intake

    def setUp(self):
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            shared_fixture.SharedApplicationTests.setUp(self)

    def another_program(self, name):
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            return shared_fixture.SharedApplicationTests.another_program(self, name)

    def test_unpublished_programs_receive_new_weights_then_freeze_at_publication(self):
        from .fixed_scoring import bind
        before = operations.latest_configuration(self.program, require_locked=False)
        published = self.another_program('SYNTHETIC already published')
        self.publish_intake(published)
        old = operations.latest_configuration(published)
        saved = deepcopy(old.payload())
        approved = approve_weights(self, 'hm')
        draft = operations.latest_configuration(self.program, require_locked=False)
        self.assertEqual(draft.vault_revision_id, approved.pk)
        self.assertNotEqual(draft.pk, before.pk)
        self.publish_intake()
        current = operations.latest_configuration(self.program)
        self.assertEqual(current.validation['weight_version'], approved.pk)
        newer = approve_weights(self, 'pa')
        self.assertNotEqual(newer.pk, approved.pk)
        self.assertEqual(shared_weights.current(current)['id'], approved.pk)
        self.assertEqual(bind(published, user=self.user).payload(), saved)
        fresh = self.another_program('SYNTHETIC future program')
        self.publish_intake(fresh)
        self.assertEqual(operations.latest_configuration(fresh).validation['weight_version'], newer.pk)

    def test_fixed_draft_refreshes_to_latest_approved_weights_at_first_publication(self):
        from .fixed_scoring import bind
        fixed_draft = bind(self.program, user=self.user)
        approved = approve_weights(self, 'hm')
        self.assertEqual(shared_weights.current(fixed_draft)['id'], approved.pk)
        self.publish_intake()
        published = operations.latest_configuration(self.program)
        self.assertEqual(published.validation['weight_version'], approved.pk)
        self.assertEqual(published.previous_id, fixed_draft.pk)
        fixed_draft.clean()

    def test_unpublish_and_republish_keep_the_same_approved_weights(self):
        from programs.services import change_publication
        self.publish_intake()
        original = operations.latest_configuration(self.program)
        change_publication(self.program.pk, user=self.user, version=self.program.version,
            action='unpublish', notes='SYNTHETIC temporarily hide program')
        self.program.refresh_from_db()
        self.assertTrue(shared_weights.publication_locked(self.program))
        approve_weights(self, 'hm')
        self.assertIsNone(vault.inherit(self.program, user=self.user))
        self.assertEqual(shared_weights.current(original)['id'], original.validation['weight_version'])
        self.publish_intake()
        self.assertEqual(operations.latest_configuration(self.program).pk, original.pk)

    def test_published_weights_only_intake_keeps_original_weights_when_completed(self):
        from .fixed_scoring import bind
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            self.publish_intake()
        original = operations.latest_configuration(self.program, require_locked=False)
        self.assertEqual(original.policy['configuration_scope'], 'weights_and_sources')
        original_id = original.vault_revision_id
        approved = approve_weights(self, 'hm')
        completed = operations.latest_configuration(self.program)
        self.assertNotEqual(approved.pk, original_id)
        self.assertEqual(completed.validation['weight_version'], original_id)
        self.assertEqual(bind(self.program, user=self.user).pk, completed.pk)

    def test_publication_audit_failure_rolls_back_the_new_weight_binding(self):
        from .fixed_scoring import bind
        fixed_draft = bind(self.program, user=self.user)
        approve_weights(self, 'hm')
        count = OperationalConfiguration.objects.filter(program=self.program).count()
        with patch('programs.services.record_log', side_effect=ValidationError('SYNTHETIC failed publication audit')):
            with self.assertRaisesMessage(ValidationError, 'failed publication audit'):
                self.publish_intake()
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertIsNone(self.program.published_at)
        self.assertEqual(OperationalConfiguration.objects.filter(program=self.program).count(), count)
        self.assertEqual(operations.latest_configuration(self.program).pk, fixed_draft.pk)
