"""Owner-selected full equal-value credit, with retained per-program bounds."""
from copy import deepcopy
from fractions import Fraction
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import operational_services as operations, shared_calculation_rules as rules
from .operational_models import OperationalConfiguration, OperationalRun
from .revised import live_services, live_math
from .revised.live_models import SharedDatasetPolicy, DatasetInputReview
from .test_rolling_pool import RollingPoolTests as Rolling
from .test_composite_ses import fixture, endpoints, FORMULA, methods


def full_content(content):
    result = deepcopy(content)
    result['choices']['constant_rule'] = {'value': rules.FULL_CONSTANTS, 'specified': True}
    result['choices']['method_rules'] = {'value': rules.FULL_METHOD, 'specified': True}
    result[rules.MARKER] = {'version': rules.CONTRACT, 'scope': rules.SCOPE}
    return result


class FullCreditArithmeticTests(SimpleTestCase):
    def test_equal_values_receive_full_weight_and_ses_retains_4ps_adjustment(self):
        policy = {'method': methods.COMPOSITE, 'ses_formula': FORMULA, 'constant_rule': rules.FULL_CONSTANTS}
        result = fixture({'a': (40000, 0, 'Unemployed', 0, 3), 'b': (40000, 1, 'Unemployed', 0, 3)}, policy=policy)
        self.assertEqual(result['a']['score_exact'], '24/25')
        self.assertEqual(result['b']['score_exact'], '1')
        for key in result:
            self.assertEqual(len(result[key]['traces']), 4)
            for trace in result[key]['traces']:
                self.assertEqual(trace['minimum'], trace['maximum'])
                self.assertEqual(trace['constant_rule'], rules.FULL_CONSTANTS)
                self.assertGreater(Fraction(trace['contribution']['exact']), 0)
        single = fixture({'one': (900000, 1, 'Full-Time Worker', 12, 1)}, policy=policy)
        self.assertEqual(single['one']['score_exact'], '1')

    def test_varied_values_keep_exact_pool_minmax_and_existing_zero_endpoints(self):
        rows = endpoints() | {'higher': (200000, 0, 'Seasonal Worker', 5, 10)}
        with patch('django.utils.timezone.now', return_value=timezone.now()):
            original = fixture(rows)
            changed = fixture(rows, policy={'method': methods.COMPOSITE, 'ses_formula': FORMULA,
                                           'constant_rule': rules.FULL_CONSTANTS})
        self.assertEqual(changed, original)
        self.assertEqual(changed['higher']['traces'][0]['maximum']['exact'], '200000')

    def test_applicant_errors_are_not_mislabeled_as_scoring_configuration(self):
        from .presentation import messages_for_officers
        messages = messages_for_officers(['REF: QUALIFICATION_FAILED', 'REF: IDENTITY_REVIEW_REQUIRED',
            'REF: ELIGIBILITY_STALE', 'eligible_pool: at least one fully verified eligible application is required'])
        self.assertIn('qualification requirements', messages[0])
        self.assertIn('identity evidence', messages[1])
        self.assertIn('changed after eligibility', messages[2])
        self.assertIn('No eligible applicants', messages[3])
        self.assertNotIn('Scoring settings', ' '.join(messages))


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class SharedCalculationRulesTests(TransactionTestCase):
    setUp = Rolling.setUp
    draft = Rolling.draft
    approve = Rolling.approve
    bind = Rolling.bind
    publish = Rolling.publish
    applicant = Rolling.applicant
    pool = Rolling.pool
    generate = Rolling.generate

    def activate(self):
        return self.approve(self.draft(full_content(self.content)))

    def test_shared_rule_changes_new_runs_preserves_old_history_and_shows_every_contribution(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            old = self.generate()
            retained = deepcopy(old.payload())
            old_binding = deepcopy(self.configuration.payload())
            token = operations.context(self.program.pk, user=self.user)
            approved = self.activate()
            with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
                operations.generate(self.program.pk, user=self.user, expected=token,
                    reason='SYNTHETIC stale rule', request_key=uuid4())
            with operations.fence(self.program.pk, self.user) as (actor, program, applications):
                with self.assertRaisesMessage(ValidationError, 'equal-value calculation rule changed'):
                    operations.current_result_run(program, applications, actor, old.pk)
            run = self.generate()
            run.clean()
            self.assertEqual(run.snapshot[rules.KEY]['id'], approved.pk)
            self.assertEqual(run.configuration_id, old.configuration_id)
            for key, result in run.calculations.items():
                traces = {row['criterion']: row for row in result['traces']}
                old_traces = {row['criterion']: row for row in old.calculations[key]['traces']}
                for code in ('SES', 'ES', 'PA'):
                    self.assertGreater(Fraction(traces[code]['contribution']['exact']), 0)
                    self.assertEqual(traces[code]['minimum'], old_traces[code]['minimum'])
                    self.assertEqual(traces[code]['maximum'], old_traces[code]['maximum'])
                    self.assertEqual(traces[code]['weight'], old_traces[code]['weight'])
                self.assertEqual(traces['HM'], old_traces['HM'])
            old.refresh_from_db(); old.clean()
            self.configuration.refresh_from_db()
            self.assertEqual(old.payload(), retained)
            self.assertEqual(self.configuration.payload(), old_binding)
            page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
            self.assertTrue(page.context['ready'])
            for code in ('SES', 'ES', 'PA', 'HM'):
                self.assertContains(page, f'data-contribution="{code}"', count=2)
            self.assertContains(page, 'Total / 100')
            guide = self.client.get(reverse('ewaf:operational_calculation_guide', args=[self.program.pk]))
            self.assertContains(guide, 'use normalized value 1')
            self.assertContains(guide, 'Equal income: I = 1; SES = 1')
            bad = deepcopy(run.snapshot)
            bad[rules.KEY]['constant_rule'] = 'zero_contribution_v1'
            with self.assertRaisesMessage(ValidationError, 'exact approved version'):
                live_math.calculations(bad, run.configuration)

    def test_reviewed_inputs_keep_their_bindings_when_shared_math_changes(self):
        # This is the manually accepted source path used by PA Focus.
        self.content = deepcopy(self.document_content)
        self.publish()
        # Use its established evidence fixture rather than automatic inputs.
        from .test_composite_ses import CompositeSesWorkflowTests as Composite
        a, ar = Composite.applicant(self, 'FULL-MANUAL-A')
        b, br = Composite.applicant(self, 'FULL-MANUAL-B', prior=True)
        Composite.accept(self, a, ar, low=True)
        Composite.accept(self, b, br)
        before = list(DatasetInputReview.objects.values())
        old = self.generate()
        self.activate()
        run = self.generate()
        run.clean(); old.clean()
        self.assertEqual(list(DatasetInputReview.objects.values()), before)
        self.assertEqual(run.configuration_id, old.configuration_id)
        for key, result in old.calculations.items():
            self.assertEqual(run.calculations[key]['traces'], result['traces'])
            self.assertEqual(run.calculations[key]['score_exact'], result['score_exact'])

    def test_approval_permission_rule_pairing_and_audit_rollback(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        from .revised import contracts
        invalid = full_content(self.content)
        invalid['choices']['method_rules']['value'] = 'dataset_composite_ses_v1'
        self.assertTrue(any('full-contribution' in item for item in contracts.findings(invalid)))
        self.pool()
        draft = self.draft(full_content(self.content))
        viewer = get_user_model().objects.create_user('rule-viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operations.VIEW)
        with self.assertRaises(PermissionDenied):
            live_services.approve(draft.pk, user=viewer, expected=draft.digest,
                reviewed_groups=['A', 'B', 'C'], reason='SYNTHETIC unauthorized rule')
        count = SharedDatasetPolicy.objects.count()
        with patch('django.contrib.admin.models.LogEntry.objects.create', side_effect=ValidationError('SYNTHETIC audit failure')):
            with self.assertRaises(ValidationError):
                self.approve(draft)
        self.assertEqual(SharedDatasetPolicy.objects.count(), count)
        self.assertIsNone(rules.current(self.configuration))

    def test_changed_member_review_is_specific_and_still_blocks_ranking(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            self.activate()
            a.member.version += 1
            a.member.save(update_fields=['version'])
            page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
            self.assertFalse(page.context['ready'])
            self.assertContains(page, 'Review the flagged applicants before ranking.')
            self.assertContains(page, 'changed after eligibility was reviewed')
            self.assertNotContains(page, 'Scoring settings are incomplete')
            self.assertFalse(OperationalRun.objects.exists())
