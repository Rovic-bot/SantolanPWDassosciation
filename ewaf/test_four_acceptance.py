"""End-to-end acceptance export contains only fictional disposable records."""
import json
import os
from pathlib import Path
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.utils import timezone
from .four_testsupport import FourHelpers
from .test_source_writers import SourceHelpers
from . import test_generation_processing as previous_tests
from . import four_decisions, durable_services as durable


class FourAcceptanceTests(SourceHelpers, FourHelpers, TransactionTestCase):
    context_new = previous_tests.ProcessingTests.context_new
    accept = previous_tests.ProcessingTests.accept
    process_new = previous_tests.ProcessingTests.process_new
    current = previous_tests.ProcessingTests.current

    def test_export_complete_pool_four_trace_history_and_human_decision(self):
        from programs.testsupport import application_fixture
        from members.tests import create_member
        self.setup_durable()
        second = self.add_four_ready_applicant()
        self.register()
        self.install_four()
        # A late unresolved application remains in the full retained inventory,
        # excluded only by the explicit fictional cutoff; never silently dropped.
        pending = application_fixture(self.program, create_member('FICTIONAL-FOUR-LATE'))
        first = self.process_new(self.accept())
        self.assertEqual(len(first.snapshot['manifest']), 3)
        self.assertEqual(first.results.count(), 2)
        self.assertEqual(sum(row.traces.count() for row in first.results.all()), 8)
        preview = four_decisions.demonstrate(self.program.pk, user=self.officer, expected=self.token(),
            run_id=first.pk, application_id=second.application.pk, decision='SELECT_FOR_DEMONSTRATION',
            reason='Fictional documented need reviewed by a human; numerical equality does not select automatically.')
        replacement = self.process_new(self.accept('four-acceptance-recalculation', previous_id=first.pk))
        durable._assert_history(first)
        durable._assert_history(replacement)
        self.assertEqual(self.current()['run_id'], replacement.pk)
        complete_contract = {**self.contract, 'cutoff': timezone.now().isoformat()}
        self.contract = complete_contract
        with self.assertRaisesMessage(ValidationError, 'ELIGIBILITY_UNRESOLVED'):
            self.accept('four-pending-pool', previous_id=replacement.pk)
        evidence = {'purpose': 'FICTIONAL_DISPOSABLE_ACCEPTANCE_EVIDENCE',
            'policy_state': 'BLOCKED_POLICY', 'operational_ready': False,
            'pool': first.snapshot['manifest'], 'eligible': list(first.snapshot['eligible']),
            'late_pending': str(pending.pk), 'first': {'id': first.pk, 'digest': first.digest},
            'replacement': {'id': replacement.pk, 'digest': replacement.digest, 'previous': replacement.previous_id},
            'configuration': self.scoring_policy.configuration.payload(), 'validation': self.scoring_policy.validation.result,
            'explicit_test_policy': self.scoring_policy.proposal,
            'calculations': [row.calculation for row in first.results.all()], 'human_preview': preview,
            'pending_pool_block': 'ELIGIBILITY_UNRESOLVED', 'application_ceiling': 128}
        if os.environ.get('G12_ARTIFACT_DIR'):
            Path(os.environ['G12_ARTIFACT_DIR'], 'four-acceptance.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
