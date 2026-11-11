"""The Announcements chooser only lists programs with submitted applications."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from programs.testsupport import application_fixture, private_media


class AnnouncementApplicantCatalogTests(TestCase):
    def setUp(self):
        private_media(self)
        self.admin = get_user_model().objects.create_superuser('applicant_catalog_admin')
        self.client.force_login(self.admin)
        self.program = create_program(name='Program with applicants')
        self.application = application_fixture(self.program, create_member('CATALOG-001'))

    def test_empty_programs_are_excluded_before_pagination_and_counts(self):
        # More than a page of newer empty programs must not displace this card.
        for index in range(21):
            create_program(name=f'Empty program {index}')
        application_fixture(self.program, create_member('CATALOG-002'))
        for route in ('announcements:manage_list', 'announcements:choose_results',
                      'announcements:choose_recipients'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                page = response.context['page_obj']
                self.assertEqual(page.paginator.count, 1)
                self.assertEqual([(item.pk, item.applicant_count) for item in page],
                                 [(self.program.pk, 2)])
                self.assertNotContains(response, 'Empty program')
                self.assertNotContains(response, 'id="program-applicants"')

    def test_filter_reset_and_query_parameters_cannot_include_empty_programs(self):
        empty = create_program(name='Empty searchable program')
        url = reverse('announcements:manage_list')
        for filters in ({}, {'with_applications': '0'}, {'with_applications': '1'},
                        {'page': '999', 'sort': 'oldest'}):
            with self.subTest(filters=filters):
                response = self.client.get(url, filters)
                self.assertEqual(response.context['page_obj'].paginator.count, 1)
                self.assertNotContains(response, empty.name)
        response = self.client.get(url, {'q': empty.name, 'with_applications': '0'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertContains(response, 'No programs match your filters.')

    def test_applicants_count_regardless_of_review_or_program_status(self):
        url = reverse('announcements:manage_list')
        for program_status in ('draft', 'published', 'cancelled'):
            self.program.status = program_status
            self.program.save(update_fields=['status'])
            for application_status in ('PENDING_PHOTO_VERIFICATION', 'INELIGIBLE', 'CLOSED'):
                with self.subTest(program=program_status, application=application_status):
                    ProgramApplication.objects.filter(pk=self.application.pk).update(status=application_status)
                    response = self.client.get(url, {'status': program_status})
                    self.assertEqual([item.pk for item in response.context['page_obj']], [self.program.pk])
