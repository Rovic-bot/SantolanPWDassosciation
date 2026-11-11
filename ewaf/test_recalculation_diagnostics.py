import json
from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_UP
from unittest.mock import patch

from django.test import SimpleTestCase

from .recalculation_diagnostics import _Simulation, simulate_fixture, digest, RULES
from .recalculation_fixtures import load_scenario, load_pool, SCENARIOS, POOLS
from .ranking_diagnostics import FixtureIssue, BARRIERS

AT = '2026-10-15T01:00:00Z'


def observe(context='BASE', at=AT):
    return {'type': 'OBSERVE', 'context': 'SYN-G17-' + context, 'at': at}


def begin(context='BASE', trigger='INITIAL', actor='OFFICER', at=AT):
    return {'type': 'BEGIN', 'context': 'SYN-G17-' + context, 'trigger': trigger,
            'actor': 'SYN-G17-' + actor, 'at': at, 'reason': 'Synthetic test only.'}


def finish(attempt=1, at=AT):
    return {'type': 'FINISH', 'attempt': attempt, 'at': at}


class RecalculationDiagnosticTests(SimpleTestCase):
    def source(self):
        value = load_scenario('repeat-v1')
        value['events'] = [observe(), begin(), finish()]
        return value

    def replay(self, source):
        simulation = _Simulation(source)
        for event in source['events']:
            simulation.step(event)
        return simulation

    def initial(self):
        return self.replay(self.source())

    def blocked_after_initial(self, mutate):
        source = self.source()
        context = deepcopy(source['contexts']['SYN-G17-BASE'])
        context['versions']['evidence'] = 'SYN-G17-EVIDENCE-2'
        context['versions']['governance'] = 'SYN-G17-GOVERNANCE-2'
        mutate(context)
        source['contexts']['SYN-G17-NEXT'] = context
        source['events'] += [observe('NEXT'), begin('NEXT', 'EVIDENCE_REVIEW')]
        result = self.replay(source).report()
        self.assertEqual(len(result['results']), 1)
        self.assertIsNone(result['simulated_current_result'])
        self.assertNotIn('comparison', result['attempts'][-1])
        self.assertFalse(result['complete'])
        return result['attempts'][-1]['reasons']

    def test_initial_calculation_has_independent_expected_scores_and_ties(self):
        result = self.initial().report()
        self.assertTrue(result['complete'])
        self.assertEqual(result['simulated_current_result'], 1)
        row = result['results'][0]
        self.assertIsNone(row['previous_result'])
        self.assertEqual([g['score_0_1'] for g in row['comparison']['groups']], ['1', '0.5', '0'])
        self.assertEqual(row['comparison']['groups'][1]['synthetic_ids'], ['SYN-G16-B', 'SYN-G16-C'])
        self.assertEqual(row['comparison']['groups'][1]['position_start'], 2)
        self.assertEqual(row['comparison']['groups'][1]['position_end'], 3)
        self.assertEqual([i['calculation']['score_0_100'] for i in row['comparison']['items']], ['0', '50', '50', '100'])

    def test_input_and_configuration_recalculations_have_distinct_predecessors(self):
        result = simulate_fixture('history-v1')
        self.assertTrue(result['complete'])
        self.assertEqual([row['id'] for row in result['results']], [1, 2, 3])
        self.assertEqual([row['previous_result'] for row in result['results']], [None, 1, 2])
        self.assertEqual(len({row['digest'] for row in result['results']}), 3)
        self.assertEqual(result['simulated_current_result'], 3)

    def test_corrected_input_recomputes_the_entire_pool(self):
        result = simulate_fixture('history-v1')['results'][1]
        items = result['comparison']['items']
        self.assertEqual(len(items), 4)
        self.assertEqual(items[1]['calculation']['score_0_1'], '0.6')
        self.assertEqual(items[1]['calculation']['score_0_100'], '60')
        self.assertEqual([t['contribution'] for t in items[1]['calculation']['traces']], ['0.2', '0.1', '0.1', '0.1', '0.1'])
        self.assertEqual([g['score_0_1'] for g in result['comparison']['groups']], ['1', '0.6', '0.5', '0'])

    def test_configuration_change_retains_new_judgments_and_full_weights(self):
        first, corrected, revised = simulate_fixture('history-v1')['results']
        self.assertEqual(revised['snapshot']['pool']['contract']['judgments']['values']['SI:ES'], '2')
        self.assertEqual(first['snapshot']['pool']['contract']['judgments']['values']['SI:ES'], '1')
        a = corrected['comparison']['items'][1]['calculation']
        b = revised['comparison']['items'][1]['calculation']
        self.assertNotEqual(a['score_0_1'], b['score_0_1'])
        self.assertTrue(any(len(t['weight']) > 42 for t in b['traces']))
        self.assertEqual(a['settings'], b['settings'])

    def test_prior_snapshot_unchanged_after_recalculation(self):
        source = load_scenario('history-v1')
        simulation = _Simulation(source)
        for event in source['events'][:3]:
            simulation.step(event)
        old = simulation.report()['results'][0]
        for event in source['events'][3:]:
            simulation.step(event)
        self.assertEqual(simulation.report()['results'][0], old)
        self.assertEqual(old['snapshot']['pool']['candidates'][1]['inputs']['SI']['value'], '0.5')
        self.assertEqual(old['comparison']['groups'][1]['synthetic_ids'], ['SYN-G16-B', 'SYN-G16-C'])

    def test_nested_caller_source_mutation_cannot_change_recorded_snapshots(self):
        source = self.source()
        simulation = self.replay(source)
        before = simulation.report()
        source['contexts']['SYN-G17-BASE']['evidence']['SYN-G16-A']['SI']['state'] = 'REJECTED'
        source['contexts']['SYN-G17-BASE']['versions']['inputs'] = 'SYN-G17-FORGED'
        source['actors']['SYN-G17-OFFICER']['capability'] = 'READ_ONLY'
        source['rules']['pool'] = 'subset'
        self.assertEqual(simulation.report(), before)

    def test_nested_loader_input_and_returned_output_mutations_are_isolated(self):
        pool = load_pool('base-v1')
        with patch('ewaf.recalculation_fixtures.load_pool', return_value=pool):
            simulation = _Simulation(self.source())
        pool['candidates'][0]['inputs']['SI']['value'] = '1'
        for event in (observe(), begin(), finish()):
            simulation.step(event)
        before = simulation.report()
        changed = simulation.report()
        changed['results'][0]['snapshot']['pool']['candidates'][0]['inputs']['SI']['value'] = 'forged'
        changed['audit'][0]['event']['context'] = 'forged'
        changed['attempts'][0]['comparison']['groups'].clear()
        self.assertEqual(simulation.report(), before)
        self.assertEqual(before['results'][0]['comparison']['items'][0]['calculation']['score_0_1'], '0')

    def test_event_mutation_cannot_rewrite_audit(self):
        simulation = _Simulation(self.source())
        event = observe()
        simulation.step(event)
        before = simulation.report()
        event['context'] = 'SYN-G17-FORGED'
        self.assertEqual(simulation.report(), before)

    def test_versions_input_digests_and_pool_checksums_are_traceable(self):
        rows = simulate_fixture('history-v1')['results']
        for row in rows:
            snapshot = row['snapshot']
            self.assertEqual(row['context_digest'], digest('context', snapshot))
            self.assertEqual(snapshot['pool_checksum'], POOLS[snapshot['context']['pool_fixture']])
            self.assertEqual(snapshot['evaluation_timezone'], 'Asia/Manila')
            self.assertEqual(len(row['comparison']['items']), len(snapshot['pool']['contract']['pool_ids']))
        self.assertNotEqual(rows[0]['snapshot']['context']['versions']['inputs'], rows[1]['snapshot']['context']['versions']['inputs'])
        self.assertEqual(rows[1]['snapshot']['context']['versions']['inputs'], rows[2]['snapshot']['context']['versions']['inputs'])
        self.assertNotEqual(rows[1]['snapshot']['context']['versions']['configuration'], rows[2]['snapshot']['context']['versions']['configuration'])

    def test_reused_version_cannot_refer_to_changed_inputs(self):
        source = load_scenario('history-v1')
        source['contexts']['SYN-G17-CORRECTED']['versions']['inputs'] = 'SYN-G17-INPUTS-1'
        with self.assertRaisesRegex(FixtureIssue, 'G17_VERSION_CONTENT_CONFLICT'):
            _Simulation(source)

    def test_configuration_or_policy_version_rebinding_is_rejected(self):
        source = load_scenario('history-v1')
        source['contexts']['SYN-G17-CONFIGURATION']['versions']['configuration'] = 'SYN-G17-CONFIGURATION-1'
        with self.assertRaisesRegex(FixtureIssue, 'G17_VERSION_CONTENT_CONFLICT'):
            _Simulation(source)

    def test_stale_finish_preserves_previous_history_without_current_pointer(self):
        result = simulate_fixture('stale-v1')
        self.assertEqual(len(result['results']), 1)
        self.assertIsNone(result['simulated_current_result'])
        self.assertEqual(result['audit'][-1]['outcome'], 'SIMULATED_STALE')
        self.assertIn('SOURCE_CHANGED_DURING_CALCULATION', result['audit'][-1]['reasons'])
        self.assertEqual(result['pending_attempts'], [])

    def test_source_changed_then_restored_still_invalidates_pending_generation(self):
        source = load_scenario('history-v1')
        simulation = _Simulation(source)
        for event in (observe(), begin(), observe('CORRECTED'), observe(), finish()):
            simulation.step(event)
        self.assertEqual(simulation.report()['results'], [])
        self.assertIn('SOURCE_CHANGED_DURING_CALCULATION', simulation.report()['audit'][-1]['reasons'])

    def test_stale_expected_context_never_calculates(self):
        simulation = _Simulation(load_scenario('history-v1'))
        simulation.step(observe('CORRECTED'))
        with patch('ewaf.recalculation_diagnostics._evaluate_payload') as calculation:
            outcome = simulation.step(begin())
        calculation.assert_not_called()
        self.assertIn('EXPECTED_CONTEXT_STALE', outcome['reasons'])

    def test_missing_values_do_not_fall_back_or_compare_a_subset(self):
        result = simulate_fixture('incomplete-v1')
        self.assertEqual(len(result['results']), 1)
        self.assertIsNone(result['simulated_current_result'])
        self.assertIn('VALUE_MISSING', result['attempts'][-1]['reasons'])
        self.assertIn('CALCULATION_INCOMPLETE', result['attempts'][-1]['reasons'])
        self.assertNotIn('comparison', result['attempts'][-1])

    def test_zero_input_is_present_and_is_not_missing(self):
        result = self.initial().report()['results'][0]
        self.assertEqual(result['comparison']['items'][0]['calculation']['score_0_1'], '0')
        self.assertTrue(result['comparison']['items'][0]['calculation']['complete'])

    def test_latest_missing_declared_rejected_or_disputed_blocks(self):
        for state, code in (('MISSING', 'CRITERION_MISSING'), ('DECLARED', 'CRITERION_NOT_VERIFIED'),
                            ('NEEDS_REVIEW', 'CRITERION_NOT_VERIFIED'), ('REJECTED', 'CRITERION_REJECTED')):
            with self.subTest(state=state):
                reasons = self.blocked_after_initial(lambda c: c['evidence']['SYN-G16-B']['SI'].update(state=state))
                self.assertIn(code, reasons)
        self.assertIn('EVIDENCE_DISPUTED', self.blocked_after_initial(
            lambda c: c['evidence']['SYN-G16-B']['SI'].update(disputed=True)))

    def test_stale_and_expired_evidence_blocks(self):
        self.assertIn('SOURCE_CHANGED', self.blocked_after_initial(
            lambda c: c['evidence']['SYN-G16-B']['SI'].update(source_current=False)))
        self.assertIn('EVIDENCE_EXPIRED', self.blocked_after_initial(
            lambda c: c['evidence']['SYN-G16-B']['SI'].update(expires_on='2026-10-14')))

    def test_expiry_is_inclusive_but_midnight_blocks_promotion(self):
        simulation = _Simulation(self.source())
        simulation.step(observe())
        simulation.step(begin())
        outcome = simulation.step(finish(at='2026-10-15T16:00:00Z'))
        self.assertIn('EVIDENCE_EXPIRED', outcome['reasons'])
        self.assertIn('EVALUATION_DATE_CHANGED', outcome['reasons'])
        self.assertEqual(simulation.report()['results'], [])
        self.assertTrue(self.initial().report()['complete'])

    def test_read_observation_after_expiry_invalidates_old_current_result(self):
        simulation = self.initial()
        old = simulation.report()['results']
        simulation.step(observe(at='2026-10-16T01:00:00Z'))
        self.assertIsNone(simulation.report()['simulated_current_result'])
        self.assertEqual(simulation.report()['results'], old)

    def test_simulated_b1_b2_b3_and_integrity_findings_block(self):
        for code in ('EVIDENCE_MAPPING_INVALID', 'PR_FINDINGS_INCOMPLETE', 'PR_ATTESTATION_REQUIRED',
                     'REUSABLE_TYPE_MISMATCH', 'ARTIFACT_INTEGRITY_FAILED'):
            with self.subTest(code=code):
                self.assertIn(code, self.blocked_after_initial(
                    lambda c: c['evidence']['SYN-G16-B']['PR'].update(findings=[code])))

    def test_stale_eligibility_terms_and_binding_never_promote(self):
        for field, code in (('eligibility_current', 'ELIGIBILITY_STALE'),
                            ('terms_current', 'TERMS_CHANGED'), ('binding_current', 'BINDING_INVALID')):
            with self.subTest(field=field):
                self.assertIn(code, self.blocked_after_initial(lambda c: c.update({field: False})))

    def test_unresolved_policies_have_explicit_diagnostics(self):
        result = simulate_fixture('unresolved-v1')
        self.assertIn('POLICY_UNRESOLVED:revisions', result['attempts'][-1]['reasons'])
        for policy in ('admission', 'cutoff', 'evidence', 'normalization', 'ties', 'authority', 'pa_scope'):
            self.assertIn('POLICY_UNRESOLVED:' + policy,
                          self.blocked_after_initial(lambda c: c.update(unresolved=[policy])))

    def test_unresolved_scope_triggers_do_not_invent_policy(self):
        for trigger, code in (('POOL_CHANGE', 'POOL_CHANGE_POLICY_UNRESOLVED'),
                              ('TERMS_CHANGE', 'G06_B2_B3_UNAVAILABLE'), ('PA_CHANGE', 'PA_SCOPE_POLICY_UNRESOLVED')):
            simulation = self.initial()
            result = simulation.step(begin(trigger=trigger))
            self.assertIn(code, result['reasons'])
            self.assertEqual(len(simulation.report()['results']), 1)

    def test_wrong_change_trigger_blocks_recalculation(self):
        simulation = _Simulation(load_scenario('history-v1'))
        for event in (observe(), begin(), finish(), observe('CORRECTED')):
            simulation.step(event)
        outcome = simulation.step(begin('CORRECTED', 'CONFIGURATION_REVISION'))
        self.assertIn('RECALCULATION_TRIGGER_MISMATCH', outcome['reasons'])

    def test_policy_version_only_change_is_retained_separately(self):
        source = self.source()
        new = deepcopy(source['contexts']['SYN-G17-BASE'])
        new['versions']['scoring_policy'] = 'SYN-G17-SCORING-POLICY-2'
        source['contexts']['SYN-G17-NEXT'] = new
        source['events'] += [observe('NEXT'), begin('NEXT', 'CONFIGURATION_REVISION'), finish(2)]
        rows = self.replay(source).report()['results']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['comparison'], rows[1]['comparison'])
        self.assertNotEqual(rows[0]['context_digest'], rows[1]['context_digest'])

    def test_evidence_review_can_append_new_snapshot_without_changed_math(self):
        source = self.source()
        new = deepcopy(source['contexts']['SYN-G17-BASE'])
        new['versions']['evidence'] = 'SYN-G17-EVIDENCE-2'
        new['evidence']['SYN-G16-B']['SI']['expires_on'] = '2026-10-16'
        source['contexts']['SYN-G17-NEXT'] = new
        source['events'] += [observe('NEXT'), begin('NEXT', 'EVIDENCE_REVIEW'), finish(2)]
        rows = self.replay(source).report()['results']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['comparison'], rows[1]['comparison'])

    def test_explicit_date_reevaluation_requires_current_unexpired_context(self):
        source = self.source()
        for findings in source['contexts']['SYN-G17-BASE']['evidence'].values():
            for row in findings.values():
                row['expires_on'] = '2026-10-17'
        new = deepcopy(source['contexts']['SYN-G17-BASE'])
        new['evaluation_date'] = '2026-10-16'
        source['contexts']['SYN-G17-NEXT'] = new
        later = '2026-10-16T01:00:00Z'
        source['events'] += [observe('NEXT', later), begin('NEXT', 'DATE_REEVALUATION', at=later), finish(2, later)]
        rows = self.replay(source).report()['results']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['comparison'], rows[1]['comparison'])
        self.assertNotEqual(rows[0]['context_digest'], rows[1]['context_digest'])

    def test_stale_attempt_can_be_followed_by_fresh_complete_recalculation(self):
        source = load_scenario('history-v1')
        simulation = _Simulation(source)
        for event in (observe(), begin(), observe('CORRECTED'), finish(),
                      begin('CORRECTED', 'RETRY'), finish(2)):
            simulation.step(event)
        result = simulation.report()
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(result['audit'][3]['outcome'], 'SIMULATED_STALE')
        self.assertEqual(result['audit'][-1]['outcome'], 'SIMULATED_PROMOTED')

    def test_missing_candidate_evidence_cannot_silently_shrink_pool(self):
        for remove in ('candidate', 'criterion'):
            source = self.source()
            evidence = source['contexts']['SYN-G17-BASE']['evidence']
            if remove == 'candidate':
                del evidence['SYN-G16-B']
            else:
                del evidence['SYN-G16-B']['SI']
            with self.assertRaisesRegex(FixtureIssue, 'G17_SCHEMA_INVALID'):
                _Simulation(source)

    def test_candidate_pool_change_remains_blocked_even_with_fresh_versions(self):
        source = self.source()
        precision = load_scenario('precision-v1')['contexts']['SYN-G17-PRECISION']
        for key in precision['versions']:
            precision['versions'][key] += '-NEXT'
        source['contexts']['SYN-G17-NEXT'] = precision
        source['events'] += [observe('NEXT'), begin('NEXT', 'CONFIGURATION_REVISION')]
        result = self.replay(source).report()
        self.assertIn('POOL_CHANGE_POLICY_UNRESOLVED', result['attempts'][-1]['reasons'])
        self.assertIsNone(result['simulated_current_result'])

    def test_unauthorized_inactive_unknown_or_foreign_scope_actor_never_calculates(self):
        for changes in ({'active': False}, {'capability': 'READ_ONLY'}, {'scope': 'SYN-G17-OTHER'}):
            source = self.source()
            source['actors']['SYN-G17-OFFICER'].update(changes)
            simulation = _Simulation(source)
            simulation.step(observe())
            with patch('ewaf.recalculation_diagnostics._evaluate_payload') as calculation:
                result = simulation.step(begin())
            calculation.assert_not_called()
            self.assertEqual(result['outcome'], 'SIMULATED_DENIED')
            self.assertNotIn('snapshot', simulation.report()['attempts'][0])
        simulation = _Simulation(self.source())
        simulation.step(observe())
        self.assertEqual(simulation.step(begin(actor='UNKNOWN'))['outcome'], 'SIMULATED_DENIED')

    def test_denied_request_does_not_invalidate_a_valid_existing_result(self):
        simulation = self.initial()
        simulation.step(begin(actor='READER'))
        self.assertEqual(simulation.report()['simulated_current_result'], 1)
        self.assertEqual(len(simulation.report()['results']), 1)

    def test_simulated_audit_retains_actor_reason_versions_outcome_and_digest(self):
        result = self.initial().report()
        attempt = result['attempts'][0]
        self.assertEqual(attempt['actor'], 'SYN-G17-OFFICER')
        self.assertEqual(attempt['reason'], 'Synthetic test only.')
        self.assertEqual(result['audit'][-1]['outcome'], 'SIMULATED_PROMOTED')
        self.assertEqual(result['audit'][-1]['versions'], attempt['versions'])
        self.assertEqual(result['audit'][-1]['actor'], attempt['actor'])
        self.assertEqual(result['audit'][-1]['reason'], attempt['reason'])
        for kind, rows in (('attempt', result['attempts']), ('result', result['results']), ('audit', result['audit'])):
            for row in rows:
                payload = {k: v for k, v in row.items() if k != 'digest'}
                self.assertEqual(row['digest'], digest(kind, payload))
                self.assertEqual(row['mode'], 'SIMULATION_ONLY')
                self.assertFalse(row['operational_ready'])
                self.assertFalse(row['effective_authorization'])

    def test_identical_and_retry_requests_reuse_result_append_attempts(self):
        result = simulate_fixture('repeat-v1')
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(len(result['attempts']), 3)
        self.assertEqual([r['outcome'] for r in result['attempts'][1:]], ['SIMULATED_REUSED'] * 2)
        self.assertEqual([r['result'] for r in result['attempts'][1:]], [1, 1])

    def test_reuse_does_not_call_calculator(self):
        simulation = self.initial()
        with patch('ewaf.recalculation_diagnostics._evaluate_payload') as calculator:
            simulation.step(begin())
            simulation.step(begin(trigger='RETRY'))
        calculator.assert_not_called()

    def test_competing_same_context_completions_only_create_one_result(self):
        simulation = _Simulation(self.source())
        for event in (observe(), begin(), begin(), finish(2), finish(1)):
            simulation.step(event)
        result = simulation.report()
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['audit'][-1]['outcome'], 'SIMULATED_REUSED')

    def test_repeated_finish_never_restores_old_current_result(self):
        source = load_scenario('history-v1')
        simulation = self.replay(source)
        before = simulation.report()['results']
        simulation.step(finish(1))
        self.assertEqual(simulation.report()['results'], before)
        self.assertEqual(simulation.report()['simulated_current_result'], 3)
        self.assertEqual(simulation.report()['audit'][-1]['outcome'], 'SIMULATED_FINISH_REPEATED')

    def test_unfinished_run_cannot_become_current(self):
        simulation = _Simulation(self.source())
        simulation.step(observe())
        simulation.step(begin())
        result = simulation.report()
        self.assertFalse(result['complete'])
        self.assertEqual(result['pending_attempts'], [1])
        self.assertEqual(result['results'], [])

    def test_finishing_blocked_attempt_cannot_promote(self):
        simulation = _Simulation(self.source())
        simulation.step(observe())
        simulation.step(begin(actor='READER'))
        self.assertIn('ATTEMPT_NOT_PENDING', simulation.step(finish())['reasons'])

    def test_pinned_scenarios_are_repeatable_without_clock_or_uuid(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                self.assertEqual(simulate_fixture(name), simulate_fixture(name))

    def test_precision_near_ties_and_ambient_context_preserved(self):
        expected = simulate_fixture('precision-v1')
        groups = expected['results'][0]['comparison']['groups']
        a, b = [Decimal(g['score_0_1']) for g in groups]
        self.assertNotEqual(a, b)
        self.assertEqual(float(a), float(b))
        self.assertEqual(format(a, '.2f'), format(b, '.2f'))
        with localcontext() as context:
            context.prec, context.rounding = 3, ROUND_UP
            self.assertEqual(simulate_fixture('precision-v1'), expected)

    def test_capacity_and_ties_never_select_waitlist_or_activate(self):
        for name in SCENARIOS:
            result = simulate_fixture(name)
            text = json.dumps(result)
            for key in ('"selected"', '"waitlisted"', '"approved"', '"rank"', '"winner"'):
                self.assertNotIn(key, text)
            self.assertFalse(result['operational_ready'])
            self.assertFalse(result['effective_authorization'])
            self.assertTrue(set(BARRIERS) <= set(result['barriers']))

    def test_unknown_path_real_identifier_or_synthetic_flag_rejected(self):
        for value in ('../history-v1', 'PWD-123', 1, {'synthetic': True}, None):
            self.assertEqual(simulate_fixture(value)['reasons'], ['G17_FIXTURE_NOT_ALLOWLISTED'])

    def test_pins_required_and_registries_immutable(self):
        for registry in (SCENARIOS, POOLS):
            with self.assertRaises(TypeError):
                registry['new'] = 'forged'
        with patch('pathlib.Path.open') as opened:
            opened.return_value.__enter__.return_value.read.return_value = b'{}'
            self.assertEqual(simulate_fixture('history-v1')['reasons'], ['G17_FIXTURE_CHECKSUM_MISMATCH'])

    def test_missing_fixture_is_explicit_blocker(self):
        with patch('pathlib.Path.open', side_effect=OSError):
            self.assertEqual(simulate_fixture('history-v1')['reasons'], ['G17_FIXTURE_UNAVAILABLE'])

    def test_missing_rules_or_approval_fields_never_supply_authority(self):
        for changes in ({'rules': {}}, {'approved': True}, {'schema_version': True}):
            source = self.source()
            source.update(changes)
            with self.assertRaises(FixtureIssue):
                _Simulation(source)

    def test_events_require_reason_strict_fields_and_monotonic_time(self):
        for event in ({**begin(), 'reason': ''}, {**begin(), 'score': '1'},
                      {**begin(), 'actor': '123'}, {**begin(), 'trigger': 'AUTO_SELECT'},
                      observe(at='bad'), finish(True), finish(999)):
            with self.subTest(event=event):
                simulation = _Simulation(self.source())
                with self.assertRaises(FixtureIssue):
                    simulation.step(event)
        simulation = self.initial()
        with self.assertRaisesRegex(FixtureIssue, 'G17_TIME_REVERSED'):
            simulation.step(observe(at='2026-10-14T01:00:00Z'))

    def test_invalid_context_and_excess_events_are_bounded(self):
        simulation = self.initial()
        with self.assertRaisesRegex(FixtureIssue, 'G17_CONTEXT_UNKNOWN'):
            simulation.step(observe('UNKNOWN'))
        source = self.source()
        source['events'] = [observe()] * 65
        with self.assertRaisesRegex(FixtureIssue, 'G17_RESOURCE_LIMIT'):
            _Simulation(source)

    def test_false_completeness_with_present_score_cannot_promote(self):
        simulation = _Simulation(self.source())
        simulation.step(observe())
        with patch('ewaf.recalculation_diagnostics._evaluate_payload', return_value={
                'complete': False, 'score_0_1': '1', 'reasons': [{'code': 'SCORE_RANGE_ANOMALY'}]}):
            result = simulation.step(begin())
        self.assertIn('SCORE_RANGE_ANOMALY', result['reasons'])
        self.assertEqual(simulation.report()['results'], [])
