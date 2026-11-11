"""Code-owned rules need no database seed. Test source; no operational fixtures."""
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from .fixed_scoring import VERSION, definition, validate
from .employment_scoring import MAPPING


class FixedScoringDefinitionTests(SimpleTestCase):
    def test_definition_available_without_database_and_uses_confirmed_rules(self):
        rules = definition()
        self.assertEqual(rules['fixed_scoring_version'], VERSION)
        self.assertEqual(rules['pa_months'], 12)
        self.assertEqual(rules['pa_scope'], 'all_programs')
        self.assertEqual(rules['ses_adjustment'], '90_10')
        self.assertEqual(rules['constant_rule'], 'full_contribution_v1')
        self.assertEqual(rules['tie_rule'], 'hold_boundary')
        self.assertEqual(rules['registration_inputs']['employment'], MAPPING)
        self.assertEqual(rules['evidence_rule'], 'current_member_records_v1')
        self.assertEqual(rules['pool_rule'], 'current_eligible_v1')

    def test_callers_cannot_mutate_the_code_definition(self):
        original = definition()
        changed = definition()
        changed['registration_inputs']['employment']['student'] = 'Unemployed'
        self.assertEqual(definition(), original)

    def test_changed_snapshot_is_rejected_before_accessing_weight_records(self):
        changed = definition()
        changed['pa_months'] = 1
        with self.assertRaises(ValidationError):
            validate(SimpleNamespace(policy=changed))
