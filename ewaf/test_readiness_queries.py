"""Keep the verified readiness path bounded without bypassing validation."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from .operational_testsupport import OperationalHelpers
from .readiness import assess_readiness


class ReadinessQueryTests(OperationalHelpers, TestCase):
    def test_verified_readiness_keeps_evidence_checks_within_query_budget(self):
        self.setup_operational()
        self.lock_policy()
        with CaptureQueriesContext(connection) as queries:
            result = assess_readiness(self.application.pk, user=self.officer)
        self.assertTrue(result['eligibility_readiness'])
        self.assertTrue(result['criterion_completeness'])
        # The measured baseline is 61 queries. Keep at least a 25% reduction
        # while preserving all evidence/authority checks, rather than caching
        # validation results across calls. The optimized fixture currently uses 42.
        self.assertLessEqual(len(queries), 45)
