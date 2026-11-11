"""Policy-draft examples only: no database, approval, weights or real member data."""
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from .revised import engine, policy
from .revised.math import CalculationError, CRITERIA


def refreeze(data):
    return engine.freeze_pool(**{key: data[key] for key in
        ('program', 'version', 'cutoff', 'expected_ids', 'applicants', 'unresolved_ids')})


class RevisedPolicyTests(TestCase):
    def setUp(self):
        self.draft = policy.load_draft()

    def test_source_mapping_directions_and_bounds_are_documented_not_authorized(self):
        data = self.draft.data
        self.assertEqual(data['document_rules']['employment_encoding']['mapping'], {
            'Full-Time Worker': 1, 'Part-Time Worker': 2, 'Seasonal Worker': 3, 'Unemployed': 4})
        self.assertEqual(data['document_rules']['directions']['values'], {
            'HI': 'inverse', 'SI': 'increasing', 'ES': 'increasing', 'PA': 'inverse', 'HM': 'increasing'})
        self.assertEqual(data['document_rules']['normalization']['method'], 'dataset-minmax-v1')
        self.assertIsNone(data['document_rules']['normalization']['numerical_bounds'])
        self.assertIsNone(data['authorization'])
        self.assertIsNone(data['weight_authorization_reference'])
        self.assertTrue(all(item['status'] == 'PROPOSED_NOT_AUTHORIZED' for item in data['proposals'].values()))

    def test_required_open_decisions_remain_explicit(self):
        codes = {item['code'] for item in self.draft.data['unresolved_decisions']}
        self.assertTrue({'CONSTANT_COLUMNS', 'INCOME_SOURCE_RULES', 'EMPLOYMENT_UNLISTED',
                         'EVIDENCE_ACCEPTANCE', 'HISTORY_COMPLETENESS', 'SI_RUBRIC_AUTHORITY',
                         'RANKING_AND_TIES', 'COMPLETE_POOL_AND_CORRECTIONS', 'WEIGHT_AUTHORITY'} <= codes)

    def test_policy_review_does_not_require_pre_application_numerical_bounds(self):
        status = policy.policy_readiness(self.draft)
        self.assertFalse(status['ready'])
        self.assertFalse(status['numerical_bounds_required_before_opening'])
        self.assertFalse(status['program_binding']['ready'])
        data_status = policy.applicant_data_readiness()
        self.assertEqual(data_status['status'], 'NOT_EVALUATED')
        self.assertIsNone(data_status['bounds'])
        self.assertEqual(data_status['issues'], [])
        self.assertFalse(any('BOUND' in item['code'] for item in status['decisions']))

    def test_complete_synthetic_data_does_not_make_policy_or_program_ready(self):
        data = policy.demonstrate(self.draft).data
        self.assertEqual(data['applicant_data_readiness']['status'], 'SYNTHETIC_READY')
        self.assertFalse(data['applicant_data_readiness']['official_ready'])
        self.assertFalse(data['policy_readiness']['ready'])
        self.assertFalse(data['policy_readiness']['program_binding']['ready'])
        self.assertIsNone(data['policy_snapshot']['authorization'])
        self.assertFalse(data['official'])

    def test_document_example_scores_and_evaluation_time_bounds(self):
        result = policy.demonstrate(self.draft).data['result']
        expected_bounds = [('5000', '20000'), ('1', '4'), ('1', '4'), ('0', '3'), ('2', '6')]
        self.assertEqual([(item['lower']['exact'], item['upper']['exact']) for item in result['bounds']], expected_bounds)
        self.assertEqual([row['score_0_100']['exact'] for row in result['applicants']], ['839/10', '7537/120', '611/50'])
        self.assertEqual([row['display_score'] for row in result['applicants']], ['83.90', '62.81', '12.22'])
        self.assertTrue(all(row['classification'] is None for row in result['applicants']))

    def test_different_complete_pool_recomputes_bounds_and_preserves_previous_run(self):
        first = policy.demonstrate(self.draft)
        retained = first.snapshot
        data = policy.synthetic_pool().data
        data['version'] += 1
        data['applicants'][2]['inputs']['HI']['value'] = '30000'
        data['applicants'][2]['inputs']['HI']['evidence_version'] += 1
        second = policy.demonstrate(self.draft, pool=refreeze(data))
        self.assertEqual(second.data['result']['bounds'][0]['upper']['exact'], '30000')
        self.assertNotEqual(first.data['result']['applicants'][1]['score_0_100'],
                            second.data['result']['applicants'][1]['score_0_100'])
        self.assertEqual(first.snapshot, retained)
        self.assertEqual(policy.replay(first).snapshot, retained)
        self.assertEqual(self.draft.digest, policy.load_draft().digest)

    def test_constant_columns_remain_unresolved_without_imputed_scores(self):
        for code in CRITERIA:
            with self.subTest(criterion=code):
                data = policy.synthetic_pool().data
                value = data['applicants'][0]['inputs'][code]['value']
                for row in data['applicants']:
                    row['inputs'][code]['value'] = value
                pool = refreeze(data)
                status = policy.applicant_data_readiness(pool)
                self.assertEqual(status['status'], 'BLOCKED')
                self.assertIn(code, status['issues'][0])
                with self.assertRaisesRegex(CalculationError, 'Constant-value'):
                    policy.demonstrate(self.draft, pool=pool)

    def test_single_applicant_pool_is_not_given_a_fabricated_normalized_value(self):
        data = policy.synthetic_pool().data
        data['applicants'] = data['applicants'][:1]
        data['expected_ids'] = ['A']
        with self.assertRaisesRegex(CalculationError, 'Constant-value'):
            policy.demonstrate(self.draft, pool=refreeze(data))

    def test_missing_stale_disputed_and_unlisted_inputs_block_without_imputation(self):
        for field, value in [('value', None), ('state', 'DECLARED'), ('stale', True), ('disputed', True)]:
            with self.subTest(field=field):
                data = policy.synthetic_pool().data
                data['applicants'][0]['inputs']['SI'][field] = value
                forged = engine.FrozenPool(engine.canonical(data))
                status = policy.applicant_data_readiness(forged)
                self.assertFalse(status['ready'])
                self.assertIsNone(status['bounds'])
        data = policy.synthetic_pool().data
        data['applicants'][0]['inputs']['ES']['value'] = 'Self-employed'
        with self.assertRaisesRegex(CalculationError, 'unlisted'):
            refreeze(data)

    def test_incomplete_history_does_not_become_zero(self):
        for complete in (None, False):
            with self.subTest(complete=complete):
                data = policy.synthetic_pool().data
                data['applicants'][1]['inputs']['PA']['history_complete'] = complete
                self.assertEqual(data['applicants'][1]['inputs']['PA']['value'], '0')
                with self.assertRaisesRegex(CalculationError, 'Incomplete PA history'):
                    policy.demonstrate(self.draft, pool=refreeze(data))

    def test_filtered_or_unresolved_pool_cannot_define_bounds(self):
        data = policy.synthetic_pool().data
        data['applicants'] = data['applicants'][:2]
        with self.assertRaisesRegex(CalculationError, 'complete frozen eligible inventory'):
            refreeze(data)
        data = policy.synthetic_pool().data
        data['unresolved_ids'] = ['D']
        with self.assertRaisesRegex(CalculationError, 'Unresolved'):
            refreeze(data)

    def test_proposed_competition_ranking_holds_boundary_tie(self):
        data = policy.synthetic_pool().data
        first, second = data['applicants'][:2]
        for code in CRITERIA:
            second['inputs'][code]['value'] = first['inputs'][code]['value']
        result = policy.demonstrate(self.draft, pool=refreeze(data), capacity=1).data['result']
        self.assertEqual([row['rank'] for row in result['applicants']], [1, 1, 3])
        self.assertTrue(result['capacity_boundary_tie'])
        self.assertTrue(all('synthetic demonstration only' in row['human_decision'] for row in result['applicants']))

    def test_revising_shared_draft_cannot_mutate_snapshot_or_retained_result(self):
        first = policy.demonstrate(self.draft)
        revised = policy.revise_proposal(self.draft, expected_digest=self.draft.digest,
            name='assessment_periods', description='Synthetic alternative period for review, not approval.')
        self.assertNotEqual(revised.digest, self.draft.digest)
        self.assertEqual(revised.data['previous_digest'], self.draft.digest)
        self.assertEqual(revised.data['revision'], 2)
        self.assertEqual(first.data['policy_reference'], self.draft.reference)
        with patch.object(policy, 'load_draft', side_effect=AssertionError('Do not consult the current draft')):
            self.assertEqual(policy.replay(first).digest, first.digest)
        self.assertEqual(self.draft.digest, policy.load_draft(1).digest)
        with self.assertRaises(FrozenInstanceError):
            self.draft.snapshot = revised.snapshot
        detached = self.draft.data
        detached['proposals']['si_rubric']['description'] = 'Changed local copy'
        self.assertNotEqual(detached, self.draft.data)

    def test_stale_revision_unknown_version_and_overwritten_file_are_rejected(self):
        with self.assertRaisesRegex(CalculationError, 'draft changed'):
            policy.revise_proposal(self.draft, expected_digest='0' * 64, name='si_rubric', description='Stale')
        with self.assertRaisesRegex(CalculationError, 'Unknown retained'):
            policy.load_draft(999)
        with patch.object(Path, 'read_bytes', return_value=b'{"status":"APPROVED"}'):
            with self.assertRaisesRegex(CalculationError, 'Retained policy content changed'):
                policy.load_draft()

    def test_forged_authority_and_fixed_bounds_are_rejected(self):
        for field, value in [('status', 'APPROVED'), ('authorization', {'synthetic_forgery': True}),
                             ('weight_authorization_reference', 'synthetic-forged-weight-approval')]:
            with self.subTest(field=field):
                data = self.draft.data
                data[field] = value
                with self.assertRaisesRegex(CalculationError, 'no authority may be fabricated'):
                    policy.PolicyDraft(engine.canonical(data))
        data = self.draft.data
        data['document_rules']['normalization']['numerical_bounds'] = {'HI': {'min': 0, 'max': 20000}}
        with self.assertRaisesRegex(CalculationError, 'evaluation-time dataset bounds'):
            policy.PolicyDraft(engine.canonical(data))
        data = self.draft.data
        data['document_rules']['aggregation']['formula'] = 'Manually replace the final score'
        with self.assertRaisesRegex(CalculationError, 'Retain the document rules'):
            policy.PolicyDraft(engine.canonical(data))

    def test_replay_detects_tampered_policy_reference_or_manual_score(self):
        demonstration = policy.demonstrate(self.draft)
        for target in ('reference', 'score'):
            data = demonstration.data
            if target == 'reference':
                data['policy_reference']['digest'] = '0' * 64
            else:
                data['result']['applicants'][0]['score_0_100']['exact'] = '100'
            with self.assertRaisesRegex(CalculationError, 'does not replay'):
                policy.replay(policy.PolicyDemonstration(engine.canonical(data)))

    def test_real_data_is_not_certified_by_a_synthetic_adapter(self):
        data = policy.synthetic_pool().data
        data['synthetic'] = False
        readiness = policy.applicant_data_readiness(engine.FrozenPool(engine.canonical(data)))
        self.assertFalse(readiness['ready'])
        self.assertFalse(readiness['official_ready'])
        self.assertIn('not implemented', readiness['issues'][0])
