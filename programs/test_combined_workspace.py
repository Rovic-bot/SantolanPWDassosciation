from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from assistance.tests import review_data
from assistance.models import AssistanceCase
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.models import CriterionAssessment
from ewaf.evidence import digest, source_context
from ewaf.operational_forms import WeightConfigurationForm
from membership.tests import grant
from programs.tests import create_program
from programs.review_services import complete_eligibility_review


class CombinedWorkspaceTests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational()
        self.client.force_login(self.officer)
        self.url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])

    def test_cards_combine_query_sort_category_status_and_inventory(self):
        create_program(name='Zebra fictional empty', assistance_type='Food & Nutrition')
        create_program(name='Alpha fictional empty', assistance_type='Food & Nutrition')
        url = reverse('core:application_programs')
        response = self.client.get(url, {'q': 'fictional empty', 'assistance_type': 'Food & Nutrition',
            'status': 'published', 'sort': 'az'})
        self.assertEqual([p.name for p in response.context['page_obj']], ['Alpha fictional empty', 'Zebra fictional empty'])
        response = self.client.get(url, {'q': 'fictional empty', 'sort': 'za', 'with_applications': '1'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        response = self.client.get(url, {'with_applications': '1'})
        self.assertEqual([p.pk for p in response.context['page_obj']], [self.program.pk])
        self.assertEqual(response.context['page_obj'][0].applicant_count, 1)
        self.assertContains(response, 'Registration')

    def test_legacy_routes_land_inside_combined_pages(self):
        response = self.client.get(reverse('assistance:review', args=[self.application.pk]))
        self.assertRedirects(response, self.url + '#eligibility')
        response = self.client.get(reverse('ewaf:operational_configuration', args=[self.program.pk]))
        self.assertRedirects(response, reverse('ewaf:operational_workspace', args=[self.program.pk]) + '#configuration')
        self.assertEqual(self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]), {'run': 'bad'}).status_code, 404)

    def test_inline_review_preserves_pr_history_and_updates_list(self):
        self.lock_policy()
        before = CriterionAssessment.objects.filter(application=self.application, criterion='PR').count()
        data = review_data(self.application)
        data.update({f'check_{item["id"]}': 'pass' for item in self.application.requirements_snapshot})
        response = self.client.post(self.url, {**data, 'action': 'eligibility'})
        self.assertEqual(response.status_code, 302, response.context['eligibility_form'].errors if response.status_code == 200 else '')
        self.assertEqual(CriterionAssessment.objects.filter(application=self.application, criterion='PR').count(), before + 1)
        current = CriterionAssessment.objects.filter(application=self.application, criterion='PR').first()
        self.application.refresh_from_db()
        self.assertEqual(current.source_manifest['context'], source_context(self.application))
        listing = self.client.get(reverse('programs:applications', args=[self.program.pk]), {'eligibility': 'eligible'})
        self.assertContains(listing, self.application.member.full_name)
        from django.core.exceptions import ValidationError
        with patch('ewaf.four_pool.eligibility', side_effect=ValidationError('Authorized functional-need condition is not met.')):
            response = self.client.post(self.url, {**review_data(self.application), 'action': 'eligibility'})
        self.assertContains(response, 'Authorized functional-need condition is not met.')
        self.assertEqual(CriterionAssessment.objects.filter(application=self.application, criterion='PR').count(), before + 1)

    def test_unresolved_pr_cannot_be_overridden_by_checklist(self):
        data = review_data(self.application)
        original = AssistanceCase.objects.get(application=self.application).reviewed_at
        with patch('ewaf.evidence.source_context', return_value={'changed': True}):
            response = self.client.post(self.url, {**data, 'action': 'eligibility'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verify the current program qualification')
        self.assertEqual(AssistanceCase.objects.get(application=self.application).reviewed_at, original)

    def test_return_review_reuses_reason_version_and_permission_checks(self):
        self.application.refresh_from_db()
        response = self.client.post(self.url, {'action': 'return_review', 'return-version': self.application.version,
            'return-decision': 'pending', 'return-notes': 'Fictional source correction requires a renewed review.', 'return-confirm': 'on'})
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.status, 'ELIGIBLE')
        self.assertEqual(AssistanceCase.objects.get(application=self.application).decision, 'pending')
        response = self.client.post(self.url, {'action': 'return_review', 'return-version': self.application.version,
            'return-decision': 'approved', 'return-notes': 'Forged action', 'return-confirm': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AssistanceCase.objects.get(application=self.application).decision, 'pending')

    def test_private_review_report_and_csrf_permissions(self):
        limited = get_user_model().objects.create_user('combined_limited', is_staff=True)
        grant(limited, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(limited)
        for action in ('photo', 'qualification', 'eligibility', 'return_review'):
            self.assertEqual(self.client.post(self.url, {'action': action}).status_code, 403)
        report = self.client.get(reverse('reports:applications'), {'format': 'csv'}).content.decode('utf-8-sig')
        self.assertIn('Restricted,Restricted,Restricted,Restricted', report)
        self.assertNotIn('Recorded approval', report)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.officer)
        self.assertEqual(csrf.post(self.url, {'action': 'eligibility'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_simplified_weights_cannot_replace_policy_definitions(self):
        current = self.lock_policy()
        form = WeightConfigurationForm(configuration=current, program=self.program)
        self.assertNotIn('si_source', form.fields)
        form.cleaned_data = {'slider_proposal': '', 'weight_review': '', 'accept_derived_weights': False}
        original = deepcopy(current.policy)
        proposed = form.proposed()
        self.assertEqual(proposed, original)
        proposed['authority_reference'] = 'attempted mutation'
        self.assertEqual(current.policy, original)
        response = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        for removed in ('Authority and selection policy', 'SI measurement and normalization',
                        'Program Relevance eligibility', 'Review confirmation'):
            self.assertNotContains(response, removed)
        self.assertContains(response, 'Generate EWAF')


class DemoCommandSafetyTests(TestCase):
    def test_seed_cannot_target_regular_settings(self):
        with patch('core.management.commands.demo_data.require_local', return_value=('santolan_pwd', 'source')):
            with self.assertRaisesMessage(CommandError, 'dedicated fictional workspace'):
                call_command('demo_data', seed=True)

    def test_nonlocal_or_non_debug_connections_fail_before_any_mutation(self):
        from core.management.commands.demo_data import require_local
        with self.settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, 'project-local'):
                require_local()
