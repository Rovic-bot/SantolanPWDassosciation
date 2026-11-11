from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programs.tests import create_program
from . import operational_services as service
from .operational_models import OperationalConfiguration
from .operational_testsupport import OperationalHelpers
from .program_cards import applicant_counts, configuration_summary
from .weight_input import project, percentages


class EWAFCardTests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational(additional=3)
        self.client.force_login(self.officer)
        self.url = reverse('ewaf:operational_programs')

    def test_saved_ahp_weights_are_used_instead_of_slider_percentages(self):
        proposal = {'order': ['SI', 'ES', 'PA', 'ND'],
                    'weights': {'SI': 4000, 'ES': 3000, 'PA': 2000, 'ND': 1000}}
        judgments, result, provenance = project(proposal)
        self.proposal['weight_input'] = provenance
        saved = service.record_configuration(self.program.pk, user=self.officer,
            expected=service.configuration_token(self.program), proposed=self.proposal,
            judgments=judgments, status='LOCKED', reason='Fictional reviewed slider result', attested=True)
        actual = percentages(result['weights'])
        self.assertNotEqual(actual, proposal['weights'])
        response = self.client.get(self.url)
        program = response.context['page_obj'][0]
        self.assertEqual(program.ewaf_card['state'], 'ready')
        self.assertEqual([row['percent'] for row in program.ewaf_card['rows']],
                         [f'{actual[code] / 100:.2f}' for code in proposal['order']])
        self.assertEqual(saved.validation, result)
        for code, value in actual.items():
            self.assertContains(response, f'value="{value / 100:.2f}" max="100"')
        self.assertNotContains(response, 'program-card-dates')
        self.assertNotContains(response, 'program-category')
        self.assertNotContains(response, 'Created ')
        self.assertContains(response, reverse('ewaf:operational_workspace', args=[self.program.pk]))

    def test_unconfigured_draft_and_superseded_authorization_have_no_active_weights(self):
        self.assertEqual(configuration_summary(self.program)['state'], 'unconfigured')
        locked = self.lock_policy()
        original = deepcopy(locked.payload())
        service.record_configuration(self.program.pk, user=self.officer,
            expected=service.configuration_token(self.program), proposed=self.proposal,
            judgments=locked.judgments, status='DRAFT', reason='Fictional proposed revision')
        summary = configuration_summary(self.program)
        self.assertEqual(summary['state'], 'draft')
        self.assertTrue(all(row['percent'] is None for row in summary['rows']))
        page = self.client.get(self.url)
        self.assertFalse(page.context['page_obj'][0].selection['can_generate'])
        self.assertNotContains(page, 'Approved criteria weights')
        self.assertNotContains(page, 'aria-label="Socioeconomic Indicator weight"')
        locked.refresh_from_db()
        self.assertEqual(locked.payload(), original)
        self.assertEqual(OperationalConfiguration.objects.count(), 2)

    def test_stale_expired_and_corrupt_configuration_are_not_presented_as_ready(self):
        locked = self.lock_policy()
        with patch('ewaf.operational_services.timezone') as evaluation_clock:
            evaluation_clock.now.return_value = timezone.now() + timedelta(days=9)
            self.assertEqual(configuration_summary(self.program)['state'], 'review')
            self.assertEqual(len(self.client.get(self.url, {'configuration': 'ready'}).context['page_obj']), 0)
        self.program.version += 1
        self.program.save(update_fields=['version'])
        self.assertEqual(configuration_summary(self.program)['state'], 'review')
        locked.validation['weights']['SI'] = '0.99'
        with patch('ewaf.operational_services.Configuration.objects') as records:
            records.filter.return_value.first.return_value = locked
            self.assertEqual(configuration_summary(self.program)['state'], 'review')

    def test_search_status_sort_and_scope_work_together(self):
        self.lock_policy()
        empty = create_program(name='AAA empty EWAF', ewaf_applicable=True)
        create_program(name='Not an EWAF program')
        response = self.client.get(self.url, {'q': self.program.public_code, 'configuration': 'ready', 'sort': 'az'})
        self.assertEqual([p.pk for p in response.context['page_obj']], [self.program.pk])
        response = self.client.get(self.url, {'configuration': 'unconfigured', 'sort': 'az'})
        self.assertEqual([p.pk for p in response.context['page_obj']], [empty.pk])
        newest = list(self.client.get(self.url).context['page_obj'])
        oldest = list(self.client.get(self.url, {'sort': 'oldest'}).context['page_obj'])
        self.assertEqual([p.pk for p in newest], [p.pk for p in reversed(oldest)])

    def test_counts_and_capacity_follow_saved_reviews_and_authorized_selection(self):
        # Synthetic display fixtures exercise pending, ineligible and closed records.
        applications = list(self.program.applications.exclude(pk=self.application.pk).order_by('pk'))
        from assistance.models import AssistanceCase
        from programs.models import Program, ProgramApplication
        for application, status, eligibility in zip(applications,
                ['NEEDS_INFORMATION', 'INELIGIBLE', 'CLOSED'], ['review', 'ineligible', 'eligible']):
            ProgramApplication.objects.filter(pk=application.pk).update(status=status)
            AssistanceCase.objects.filter(application=application).update(eligibility_id=eligibility)
        program = applicant_counts(Program.objects.filter(pk=self.program.pk)).get()
        self.assertEqual((program.applicant_count, program.eligible_count, program.pending_count), (4, 1, 1))
        from programs.catalog import capacity_context
        capacity_context(program, self.officer)
        self.assertEqual(program.allocated_slots, 0)
        empty = create_program(name='Empty EWAF', ewaf_applicable=True)
        empty = applicant_counts(Program.objects.filter(pk=empty.pk)).get()
        self.assertEqual((empty.applicant_count, empty.eligible_count, empty.pending_count), (0, 0, 0))

    def test_selected_slots_and_workspace_preserve_actual_calculation(self):
        self.lock_policy()
        run = self.calculate()
        original = deepcopy(run.calculations)
        self.choose(run)
        page = self.client.get(self.url)
        program = page.context['page_obj'][0]
        self.assertEqual((program.allocated_slots, program.applicant_count, program.eligible_count), (1, 4, 4))
        workspace = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertContains(page, 'Slots used')
        self.assertContains(workspace, 'Generate EWAF')
        run.refresh_from_db()
        self.assertEqual(run.calculations, original)
