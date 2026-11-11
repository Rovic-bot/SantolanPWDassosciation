"""Presentation regressions against existing private EWAF readiness and ranking."""
from copy import deepcopy
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tests.test_workspace_navigation import grant
from programs.models import ProgramApplication
from programs.tests import create_program
from .operational_models import OperationalRun
from .operational_testsupport import OperationalHelpers
from . import operational_services as service


class SelectionWorkspaceTests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational(additional=3)
        self.lock_policy()
        self.client.force_login(self.officer)
        self.url = reverse('ewaf_selection')
        self.panel_url = reverse('ewaf:selection_panel', args=[self.program.pk])

    def test_ready_requires_actual_pool_checks_and_filtering_does_not_generate(self):
        ready = self.client.get(self.panel_url)
        self.assertEqual(ready.status_code, 200)
        row = ready.context['program']
        row.selection = ready.context['selection']
        self.assertEqual(row.selection['state'], 'ready')
        self.assertEqual(row.selection['percent'], 100)
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='NEEDS_INFORMATION')
        pending = self.client.get(self.panel_url)
        self.assertEqual(pending.context['selection']['state'], 'pending')
        self.assertFalse(pending.context['selection']['can_generate'])
        self.assertLess(pending.context['selection']['percent'], 100)
        self.assertEqual(self.client.get(self.url, {'configuration': 'ready'}).context['page_obj'].paginator.count, 0)
        self.assertEqual(OperationalRun.objects.count(), 0)

    def test_selection_scope_empty_state_and_actual_weights(self):
        other = create_program(name='Synthetic unconfigured program', ewaf_applicable=True)
        create_program(name='Not in EWAF')
        page = self.client.get(self.url, {'q': other.name, 'selected': self.program.pk})
        self.assertEqual(page.context['selected_id'], str(other.pk))
        self.assertNotIn('can_generate', page.context['page_obj'][0].selection)
        self.assertEqual(page.context['page_obj'].paginator.count, 1)
        self.assertContains(self.client.get(self.url, {'q': 'does-not-exist'}), 'No EWAF programs found')
        ready = self.client.get(self.panel_url)
        self.assertContains(ready, 'Approved criteria weights')
        self.assertNotContains(ready, 'Disability impact')
        self.assertContains(self.client.get(self.url), 'role="search"')
        self.assertEqual(OperationalRun.objects.count(), 0)

    def test_saved_preview_preserves_exact_ranks_and_marks_stale_runs(self):
        run = self.calculate()
        original = deepcopy(run.calculations)
        page = self.client.get(self.panel_url)
        preview = page.context['selection']['preview']
        self.assertTrue(preview['active'])
        expected = service.ordered(run)[:3]
        self.assertEqual([row['application'] for row in preview['rows']], [row['application'] for row in expected])
        self.assertEqual([row['rank'] for row in preview['rows']], [row['comparison']['higher'] + 1 for row in expected])
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='NEEDS_INFORMATION')
        stale = self.client.get(self.panel_url)
        self.assertContains(stale, 'Refresh required before selection')
        run.refresh_from_db()
        self.assertEqual(run.calculations, original)
        self.assertEqual(OperationalRun.objects.count(), 1)

    def test_private_route_and_calculation_permission_are_preserved(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        user = get_user_model().objects.create_user('synthetic_ewaf_reader', is_staff=True)
        grant(user, 'accounts.access_dashboard', *service.VIEW)
        self.client.force_login(user)
        page = self.client.get(self.panel_url)
        self.assertEqual(page.status_code, 200)
        self.assertFalse(page.context['selection']['can_generate'])
        self.assertContains(page, 'calculation permission')
        self.assertEqual(self.client.post(reverse('ewaf:operational_workspace', args=[self.program.pk]),
            {'action': 'GENERATE', 'expected': json.dumps(page.context['selection']['expected']),
             'request_key': '00000000-0000-0000-0000-000000000001'}).status_code, 403)

    def test_unvalidated_saved_result_never_displays_scores(self):
        self.calculate()
        from django.core.exceptions import ValidationError
        with patch.object(OperationalRun, 'clean', side_effect=ValidationError('Invalid saved calculation')):
            page = self.client.get(self.panel_url)
        self.assertContains(page, 'Retained ranking needs integrity review')
        self.assertNotContains(page, 'Leading applicants')

    def test_landing_does_not_capture_or_validate_every_applicant_pool(self):
        self.calculate()
        with patch.object(service, 'context', side_effect=AssertionError('Eager pool capture')), \
             patch('ewaf.selection_workspace.ranking_preview', side_effect=AssertionError('Eager run validation')):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.panel_url)
        self.assertNotContains(response, 'data-generate-ranking')
        self.client.logout()
        self.assertEqual(self.client.get(self.panel_url).status_code, 302)
