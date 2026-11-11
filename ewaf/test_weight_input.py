from copy import deepcopy
from itertools import permutations
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TransactionTestCase
from django.urls import reverse

from .weight_input import project, preview, accept, validate_provenance, percentages, initial_state
from .household_criteria import LEGACY_CRITERIA as CRITERIA
from .four_criterion_development import ahp
from .operational_forms import ConfigurationForm
from .operational_testsupport import OperationalHelpers
from .operational_models import OperationalConfiguration as Configuration
from . import operational_services as service


def proposal(order=CRITERIA):
    return {'order': list(order), 'weights': dict(zip(order, [4000, 3000, 2000, 1000]))}


class WeightCompatibilityTests(SimpleTestCase):
    def test_projection_uses_existing_engine_for_every_priority_order(self):
        for order in permutations(CRITERIA):
            judgments, result, provenance = project(proposal(order))
            self.assertEqual(result, ahp(judgments))
            self.assertEqual(result['reference_consistency'], 'PASSED')
            self.assertEqual(sum(percentages(result['weights']).values()), 10000)
            self.assertNotEqual(percentages(result['weights']), proposal(order)['weights'])
            validate_provenance(provenance, judgments)

    def test_positive_total_hierarchy_and_scale_are_required(self):
        for weights in ([0, 4000, 3000, 3000], [4000, 3000, 2000, 999],
                        [4000, 2000, 3000, 1000], [7000, 2000, 900, 100],
                        [True, 4999, 2500, 2500], [-1, 5001, 2500, 2500]):
            value = {'order': list(CRITERIA), 'weights': dict(zip(CRITERIA, weights))}
            with self.subTest(weights=weights), self.assertRaises(ValidationError):
                project(value)
        for order in (['SI'] * 4, ['SI', [], 'PA', 'ND']):
            with self.assertRaises(ValidationError):
                project({**proposal(), 'order': order})

    def test_display_rounding_preserves_authorized_order_when_weights_tie(self):
        for order in permutations(CRITERIA):
            value = {'order': list(order), 'weights': dict(zip(order, [3500, 3500, 2000, 1000]))}
            _, result, provenance = project(value)
            configuration = SimpleNamespace(validation=result, policy={'weight_input': provenance})
            state = initial_state(configuration)
            self.assertEqual(state['proposal']['order'], list(order))
            self.assertTrue(state['startingFromSaved'])
            weights = state['proposal']['weights']
            self.assertEqual(sum(weights.values()), 10000)
            self.assertGreaterEqual(weights[order[0]], weights[order[1]])
            self.assertEqual(state['proposal'], state['resetProposal'])

    def test_existing_consistency_failure_cannot_produce_an_acceptance_token(self):
        with patch('ewaf.weight_input.ahp', return_value={'reference_consistency': 'NOT_PASSED'}):
            with self.assertRaises(ValidationError):
                preview(proposal(), program='one', expected='version')

    def test_preview_is_bound_to_program_configuration_and_exact_proposal(self):
        data = proposal()
        result = preview(data, program='one', expected='version')
        self.assertEqual(accept(result['token'], data, program='one', expected='version')[0], result['judgments'])
        for program, expected, target in [('two', 'version', data), ('one', 'new', data),
                                          ('one', 'version', proposal(('ND', 'SI', 'ES', 'PA')))]:
            with self.assertRaises(ValidationError):
                accept(result['token'], target, program=program, expected=expected)
        with self.assertRaises(ValidationError):
            accept(result['token'] + 'x', data, program='one', expected='version')
        judgments, _, provenance = project(data)
        judgments['SI:ES'] = '9'
        with self.assertRaises(ValidationError):
            validate_provenance(provenance, judgments)


class WeightConfigurationTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()
        self.original = self.lock_policy()
        self.client.force_login(self.officer)
        self.url = reverse('ewaf:operational_configuration', args=[self.program.pk])

    def form_data(self):
        form = ConfigurationForm(configuration=self.original, program=self.program,
            initial={'expected': service.configuration_token(self.program)})
        data = {}
        for name in form.fields:
            value = form[name].value()
            if value is not None:
                data[name] = json.dumps(value) if isinstance(value, (dict, list)) else value
        data.update(reason='Fictional explicit weight review', attested='on', action='LOCKED')
        return data

    def reviewed_data(self):
        data = self.form_data()
        data['slider_proposal'] = json.dumps(proposal())
        response = self.client.post(self.url, {**data, 'action': 'PREVIEW_WEIGHTS'})
        self.assertEqual(response.status_code, 200)
        data.update(weight_review=response.json()['token'], accept_derived_weights='on')
        return data

    def test_preview_changes_nothing_and_explicit_save_retains_history_and_provenance(self):
        run = self.calculate()
        original_payload, scores = deepcopy(self.original.payload()), deepcopy(run.calculations)
        data = self.reviewed_data()
        self.assertEqual(Configuration.objects.count(), 1)
        # Forged hidden pairwise values never override the reviewed projection.
        data['pair_SI_ES'] = '9'
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        newest = Configuration.objects.first()
        self.assertEqual(newest.judgments, project(proposal())[0])
        self.assertEqual(newest.validation, ahp(newest.judgments))
        self.assertEqual(newest.policy['weight_input']['proposal'], proposal())
        self.original.refresh_from_db()
        self.assertEqual(self.original.payload(), original_payload)
        run.refresh_from_db()
        self.assertEqual(run.calculations, scores)
        run.clean()
        newest.clean()

    def test_unreviewed_tampered_stale_and_failed_audit_do_not_save(self):
        data = self.reviewed_data()
        for change in ({'accept_derived_weights': ''}, {'weight_review': 'forged'},
                       {'slider_proposal': json.dumps(proposal(('ND', 'SI', 'ES', 'PA')))}):
            response = self.client.post(self.url, {**data, **change})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['configuration_form'].errors)
            self.assertEqual(Configuration.objects.count(), 1)
        with patch('programs.models.ProgramLog.objects.create', side_effect=ValidationError('audit failed')):
            self.client.post(self.url, data)
        self.assertEqual(Configuration.objects.count(), 1)
        self.lock_policy()
        response = self.client.post(self.url, data)
        self.assertContains(response, 'Configuration changed')
        self.assertEqual(Configuration.objects.count(), 2)

    def test_view_only_permissions_and_invalid_preview(self):
        from membership.tests import grant
        viewer = get_user_model().objects.create_user('weight_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *service.VIEW)
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url, follow=True), 'id="weight-editor"')
        self.assertEqual(self.client.post(self.url, {
            'action': 'PREVIEW_WEIGHTS', 'slider_proposal': json.dumps(proposal())}).status_code, 403)
        self.client.force_login(self.officer)
        response = self.client.post(self.url, {'action': 'PREVIEW_WEIGHTS',
            'expected': service.configuration_token(self.program), 'slider_proposal': 'not json'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Configuration.objects.count(), 1)
