"""Actual private Admin requests and fresh protected-use human previews."""
import json
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase, Client
from django.urls import reverse
from django.test.utils import CaptureQueriesContext
from django.db import connection
from .four_testsupport import FourHelpers
from .test_source_writers import SourceHelpers
from . import test_generation_processing as previous_tests
from . import four_decisions, generation_processing as processing
from .durable_models import DurableRun


class FourInterfaceTests(SourceHelpers, FourHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.client.force_login(self.officer)
        self.register()
        self.install_four()
        self.request = self.accept()
        self.url = reverse('ewaf:four_workspace', args=[self.program.pk])
        self.history_url = reverse('ewaf:development_program', args=[self.program.pk])

    context_new = previous_tests.ProcessingTests.context_new
    accept = previous_tests.ProcessingTests.accept
    process_new = previous_tests.ProcessingTests.process_new

    def decision_data(self):
        self.run = self.process_new(self.request)
        return {'user': self.officer, 'expected': self.token(), 'run_id': self.run.pk,
            'application_id': self.application.pk, 'decision': 'SELECT_FOR_DEMONSTRATION',
            'reason': 'Fictional human review of documented functional need and available evidence.'}

    def test_reasoned_decision_is_transient_and_has_no_assistance_effect(self):
        from assistance.models import AssistanceCase, AssistanceRelease
        before = list(AssistanceCase.objects.values())
        data = self.decision_data()
        result = four_decisions.demonstrate(self.program.pk, **data)
        self.assertTrue(result['eligible'] and result['comparable'] and result['selected_in_demonstration'])
        self.assertFalse(result['actually_assisted'] or result['operational_ready'])
        self.assertEqual(result['retention'], 'NOT_PERSISTED_SCHEMA_PENDING')
        self.assertEqual(before, list(AssistanceCase.objects.values()))
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_reason_identity_permission_and_stale_decision_checks(self):
        data = self.decision_data()
        for field, value in [('reason', ''), ('application_id', 987654), ('run_id', self.run.pk + 1), ('decision', 'approve-release')]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                four_decisions.demonstrate(self.program.pk, **{**data, field: value})
        self.advance_authority()
        with self.assertRaises(ValidationError):
            four_decisions.demonstrate(self.program.pk, **data)
        with patch('ewaf.four_decisions.require_workspace_permissions', side_effect=PermissionDenied):
            with self.assertRaises(PermissionDenied):
                four_decisions.demonstrate(self.program.pk, **{**data, 'expected': self.token()})

    def test_cached_superuser_cannot_bypass_current_decision_permission(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        data = self.decision_data()
        self.assertTrue(self.officer.has_perm('assistance.decide_assistance'))
        # Deliberately bypass a supported writer in this fictional fixture to
        # isolate the fresh database authorization check from generation checks.
        self.officer.user_permissions.set(Permission.objects.exclude(codename='decide_assistance'))
        get_user_model().objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            four_decisions.demonstrate(self.program.pk, **data)

    def test_actual_private_pages_and_human_post(self):
        data = self.decision_data()
        response = self.client.get(self.url)
        self.assertContains(response, 'BLOCKED_POLICY')
        self.assertContains(response, 'Complete application inventory')
        self.assertContains(response, 'Guided fictional pairwise comparisons')
        self.assertIn('no-store', response['Cache-Control'])
        data.pop('user')
        data['expected'] = json.dumps(data['expected'])
        response = self.client.post(self.url, {'action': 'choice', **data})
        self.assertContains(response, 'Selected in demonstration: yes. Actually assisted: no. Saved: no.')
        history = self.client.get(self.history_url)
        self.assertContains(history, 'Versioned four-criterion development engine')
        self.assertContains(history, 'g18-four-complete-pool-1')

    def test_configuration_post_retains_revision_and_invalidates_current(self):
        self.process_new(self.request)
        page = self.client.get(self.url)
        initial = page.context['configuration_form'].initial
        data = {**initial, 'expected': json.dumps(initial['expected']), 'reason': 'Fictional revised AHP review',
                'action': 'configuration', 'pair_SI_ES': '3'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.context['configuration_form'].errors if response.context else '')
        with self.assertRaises(ValidationError):
            processing.inspect_current(self.program.pk, user=self.officer)
        self.assertEqual(DurableRun.objects.count(), 1)
        self.assertEqual(self.client.post(self.url, data).status_code, 200)
        self.assertContains(self.client.post(self.url, data), 'STALE_GENERATION_TOKEN')

    def test_existing_readiness_and_configuration_views_do_not_reinterpret_four(self):
        from .configuration_readiness import configuration_diagnostics
        from .scoring_inputs import evaluate_application
        result = configuration_diagnostics(self.program.pk, user=self.officer)
        self.assertFalse(result['operational_ready'])
        result = evaluate_application(self.application, user=self.officer)
        self.assertFalse(result['operational_ready'])
        self.assertIn('FOUR_FICTIONAL_POLICY_ONLY', [r['code'] for r in result['reasons']])

    def test_anonymous_unprivileged_csrf_and_unregistered_privacy(self):
        from django.contrib.auth import get_user_model
        self.assertEqual(Client().get(self.url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.officer)
        self.assertEqual(csrf.post(self.url, {'action': 'choice'}).status_code, 403)
        with patch('accounts.authority_services.enlisted', return_value=False), CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertFalse(any('ewaf_programsourcestate' in row['sql'] or 'ewaf_authoritygeneration' in row['sql'] for row in queries))
        user = get_user_model().objects.create_user('fictional-four-no-permission', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
