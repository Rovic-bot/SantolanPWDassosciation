"""Measured verified-pool exercise; not a production throughput guarantee."""
import json
import os
from pathlib import Path
from time import perf_counter
from decimal import Decimal
from django.test import TransactionTestCase
from django.urls import reverse
from .operational_testsupport import OperationalHelpers


class OperationalVolumeTests(OperationalHelpers, TransactionTestCase):
    def test_one_hundred_verified_applicants_complete_scores_traces_and_pagination(self):
        self.setup_operational(additional=99)
        self.lock_policy()
        started = perf_counter()
        run = self.calculate()
        duration = perf_counter() - started
        self.assertEqual(len(run.snapshot['manifest']), 100)
        self.assertEqual(len(run.calculations), 100)
        self.assertEqual(sum(len(row['traces']) for row in run.calculations.values()), 400)
        scores = [Decimal(row['score_0_1']) for row in run.calculations.values()]
        for row in run.calculations.values():
            score = Decimal(row['score_0_1'])
            self.assertEqual(row['comparison']['higher'], sum(other > score for other in scores))
            self.assertEqual(row['comparison']['equal'], sum(other == score for other in scores))
        self.client.force_login(self.officer)
        started = perf_counter()
        url = reverse('ewaf:operational_run', args=[self.program.pk, run.pk])
        response = self.client.get(url, follow=True)
        page_duration = perf_counter() - started
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['result']['rows']), 50)
        second = self.client.get(url + '?page=2', follow=True)
        self.assertEqual(len(second.context['result']['rows']), 50)
        self.assertFalse({r['application'] for r in response.context['result']['rows']} &
                         {r['application'] for r in second.context['result']['rows']})
        self.assertEqual(response.context['inventory'].paginator.count, 100)
        self.assertEqual(second.context['result']['rows'].paginator.count, 100)
        result = {'fictional_verified_applicants': 100, 'scores': 100, 'traces': 400,
            'capture_calculate_and_persist_seconds': duration, 'revalidate_and_render_first_page_seconds': page_duration,
            'engineering_ceiling': 2000, 'ceiling_capacity_benchmarked': False}
        print('Operational volume result:', json.dumps(result), flush=True)
        if os.environ.get('G12_ARTIFACT_DIR'):
            Path(os.environ['G12_ARTIFACT_DIR'], 'operational-volume.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
