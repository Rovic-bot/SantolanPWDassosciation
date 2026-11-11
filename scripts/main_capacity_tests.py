"""Explicit 2,000-applicant boundary exercise in disposable MySQL only."""
import json
import os
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.utils import timezone
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_models import OperationalRun
from ewaf import operational_services as service


class MainTestingCapacityTests(OperationalHelpers, TransactionTestCase):
    def test_real_2000_pool_and_2001_rejection(self):
        started = perf_counter()
        self.setup_operational()
        # The helper shallow-copies its test fixture; avoid copying a self-cycle.
        self.helpers = []
        with patch('django.utils.timezone.now', return_value=self.fixture_time):
            for index in range(1999):
                self.add_four_ready_applicant('BOUNDARY-' + str(index), income=str(index % 10 * 10), dependents=index % 8)
                if (index + 1) % 250 == 0:
                    print('Verified boundary fixtures:', index + 2, flush=True)
        self.lock_policy()
        setup_seconds = perf_counter() - started
        started = perf_counter()
        from django.db import connection
        def measure(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO `ewaf_operationalrun`'):
                size = sum(len(str(value).encode()) for value in params)
                print('Operational run INSERT parameter bytes:', size, flush=True)
            return execute(sql, params, many, context)
        with connection.execute_wrapper(measure):
            run = self.calculate()
        calculate_seconds = perf_counter() - started
        self.assertEqual(len(run.snapshot['manifest']), 2000)
        self.assertEqual(len(run.calculations), 2000)
        self.assertEqual(sum(len(row['traces']) for row in run.calculations.values()), 8000)
        retained = run.digest
        with patch('django.utils.timezone.now', return_value=self.fixture_time):
            self.add_four_ready_applicant('BOUNDARY-OVERFLOW', income='10', dependents=1)
        with self.assertRaisesMessage(ValidationError, 'WHOLE_POOL_UNSUPPORTED'):
            service.context(self.program.pk, user=self.officer)
        self.assertEqual(OperationalRun.objects.count(), 1)
        run.refresh_from_db()
        self.assertEqual(run.digest, retained)
        evidence = {'accepted': 2000, 'rejected': 2001, 'scores': 2000, 'traces': 8000,
                    'setup_seconds': setup_seconds, 'calculate_seconds': calculate_seconds,
                    'production_capacity_claim': False}
        print('BOUNDARY VERIFIED:', json.dumps(evidence), flush=True)
        Path(os.environ['G12_ARTIFACT_DIR'], 'main-capacity.json').write_text(json.dumps(evidence), encoding='utf-8')
