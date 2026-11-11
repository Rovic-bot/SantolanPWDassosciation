from copy import deepcopy
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from .calculation import ahp, calculate
from .models import Configuration
from .services import save_configuration
from .testsupport import test_configuration


class CalculationTests(TestCase):
    def setUp(self):
        self.config = test_configuration()
        self.raw = {'SI': '0', 'ES': 'Test employment description', 'PA': '0', 'ND': '0', 'PR': 'Test relevance'}

    def test_equal_pairwise_comparisons_have_known_weights_consistency_and_score(self):
        weights, consistency = ahp([[1] * 5 for _ in range(5)])
        self.assertEqual(set(weights.values()), {Decimal('0.2')})
        self.assertEqual(Decimal(consistency['CR']), 0)
        result = calculate(self.config, self.raw)
        # Independently: (1 + .5 + 1 + 0 + .5) / 5 = .6.
        self.assertEqual(result['score'], Decimal('0.6'))
        self.assertEqual(result['classification'], 'Synthetic upper band')

    def test_more_income_and_previous_releases_reduce_need(self):
        baseline = calculate(self.config, self.raw)['score']
        self.assertLess(calculate(self.config, {**self.raw, 'SI': '10000'})['score'], baseline)
        self.assertLess(calculate(self.config, {**self.raw, 'PA': '1'})['score'], baseline)
        self.assertGreater(calculate(self.config, {**self.raw, 'ND': '1'})['score'], baseline)

    def test_invalid_and_nonfinite_inputs_are_not_clipped_or_imputed(self):
        for changes in ({'SI': '-1'}, {'SI': '100001'}, {'SI': 'NaN'}, {'ND': 'Infinity'}, {'ES': 'Undefined category'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                calculate(self.config, {**self.raw, **changes})

    def test_equal_bounds_and_inconsistent_judgments_block_scoring(self):
        self.config.bounds['SI']['max'] = 0
        with self.assertRaises(ValidationError):
            calculate(self.config, self.raw)
        matrix = [[1] * 5 for _ in range(5)]
        matrix[0][1], matrix[1][0] = 100, '0.01'
        with self.assertRaisesMessage(ValidationError, 'CR must be strictly below'):
            ahp(matrix)

    def test_configuration_versions_are_immutable_and_unseeded(self):
        self.config.name = 'Changed'
        with self.assertRaises(ValidationError):
            self.config.save()
        self.assertEqual(Configuration.objects.count(), 1)

    def test_configuration_service_requires_permission_and_audits_new_version(self):
        restricted = get_user_model().objects.create_user('restricted-config', is_staff=True)
        with self.assertRaises(PermissionDenied):
            save_configuration(user=restricted, data={})
        admin = get_user_model().objects.create_superuser('config-admin')
        with self.assertRaisesMessage(ValidationError, 'stage-eight'):
            save_configuration(user=admin, data={})
        self.assertEqual(Configuration.objects.count(), 1)
