"""Exact presentation and representative complete-pool acceptance on fictional data."""
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

from django.test import SimpleTestCase, TransactionTestCase
from django.urls import reverse

from .four_policy import CRITERIA, CONTEXT
from .four_review import ordered_results
from .four_testsupport import FourHelpers
from .test_source_writers import SourceHelpers
from . import test_generation_processing as previous_tests
from . import durable_services as durable, four_decisions


class ExactComparisonTests(SimpleTestCase):
    def test_order_uses_all_retained_digits_and_preserves_exact_ties(self):
        def row(value):
            return SimpleNamespace(calculation={'score_0_100': value},
                traces=SimpleNamespace(all=lambda: [SimpleNamespace(criterion=c) for c in reversed(CRITERIA)]))
        lower = row('50.000000000000000000000000000000000000000000000001')
        higher = row('50.000000000000000000000000000000000000000000000002')
        equal = row(higher.calculation['score_0_100'])
        with localcontext() as context:
            context.prec = 6
            result = ordered_results([lower, higher, equal])
        self.assertEqual(result, [higher, equal, lower])
        self.assertEqual([t.criterion for t in result[0].review_traces], list(CRITERIA))
        self.assertEqual(lower.calculation['score_0_100'], '50.000000000000000000000000000000000000000000000001')


class RepresentativePoolTests(SourceHelpers, FourHelpers, TransactionTestCase):
    context_new = previous_tests.ProcessingTests.context_new
    accept = previous_tests.ProcessingTests.accept
    process_new = previous_tests.ProcessingTests.process_new
    current = previous_tests.ProcessingTests.current

    def test_24_verified_applicants_exact_order_ties_replay_and_private_review(self):
        self.setup_durable()
        inputs = {str(self.application.pk): ('0', 0)}
        for index in range(1, 24):
            # Last two records intentionally tie; all other inputs differ.
            value = min(index, 22)
            helper = self.add_four_ready_applicant(f'FICTIONAL-POOL-{index:03d}',
                income=str(value * 4), dependents=value % 11)
            inputs[str(helper.application.pk)] = (str(value * 4), value % 11)
        self.client.force_login(self.officer)
        self.register()
        self.install_four()
        started = monotonic()
        first = self.process_new(self.accept())
        calculation_seconds = monotonic() - started
        rows = ordered_results(first.results.prefetch_related('traces').order_by('application_id'))
        self.assertEqual(len(first.snapshot['manifest']), 24)
        self.assertEqual(len(rows), 24)
        self.assertEqual(sum(len(row.review_traces) for row in rows), 96)
        weights = self.validation.result['weights']
        expected = {}
        with localcontext(CONTEXT):
            for key, (income, dependents) in inputs.items():
                # Independent arithmetic from explicit verified fixture values.
                expected[key] = (Decimal(income) / 100 * Decimal(weights['SI']) + Decimal(weights['ES']) +
                    Decimal(dependents) / 10 * Decimal(weights['ND'])) * 100
        scores = [Decimal(row.calculation['score_0_100']) for row in rows]
        self.assertEqual(scores, sorted(expected.values(), reverse=True))
        for row in rows:
            score = expected[str(row.application_id)]
            self.assertEqual(Decimal(row.calculation['score_0_100']), score)
            self.assertEqual(row.comparison, {'higher': sum(v > score for v in expected.values()),
                'equal': sum(v == score for v in expected.values()), 'business_rank': None})
            self.assertFalse(row.calculation['operational_ready'])
        self.assertTrue(any(row.comparison['equal'] == 2 for row in rows))
        first_digest = first.digest
        preview = four_decisions.demonstrate(self.program.pk, user=self.officer, expected=self.token(),
            run_id=first.pk, application_id=rows[-1].application_id, decision='DEFER_FOR_REVIEW',
            reason='Fictional separate human review; numerical ordering alone does not decide.')
        self.assertFalse(preview['selected_in_demonstration'])
        second = self.process_new(self.accept('representative-pool-replacement', previous_id=first.pk))
        durable._assert_history(first)
        self.assertEqual(first.digest, first_digest)
        self.assertEqual(second.previous_id, first.pk)
        response = self.client.get(reverse('ewaf:development_program', args=[self.program.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'row order within a tie gives no priority')
        presented = response.context['history'][0]['results']
        self.assertEqual([r.calculation['score_0_100'] for r in presented], [r.calculation['score_0_100'] for r in rows])
        self.assertIn('no-store', response['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('ewaf:development_program', args=[self.program.pk])).status_code, 302)
        output = {'purpose': 'FICTIONAL_DISPOSABLE_POOL_ACCEPTANCE', 'retained': 24, 'eligible': 24,
            'trace_count': 96, 'initial_capture_and_process_seconds': calculation_seconds,
            'production_benchmark': False, 'operational_ready': False,
            'old_digest_preserved': first_digest, 'replacement_run': second.pk,
            'comparison': [{'application': str(row.application_id), 'score': row.calculation['score_0_100'],
                **row.comparison} for row in rows]}
        if os.environ.get('G12_ARTIFACT_DIR'):
            Path(os.environ['G12_ARTIFACT_DIR'], 'readiness-pool.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
