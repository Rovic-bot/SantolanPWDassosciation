"""Counts stay distinct across current selections, actual receipts and voids."""
from django.test import RequestFactory, TestCase
from django.urls import reverse

from ewaf.operational_testsupport import OperationalHelpers
from membership.tests import grant
from programs.models import Program
from programs.tests import create_program
from . import tests as fixtures
from .models import AssistanceRelease
from .release_portfolio import receipt_counts, workspace
from .services import reserved_slots


class ReleasePortfolioTests(TestCase):
    setUp = fixtures.AssistanceTests.setUp
    review = fixtures.AssistanceTests.review
    approve = fixtures.AssistanceTests.approve
    release = fixtures.AssistanceTests.release
    void = fixtures.AssistanceTests.void

    def summary(self):
        return receipt_counts([self.program])[self.program.pk]

    def test_selection_receipt_and_void_have_separate_counts(self):
        self.assertEqual(self.summary()['selected_count'], 0)
        self.approve()
        summary = self.summary()
        self.assertEqual((summary['applicant_count'], summary['selected_count'],
                          summary['received_count'], summary['pending_count']), (1, 1, 0, 1))
        self.assertEqual(summary['allocated_count'], reserved_slots(self.program))
        receipt = self.release()
        summary = self.summary()
        self.assertEqual((summary['selected_count'], summary['received_count'], summary['pending_count']), (1, 1, 0))
        self.void(receipt)
        summary = self.summary()
        self.assertEqual((summary['selected_count'], summary['received_count'], summary['pending_count']), (0, 0, 0))
        self.assertEqual(AssistanceRelease.objects.count(), 1)

    def test_read_access_is_required_and_overview_excludes_member_details(self):
        url = reverse('assistance:release_programs')
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        grant(self.viewer, 'assistance.view_assistancerelease')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.member.control_number)
        self.assertNotContains(response, self.application.public_reference)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_all_programs_and_filters_use_bounded_summary_queries(self):
        for index in range(22):
            create_program(name=f'Empty program {index:02d}')
        request = RequestFactory().get('/assistance/releases/', {'selected': str(self.program.pk)})
        with self.assertNumQueries(2):
            result = workspace(request)
        self.assertEqual(len(result['page_obj']), 23)
        self.assertEqual(result['selected_id'], str(self.program.pk))
        empty = next(program for program in result['program_rows'] if program.pk != self.program.pk)
        self.assertEqual(empty.release_summary['received_count'], 0)
        request = RequestFactory().get('/assistance/releases/', {
            'q': self.program.public_code, 'status': 'published',
            'assistance_type': self.program.assistance_type, 'with_applications': '1', 'sort': 'az'})
        self.assertEqual([p.pk for p in workspace(request)['page_obj']], [self.program.pk])
        request = RequestFactory().get('/assistance/releases/', {'q': 'not-a-real-program', 'selected': str(self.program.pk)})
        result = workspace(request)
        self.assertEqual(result['selected_id'], '')
        self.assertEqual(len(result['page_obj']), 0)


class EWAFReleasePortfolioTests(OperationalHelpers, TestCase):
    def test_only_latest_ewaf_decisions_are_selected_and_no_runs_are_loaded(self):
        self.setup_operational(additional=1)
        self.lock_policy()
        run = self.calculate()
        self.choose(run)
        selected = receipt_counts([self.program])[self.program.pk]
        self.assertEqual(selected['selected_count'], 1)
        self.assertEqual(selected['pending_count'], 1)
        self.assertEqual(selected['allocated_count'], reserved_slots(self.program))
        self.choose(run, expected_revision=1, outcome='NOT_SELECTED')
        latest = receipt_counts([self.program])[self.program.pk]
        self.assertEqual(latest['selected_count'], 0)
        self.assertEqual(latest['pending_count'], 0)
        self.assertEqual(latest['allocated_count'], reserved_slots(self.program))
        # This read model uses decisions/counts, never configuration or scores.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            receipt_counts(list(Program.objects.all()))
        self.assertFalse(any('FROM `ewaf_operationalrun`' in item['sql'] for item in queries))
