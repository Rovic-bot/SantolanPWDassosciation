"""Saved score explanations, with independently specified arithmetic examples."""
from copy import deepcopy
from decimal import localcontext
from fractions import Fraction
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.db import models
from django.test import Client, SimpleTestCase, TransactionTestCase
from django.urls import reverse

from members.models import Member
from membership.tests import grant
from programs.tests import create_program
from .operational_models import OperationalRun, OperationalDecision
from .operational_testsupport import OperationalHelpers
from .score_breakdown import build_breakdown, calculation_guide


def saved_example():
    # Four equal weights: 1*25 + 1*25 + 1*25 + .5*25 = 87.5.
    codes = ('SI', 'ES', 'PA', 'ND')
    inputs = dict(zip(codes, ({'value': 'income_0_5000', 'unit': 'category'},
        {'value': 'retired', 'unit': 'category'}, {'value': 0, 'unit': 'records'},
        {'value': 4, 'unit': 'persons'})))
    traces = [dict(criterion=code, lower='0', upper=upper, value=value, weight='0.25',
        normalized=normalized, contribution=contribution, direction=direction)
        for code, upper, value, normalized, contribution, direction in (
            ('SI', '5', '5', '1', '.25', 'benefit'),
            ('ES', '3', '3', '1', '.25', 'benefit'),
            ('PA', '4', '0', '1', '.25', 'inverse'),
            ('ND', '8', '4', '.5', '.125', 'benefit'))]
    return SimpleNamespace(
        configuration=SimpleNamespace(dataset_policy_id=None, uses_dataset_scoring=False, evidence_policy_id=1,
            evidence_policy=SimpleNamespace(snapshot={'criteria': {
                'SI': {'categories': {'income_0_5000': 'PHP 0 to 5,000'}},
                'ES': {'categories': {'retired': 'Retired'}}}}),
            policy={'criteria': dict.fromkeys(codes, {})}),
        snapshot={'eligible': {'a': {'inputs': inputs}},
                  'manifest': [{'application': 'a', 'reference': 'FICTIONAL-REFERENCE'}]},
        calculations={'a': {'score_0_1': '.875', 'score_0_100': '87.5', 'traces': traces,
                            'comparison': {'higher': 0, 'equal': 1}}})


class ScoreBreakdownPresentationTests(SimpleTestCase):
    def test_four_criterion_example_explains_encoding_direction_and_joint_contributors(self):
        run = saved_example()
        before = deepcopy((run.calculations, run.snapshot))
        row = build_breakdown(run, {'a': 'Fictional Applicant'})[0]
        self.assertEqual(row['score'], '87.50')
        self.assertEqual(row['rank'], 1)
        self.assertEqual([t['points'] for t in row['traces']], ['25.00', '25.00', '25.00', '12.50'])
        self.assertEqual(row['leader_names'], 'SI, ES, PA')
        self.assertEqual(row['leader_share'], '85.71')
        self.assertEqual(row['best_names'], 'SI, ES, PA')
        self.assertEqual(row['traces'][0]['input_label'], 'PHP 0 to 5,000')
        self.assertEqual(row['traces'][1]['input_label'], 'Retired')
        self.assertEqual(row['traces'][2]['formula'], '(4 − 0) ÷ (4 − 0)')
        self.assertEqual(row['traces'][3]['formula'], '(4 − 0) ÷ (8 − 0)')
        self.assertEqual(row['traces'][3]['normalized_percent'], '50.00')
        self.assertEqual([trace['code'] for trace in row['display_traces']], ['HI', 'SI', 'ES', 'PA', 'HM'])
        self.assertEqual([trace.get('points') for trace in row['display_traces']],
                         [None, '25.00', '25.00', '25.00', None])
        self.assertEqual([trace['code'] for trace in row['legacy_traces']], ['ND'])
        self.assertEqual(row['displayed_points'], '75.00')
        self.assertEqual(row['legacy_points'], '12.50')
        self.assertEqual((run.calculations, run.snapshot), before)
        guide = calculation_guide(run, [row])
        self.assertEqual(guide['codes'], 'SI, ES, PA, ND')
        self.assertEqual(guide['count'], 4)
        self.assertFalse(guide['pool_bounds'])
        self.assertFalse(guide['composite'])

    def test_criterion_comparisons_use_the_whole_pool_and_exact_values_even_when_display_matches(self):
        run = saved_example()
        for key in ('b', 'c'):
            run.snapshot['eligible'][key] = deepcopy(run.snapshot['eligible']['a'])
            run.snapshot['manifest'].append({'application': key, 'reference': 'SYNTHETIC-' + key})
            run.calculations[key] = deepcopy(run.calculations['a'])
        tiny = Fraction(1, 10**40)
        run.calculations['b']['traces'][0]['contribution'] = str(Fraction(1, 4) - tiny)
        run.calculations['b'].update(score_exact=str(Fraction(7, 8) - tiny), score_display='87.50',
            comparison={'higher': 2, 'equal': 1})
        for key in ('a', 'c'):
            run.calculations[key]['comparison'] = {'higher': 0, 'equal': 2}
        before = deepcopy(run.calculations)
        rows = {row['application']: row for row in build_breakdown(run, {})}
        first, lower = rows['a']['traces'][0], rows['b']['traces'][0]
        self.assertEqual(first['points'], lower['points'])
        self.assertEqual((first['pool_higher'], first['pool_equal'], first['pool_lower']), (0, 1, 1))
        self.assertEqual((lower['pool_higher'], lower['pool_equal'], lower['pool_lower']), (2, 0, 0))
        self.assertEqual(lower['pool_position'], 'Lowest points in this pool')
        self.assertEqual(rows['a']['traces'][1]['pool_position'], 'Same points for everyone')
        self.assertEqual(rows['b']['rank'], 3)
        self.assertEqual(rows['a']['lower'], 1)
        self.assertEqual(run.calculations, before)

    def test_legacy_income_and_dependents_do_not_become_household_scores(self):
        run = saved_example()
        run.snapshot['eligible']['a']['inputs']['SI'] = {'value': '5000', 'source_type': 'monthly_income'}
        row = build_breakdown(run, {})[0]
        traces = {trace['code']: trace for trace in row['display_traces']}
        self.assertEqual(traces['SI']['name'], 'Socioeconomic Indicator')
        self.assertEqual(traces['SI']['raw'], '5000')
        self.assertEqual(traces['SI']['source_note'], 'Monthly income under this saved configuration.')
        for code in ('HI', 'HM'):
            self.assertFalse(traces[code]['included'])
            for key in ('raw', 'normalized', 'weight', 'points'):
                self.assertNotIn(key, traces[code])
        self.assertEqual(row['legacy_traces'][0]['raw'], '4')
        self.assertEqual(row['score'], '87.50')

    def test_exact_ties_and_near_ties_are_not_resorted_using_rounded_scores(self):
        run = saved_example()
        run.snapshot['eligible']['b'] = deepcopy(run.snapshot['eligible']['a'])
        run.snapshot['manifest'].append({'application': 'b', 'reference': 'FICTIONAL-B'})
        run.calculations['b'] = deepcopy(run.calculations['a'])
        for row in run.calculations.values():
            row['comparison']['equal'] = 2
        rows = build_breakdown(run, {})
        self.assertEqual([(row['rank'], row['tied_others']) for row in rows], [(1, 1), (1, 1)])
        run.calculations['a'].update(score_0_1='.87500000000000000000000000000000000000000000000001',
                                     comparison={'higher': 1, 'equal': 1})
        run.calculations['b'].update(score_0_1='.87500000000000000000000000000000000000000000000002',
                                     comparison={'higher': 0, 'equal': 1})
        with localcontext() as context:
            context.prec = 6
            rows = build_breakdown(run, {})
        self.assertEqual([row['application'] for row in rows], ['b', 'a'])
        self.assertEqual([row['rank'] for row in rows], [1, 2])
        self.assertEqual([row['score'] for row in rows], ['87.50', '87.50'])

    def test_zero_total_has_no_invented_leading_criterion_or_division_by_zero(self):
        run = saved_example()
        run.calculations['a'].update(score_0_1='0', score_0_100='0')
        for trace in run.calculations['a']['traces']:
            trace.update(normalized='0', contribution='0')
        row = build_breakdown(run, {})[0]
        self.assertEqual(row['score'], '0.00')
        self.assertEqual(row['leaders'], [])
        self.assertEqual(row['best_names'], '')
        self.assertEqual(row['leader_share'], '0.00')

    def test_rational_traces_keep_saved_total_instead_of_summing_rounded_points(self):
        run = saved_example()
        codes = ('HI', 'SI', 'ES', 'PA', 'HM')
        run.configuration.dataset_policy_id = 1
        run.configuration.uses_dataset_scoring = True
        run.configuration.policy['criteria'] = dict.fromkeys(codes, {})
        run.snapshot['eligible']['a']['inputs'] = {code: {'value': 1} for code in codes}
        run.calculations['a'].update(score_exact='1/3', score_0_1='0.33333333333333333333333333333333333333333333333333',
            score_0_100='33.333333333333333333333333333333333333333333333333', score_display='33.33',
            traces=[{'criterion': code, 'input': {'exact': '1'}, 'minimum': {'exact': '0'},
                     'maximum': {'exact': '3'}, 'normalized': {'exact': '1/3'},
                     'weight': '.2', 'contribution': {'exact': '1/15'}, 'direction': 'benefit'}
                    for code in codes])
        row = build_breakdown(run, {})[0]
        self.assertEqual(row['score'], '33.33')
        self.assertEqual(row['score_exact'], '1/3')
        self.assertEqual([trace['points'] for trace in row['traces']], ['6.67'] * 5)
        self.assertEqual(row['traces'][0]['contribution'], '1/15')
        self.assertEqual(row['traces'][0]['normalized'], '1/3')
        self.assertEqual(row['leader_share'], '100.00')
        self.assertEqual([trace['code'] for trace in row['display_traces']], ['HI', 'SI', 'ES', 'PA', 'HM'])
        self.assertTrue(all(trace['included'] for trace in row['display_traces']))
        self.assertEqual(row['missing_criterion_names'], '')
        self.assertEqual(row['legacy_traces'], [])
        self.assertEqual(row['displayed_points'], '33.33')


class ScoreBreakdownViewTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational(additional=1)
        self.client.force_login(self.officer)
        self.url = reverse('ewaf:operational_breakdown', args=[self.program.pk])
        self.guide_url = reverse('ewaf:operational_calculation_guide', args=[self.program.pk])

    def test_empty_tab_never_generates_a_calculation(self):
        for url in (self.url, self.guide_url):
            response = self.client.get(url)
            self.assertContains(response, 'No calculation yet')
            self.assertContains(response, 'Go to Generate EWAF')
            self.assertEqual(self.client.post(url, {}).status_code, 405)
        self.assertFalse(OperationalRun.objects.exists())

    def test_read_only_tab_and_applicant_switch_show_retained_inputs_and_no_decisions(self):
        self.lock_policy()
        run = self.calculate()
        retained = deepcopy(run.payload())
        audit_count = LogEntry.objects.count()
        response = self.client.get(self.url, {'run': run.pk, 'applicant': str(self.application.pk)})
        self.assertContains(response, 'Why rank')
        self.assertContains(response, 'Recorded input')
        self.assertContains(response, 'Full-precision calculation details')
        self.assertEqual(len(response.context['selected']['traces']), 4)
        self.assertEqual([trace['code'] for trace in response.context['criteria']], ['HI', 'SI', 'ES', 'PA', 'HM'])
        table = response.content.decode().split('aria-label="Criterion score breakdown"', 1)[1].split('</table>', 1)[0]
        for name in ('Employment Status (ES)', 'Socioeconomic Indicator (SI)', 'Household monthly income (HI)',
                     'Previous Assistance Received (PA)', 'Number of Household members (HM)'):
            self.assertIn(name, table)
        self.assertEqual(table.count('Not included in this calculation.'), 2)
        self.assertNotIn('data-criterion="ND"', table)
        self.assertContains(response, 'Historical criteria included in this saved score')
        self.assertContains(response, 'it does not mean a zero score')
        self.assertEqual(response.context['selected']['application'], str(self.application.pk))
        self.assertTrue(response.context['active'])
        self.assertIn('no-store', response['Cache-Control'])
        guide = self.client.get(self.guide_url, {'run': run.pk})
        self.assertContains(guide, 'How Calculation Works')
        self.assertContains(guide, 'approved historical configuration')
        self.assertContains(guide, 'data-rule-criterion="ND"')
        self.assertNotContains(guide, 'data-rule-criterion="HM"')
        self.assertNotContains(guide, 'verified 4Ps adjustment')
        self.assertIn('no-store', guide['Cache-Control'])
        self.assertEqual(LogEntry.objects.count(), audit_count)
        self.assertFalse(OperationalDecision.objects.exists())
        self.assertEqual(OperationalRun.objects.count(), 1)
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)
        workspace = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertContains(workspace, self.url)
        self.assertContains(workspace, self.guide_url + '?run=' + str(run.pk))

    def test_historical_and_stale_results_keep_saved_values(self):
        self.lock_policy()
        run = self.calculate()
        current = self.calculate()
        url_data = {'run': run.pk, 'applicant': str(self.application.pk)}
        response = self.client.get(self.url, url_data)
        self.assertFalse(response.context['active'])
        self.assertContains(response, 'Saved calculation — renewed review needed.')
        saved = deepcopy(response.context['selected']['traces'])
        models.QuerySet.update(Member.objects.filter(pk=self.member.pk), monthly_income='999999', dependents=77)
        response = self.client.get(self.url, url_data)
        self.assertEqual(response.context['selected']['traces'], saved)
        self.assertNotContains(response, '999999')
        guide = self.client.get(self.guide_url, url_data)
        self.assertFalse(guide.context['active'])
        self.assertContains(guide, 'Saved calculation — renewed review needed.')
        self.assertNotContains(guide, '999999')
        self.assertEqual(self.client.get(self.url).context['run'].pk, current.pk)

    def test_permissions_invalid_identifiers_and_cross_program_requests_fail_closed(self):
        self.lock_policy()
        run = self.calculate()
        for url in (self.url, self.guide_url):
            self.assertEqual(Client().get(url).status_code, 302)
        viewer = get_user_model().objects.create_user('synthetic-no-ewaf-breakdown', is_staff=True)
        grant(viewer, 'accounts.access_dashboard')
        limited = Client()
        limited.force_login(viewer)
        for url in (self.url, self.guide_url):
            self.assertEqual(limited.get(url).status_code, 403)
        other = create_program(ewaf_applicable=True)
        for route in ('ewaf:operational_breakdown', 'ewaf:operational_calculation_guide'):
            self.assertEqual(self.client.get(reverse(route, args=[other.pk]), {'run': run.pk}).status_code, 404)
        for url in (self.url, self.guide_url):
            for data in ({'run': 'invalid'}, {'applicant': 'not-in-this-run'}):
                self.assertEqual(self.client.get(url, data).status_code, 404)

    def test_tampered_calculation_cannot_be_presented_as_a_valid_explanation(self):
        self.lock_policy()
        run = self.calculate()
        corrupt = deepcopy(run.calculations)
        corrupt[str(self.application.pk)]['score_0_100'] = '99.123456'
        models.QuerySet.update(OperationalRun.objects.filter(pk=run.pk), calculations=corrupt)
        before = OperationalDecision.objects.count(), LogEntry.objects.count()
        workspace = reverse('ewaf:operational_workspace', args=[self.program.pk])
        for response in (self.client.get(workspace), self.client.post(workspace, {'action': 'DECISION'})):
            self.assertContains(response, 'Saved calculation needs review')
            self.assertNotContains(response, '99.123456')
            self.assertNotContains(response, 'Record beneficiary decision')
        export = self.client.get(reverse('ewaf:operational_export', args=[self.program.pk, run.pk]))
        self.assertEqual(export.status_code, 409)
        self.assertNotIn(b'99.123456', export.content)
        self.assertEqual(before, (OperationalDecision.objects.count(), LogEntry.objects.count()))
        for url in (self.url, self.guide_url):
            response = self.client.get(url)
            self.assertContains(response, 'This saved calculation could not be verified.', status_code=409)
            self.assertNotContains(response, '99.123456', status_code=409)
