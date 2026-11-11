"""Fixed-one HM scoring, exact weighted results and immutable ranking history."""
from copy import deepcopy
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import dataset_methods as methods, employment_scoring, household_scoring as household
from . import operational_services as service
from .operational_models import OperationalDecision
from .revised import live_math
from .revised.composite_ses import FORMULA
from .shared_calculation_rules import FULL_CONSTANTS
from .test_rolling_pool import RollingPoolTests as Fixture


def trace(result, key):
    return next(row for row in result[str(key)]['traces'] if row['criterion'] == 'HM')


def arithmetic(counts, *, legacy=False, constant=FULL_CONSTANTS):
    configuration = SimpleNamespace(digest='synthetic-hm-configuration', uses_dataset_scoring=True,
        policy={'method': methods.COMPOSITE, 'ses_formula': deepcopy(FORMULA), 'constant_rule': constant},
        validation={'weights': {'SES': '2/5', 'ES': '1/5', 'PA': '1/5', 'HM': '1/5'},
                    'weight_digest': 'synthetic-weights'},
        source={'terms': {'program': {'slots': 1}}}, dataset_policy=SimpleNamespace(digest='synthetic-policy'),
        assessment_cutoff=timezone.now())
    snapshot = {'engine': methods.COMPOSITE, 'configuration_digest': configuration.digest,
        **employment_scoring.capture(configuration),
        **({} if legacy else household.capture(configuration)),
        'eligible': {str(i): {'inputs': {'SES': {'value': '100', 'household_four_ps': 0},
            'ES': {'value': 'Employed'}, 'PA': {'value': '0'}, 'HM': {'value': str(value)}}}
            for i, value in enumerate(counts)}}
    return snapshot, configuration


class HouseholdScoringArithmeticTests(SimpleTestCase):
    def test_lowest_four_of_five_receives_seventy_five_percent_before_weight(self):
        result = live_math.calculations(*arithmetic([4, 5]))
        low, high = trace(result, 0), trace(result, 1)
        self.assertEqual(low['normalized']['exact'], '3/4')
        self.assertEqual(low['contribution']['exact'], '3/20')
        self.assertEqual(high['normalized']['exact'], '1')
        self.assertEqual(high['contribution']['exact'], '1/5')
        self.assertEqual(low['minimum']['exact'], '4')
        self.assertEqual(low['normalization_minimum']['exact'], '1')
        self.assertEqual(low['maximum']['exact'], '5')
        self.assertEqual(result['0']['score_exact'], '91/100')
        self.assertEqual(result['1']['score_exact'], '24/25')
        self.assertEqual(result['0']['comparison']['business_rank'], 2)

    def test_one_is_zero_and_each_program_uses_its_own_maximum(self):
        for counts, expected in (([1, 4, 5], ['0', '3/4', '1']),
                                 ([1, 4, 9], ['0', '3/8', '1']),
                                 ([2, 4, 7], ['1/6', '1/2', '1'])):
            with self.subTest(counts=counts):
                result = live_math.calculations(*arithmetic(counts))
                self.assertEqual([trace(result, i)['normalized']['exact'] for i in range(len(counts))], expected)

    def test_constant_and_single_households_have_no_division_by_zero(self):
        for constant in (FULL_CONSTANTS, 'zero_contribution_v1'):
            for counts, expected in (([1], '0'), ([1, 1], '0'), ([4], '1'), ([4, 4], '1')):
                with self.subTest(counts=counts, constant=constant):
                    result = live_math.calculations(*arithmetic(counts, constant=constant))
                    for key in result:
                        self.assertEqual(trace(result, key)['normalized']['exact'], expected)
                        self.assertNotIn('constant_rule', trace(result, key))
                    for item in result['0']['traces'][:-1]:
                        self.assertEqual(item['constant_rule'], constant)

    def test_invalid_or_missing_counts_do_not_become_zero_scores(self):
        for value in (0, -1, '3/2', None, ''):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                live_math.calculations(*arithmetic([value, 5]))

    def test_old_snapshots_keep_pool_minimum_and_old_equal_value_rule(self):
        result = live_math.calculations(*arithmetic([4, 5], legacy=True))
        self.assertEqual(trace(result, 0)['normalized']['exact'], '0')
        self.assertNotIn('normalization_minimum', trace(result, 0))
        for constant, expected in ((FULL_CONSTANTS, '1'), ('zero_contribution_v1', '0')):
            result = live_math.calculations(*arithmetic([1, 1], legacy=True, constant=constant))
            self.assertEqual(trace(result, 0)['normalized']['exact'], expected)

    def test_frozen_rule_rejects_unknown_versions_or_changed_semantics(self):
        snapshot, configuration = arithmetic([4, 5])
        for change in ({'version': 'unknown'}, {'minimum': 0}, {'minimum': True},
                       {'maximum': 'all_members'}, {'all_one': 'full'}):
            bad = deepcopy(snapshot)
            bad[household.KEY].update(change)
            with self.subTest(change=change), self.assertRaisesMessage(ValidationError, 'exact version'):
                live_math.calculations(bad, configuration)

    def test_scope_is_new_composite_rankings_including_fixed_code_bindings(self):
        from .fixed_scoring import definition
        configuration = SimpleNamespace(policy=definition(), uses_dataset_scoring=True)
        self.assertEqual(household.capture(configuration), {household.KEY: household.definition()})
        for method in (methods.HOUSEHOLD, methods.SES):
            configuration.policy = {'method': method}
            self.assertEqual(household.capture(configuration), {})
            with self.assertRaises(ValidationError):
                household.retained({household.KEY: household.definition()}, configuration)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class HouseholdScoringWorkflowTests(TransactionTestCase):
    publish = Fixture.publish
    applicant = Fixture.applicant
    generate = Fixture.generate

    def setUp(self):
        # The inherited setup backdates programs by ten days. Keep this fixture
        # after the fixed-code rules' effective date, independently of test day.
        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 20, 1, tzinfo=datetime_timezone.utc)):
            Fixture.setUp(self)

    def bind(self):
        from .fixed_scoring import bind
        # Current authorization already applies the fixed-code binding. Use that
        # real configuration instead of replacing it with a historical policy.
        return bind(self.program, user=self.user)

    def pool(self):
        self.publish()
        return self.applicant('HM-FOUR', household_members=4), self.applicant('HM-FIVE', household_members=5)

    def test_generated_ranking_and_visible_breakdown_use_one_and_keep_human_selection(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            low, high = self.pool()
            binding = deepcopy(self.configuration.payload())
            run = self.generate()
            run.clean()
            self.assertEqual(run.snapshot[household.KEY], household.definition())
            self.assertEqual(trace(run.calculations, low.pk)['normalized']['exact'], '3/4')
            self.assertEqual(trace(run.calculations, low.pk)['contribution']['exact'], '3/20')
            self.assertEqual(trace(run.calculations, high.pk)['normalized']['exact'], '1')
            self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())
            self.configuration.refresh_from_db()
            self.assertEqual(self.configuration.payload(), binding)
            page = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]),
                                   {'run': run.pk, 'applicant': low.pk})
            self.assertContains(page, '(4 − 1) ÷ (5 − 1)')
            self.assertContains(page, 'Baseline: 1 household member.')
            self.assertContains(page, '75.00')
            self.assertTrue(page.context['active'])
            decision = service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                application_id=high.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic human selection')
            self.assertEqual(decision.outcome, 'SELECTED')

    def test_new_maximum_requires_manual_recalculation_and_preserves_old_scores(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            low, _ = self.pool()
            old = self.generate()
            saved = deepcopy(old.payload())
            token = service.context(self.program.pk, user=self.user)
            self.applicant('HM-NINE', household_members=9)
            with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
                service.generate(self.program.pk, user=self.user, expected=token,
                    reason='Synthetic stale maximum', request_key=uuid4())
            new = self.generate()
            self.assertEqual(trace(new.calculations, low.pk)['normalized']['exact'], '3/8')
            self.assertEqual(new.previous_id, old.pk)
            old.refresh_from_db(); old.clean(); new.clean()
            self.assertEqual(old.payload(), saved)

    def test_legacy_run_replays_but_old_tokens_and_new_decisions_require_new_rule(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            low, high = self.pool()
            with patch('ewaf.household_scoring.capture', return_value={}):
                old = self.generate()
                token = service.context(self.program.pk, user=self.user)
            saved = deepcopy(old.payload())
            old.clean()
            self.assertEqual(trace(old.calculations, low.pk)['normalized']['exact'], '0')
            with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
                service.generate(self.program.pk, user=self.user, expected=token,
                    reason='Synthetic stale rule', request_key=uuid4())
            with self.assertRaisesMessage(ValidationError, 'Household Members scoring rule changed'):
                service.record_decision(self.program.pk, user=self.user, run_id=old.pk,
                    application_id=high.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic stale selection')
            with self.assertRaisesMessage(ValidationError, 'Household Members scoring rule changed'):
                service.publication_snapshot(self.program)
            page = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]),
                                   {'run': old.pk, 'applicant': low.pk})
            self.assertContains(page, '(4 − 4) ÷ (5 − 4)')
            self.assertContains(page, 'Scoring rules changed; update the ranking.')
            self.assertFalse(page.context['active'])
            new = self.generate()
            old.refresh_from_db(); old.clean(); new.clean()
            self.assertEqual(old.payload(), saved)
            self.assertEqual(new.previous_id, old.pk)
            self.assertEqual(trace(new.calculations, low.pk)['normalized']['exact'], '3/4')

    def test_pending_application_does_not_set_the_eligible_pool_maximum(self):
        from programs.models import ProgramApplication
        with patch('django.utils.timezone.now', return_value=self.open_at):
            low, high = self.pool()
            pending = self.applicant('HM-PENDING', household_members=99)
            ProgramApplication.objects.filter(pk=pending.pk).update(status='ELIGIBILITY_REVIEW')
            run = self.generate()
            self.assertEqual(set(run.calculations), {str(low.pk), str(high.pk)})
            self.assertEqual(trace(run.calculations, low.pk)['maximum']['exact'], '5')
            self.assertEqual(trace(run.calculations, low.pk)['normalized']['exact'], '3/4')

    def test_one_person_households_get_zero_while_other_equal_criteria_keep_their_rules(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            app = self.applicant('HM-ONE', household_members=1)
            run = self.generate()
            run.clean()
            result = run.calculations[str(app.pk)]
            self.assertEqual(trace(run.calculations, app.pk)['normalized']['exact'], '0')
            for item in result['traces'][:-1]:
                self.assertEqual(item['constant_rule'], FULL_CONSTANTS)
            page = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]))
            self.assertContains(page, 'Every household has 1 member: normalized value = 0')

    def test_equal_households_still_hold_exact_boundary_ties(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            a = self.applicant('HM-TIE-A', household_members=4)
            b = self.applicant('HM-TIE-B', household_members=4)
            run = self.generate()
            self.assertEqual(run.calculations[str(a.pk)]['score_exact'], run.calculations[str(b.pk)]['score_exact'])
            self.assertTrue(run.calculations[str(a.pk)]['comparison']['capacity_boundary_tie'])
            self.assertEqual(trace(run.calculations, a.pk)['normalized']['exact'], '1')
            with self.assertRaisesMessage(ValidationError, 'holds exact ties'):
                service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                    application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic tied selection')
