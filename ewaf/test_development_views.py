"""Actual private Admin development requests; no operational endpoints."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, Client
from django.urls import reverse
from django.test.utils import CaptureQueriesContext
from django.db import connection

from .durable_testsupport import DurableHelpers
from .test_source_writers import SourceHelpers
from .four_criterion_reference import REFERENCE_PAIRS
from .generation_models import DevelopmentPromotion


class DevelopmentViewTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.request_run()  # Harness-created fictional evaluation contract.
        self.client.force_login(self.officer)
        self.register()
        self.lab = reverse('ewaf:development_lab')
        self.program_url = reverse('ewaf:development_program', args=[self.program.pk])

    def data(self, **changes):
        return {**{'pair_' + a + '_' + b: value for a, b, value in REFERENCE_PAIRS}, **changes}

    def test_private_page_has_policy_blocks_labels_and_no_live_actions(self):
        response = self.client.get(self.lab)
        self.assertContains(response, 'Four-criterion policy readiness: blocked')
        self.assertContains(response, 'Operational EWAF remains disabled')
        self.assertContains(response, '<legend', html=False)
        self.assertContains(response, '<caption', html=False)
        for a, b, _ in REFERENCE_PAIRS:
            self.assertContains(response, f'for="id_pair_{a}_{b}"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'PR is a program-specific eligibility requirement')

    def test_fictional_selection_and_pending_inventory_form(self):
        response = self.client.post(self.lab, self.data(selected='DEMO-B'))
        self.assertContains(response, 'Human choice in this example: yes')
        self.assertContains(response, 'Actually assisted: no')
        response = self.client.post(self.lab, self.data(pending='on'))
        self.assertContains(response, 'ELIGIBILITY_REVIEW_PENDING')
        self.assertNotContains(response, 'Illustrative score:')
        self.assertFalse(DevelopmentPromotion.objects.exists())

    def test_invalid_comparisons_remain_in_accessible_form(self):
        response = self.client.post(self.lab, self.data(pair_SI_ES='NaN'))
        self.assertContains(response, 'Select a valid choice')
        self.assertNotContains(response, 'Illustrative score:')

    def test_anonymous_and_unprivileged_access_denied(self):
        self.assertEqual(Client().get(self.lab).status_code, 302)
        user = get_user_model().objects.create_user('fictional_unprivileged_dev', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.lab).status_code, 403)

    def test_default_mode_has_no_generation_table_queries_and_no_interface(self):
        with patch('accounts.authority_services.enlisted', return_value=False), CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(self.lab).status_code, 404)
            self.assertEqual(self.client.post(self.lab, self.data()).status_code, 404)
            self.assertEqual(self.client.get(self.program_url).status_code, 404)
        self.assertFalse(any('ewaf_programsourcestate' in q['sql'] or 'ewaf_authoritygeneration' in q['sql'] for q in queries))

    def test_generation_calculation_and_versioned_history_actual_posts(self):
        first_page = self.client.get(self.program_url)
        self.assertEqual(first_page.status_code, 200)
        initial = first_page.context['form'].initial
        import json
        data = {**initial, 'expected': json.dumps(initial['expected']), 'previous_id': '',
                'reason': 'Fictional first private version'}
        self.assertRedirects(self.client.post(self.program_url, data), self.program_url)
        page = self.client.get(self.program_url)
        self.assertContains(page, 'current at this inspection')
        initial = page.context['form'].initial
        data = {**initial, 'expected': json.dumps(initial['expected']), 'reason': 'Fictional recalculated version'}
        self.assertRedirects(self.client.post(self.program_url, data), self.program_url)
        page = self.client.get(self.program_url)
        self.assertContains(page, 'historical only')
        self.assertEqual(DevelopmentPromotion.objects.count(), 2)
        initial = page.context['form'].initial
        data = {**initial, 'expected': json.dumps(initial['expected']), 'reason': 'Fictional failed replacement'}
        with patch('ewaf.generation_processing._persist_graph', side_effect=ValidationError('Fictional processing failure')):
            response = self.client.post(self.program_url, data)
        self.assertContains(response, 'Fictional processing failure')
        self.assertContains(response, 'No currently usable development result is shown')
        self.assertNotContains(response, 'current at this inspection')
        from .generation_models import ProgramSourceState
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        self.assertEqual(DevelopmentPromotion.objects.count(), 2)

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        self.assertEqual(client.post(self.lab, self.data()).status_code, 403)
        self.assertEqual(client.post(self.program_url, {'reason': 'Fictional request'}).status_code, 403)

    def test_get_does_not_run_calculation_or_promote(self):
        self.client.get(self.lab)
        self.client.get(self.program_url)
        self.assertFalse(DevelopmentPromotion.objects.exists())
