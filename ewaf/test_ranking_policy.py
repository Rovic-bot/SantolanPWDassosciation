from django.test import SimpleTestCase
from .ranking_policy import DECISIONS, policy_completeness
from .ranking_diagnostics import BARRIERS


class RankingPolicyTests(SimpleTestCase):
    def test_all_decisions_start_pending(self):
        result = policy_completeness()
        self.assertTrue(result['valid_schema'])
        self.assertEqual([r['decision'] for r in result['findings']], list(DECISIONS))
        self.assertTrue(all(r['status'] == 'PENDING_ASSOCIATION_DECISION' for r in result['findings']))

    def test_references_never_approve_policy_or_expose_private_text(self):
        proposal = {'schema_version': 1, 'references': {key: 'Synthetic draft reference' for key in DECISIONS}}
        result = policy_completeness(proposal)
        self.assertTrue(all(r['documentary_reference_present'] for r in result['findings']))
        self.assertFalse(result['effective_authorization'])
        self.assertFalse(result['operational_ready'])
        self.assertTrue(set(BARRIERS) <= set(result['reasons']))
        self.assertNotIn('Synthetic draft reference', str(result))

    def test_unknown_missing_oversized_or_approval_fields_rejected(self):
        for proposal in ({}, {'schema_version': True, 'references': {}},
                         {'schema_version': 1, 'references': {key: 'x' * 201 for key in DECISIONS}},
                         {'schema_version': 1, 'references': {}, 'approved': True}, []):
            self.assertFalse(policy_completeness(proposal)['valid_schema'])

    def test_canonical_reference_order(self):
        a = {'schema_version': 1, 'references': dict.fromkeys(DECISIONS)}
        b = {'references': dict(reversed(list(a['references'].items()))), 'schema_version': 1}
        self.assertEqual(policy_completeness(a), policy_completeness(b))
