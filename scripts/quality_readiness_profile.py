"""Measure one verified applicant's real readiness query count."""
import json
import os
from pathlib import Path
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.readiness import assess_readiness


class ReadinessProfile(OperationalHelpers, TestCase):
    def test_current_readiness_query_budget(self):
        self.setup_operational()
        self.lock_policy()
        with CaptureQueriesContext(connection) as queries:
            result = assess_readiness(self.application.pk, user=self.officer)
        output = {'queries':len(queries),'result':result}
        Path(os.environ['G12_ARTIFACT_DIR'],'readiness-query-profile.json').write_text(json.dumps(output,indent=2,default=str),encoding='utf-8')
        print('Readiness queries:',len(queries),flush=True)
