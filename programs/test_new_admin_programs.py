"""Administrative New filtering uses the public one-hour publication window."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.tests import create_member
from membership.tests import grant
from .models import Program, ProgramApplication
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class NewAdminProgramTests(TestCase):
    def setUp(self):
        self.at = timezone.now().replace(microsecond=0)
        clock = patch('programs.catalog.timezone.now', return_value=self.at)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.admin = get_user_model().objects.create_superuser('SYNTHETIC-NEW-FILTER')
        self.client.force_login(self.admin)

    def program(self, name, *, age=timedelta(), **changes):
        program = create_program(name=name, ewaf_applicable=True, slots=5)
        Program.objects.filter(pk=program.pk).update(published_at=self.at - age, **changes)
        program.refresh_from_db()
        return program

    def listing(self, **params):
        response = self.client.get(reverse('program_portfolio'), {'status': 'new', **params})
        self.assertEqual(response.status_code, 200)
        return response

    def test_status_option_uses_publication_order_and_preserves_actual_status(self):
        older = self.program('A earlier publication', age=timedelta(minutes=15))
        latest = self.program('Z older draft published now', created_at=self.at - timedelta(days=90))
        response = self.listing()
        self.assertIn(('new', 'New (last hour)'), response.context['statuses'])
        self.assertEqual(response.context['status'], 'new')
        self.assertEqual([p.pk for p in response.context['page_obj']], [latest.pk, older.pk])
        self.assertEqual(dict(response.context['sort_options'])['newest'], 'Newest published first')
        self.assertContains(response, 'data-status="published">Published')
        self.assertNotContains(response, 'data-status="new"')
        self.assertEqual([p.pk for p in self.listing(sort='az').context['page_obj']], [older.pk, latest.pk])

    def test_admin_and_public_share_exact_boundaries_and_visibility(self):
        current = self.program('Published now')
        edge = self.program('Inside the hour', age=timedelta(hours=1) - timedelta(microseconds=1))
        self.program('Exactly one hour old', age=timedelta(hours=1))
        self.program('Edited older publication', age=timedelta(days=1), updated_at=self.at)
        self.program('Future publication', age=-timedelta(microseconds=1))
        for status in ('draft', 'archived', 'cancelled'):
            self.program(f'Not new: {status}', status=status)
        admin = self.listing()
        public = self.client.get(reverse('core:programs'), {'period': 'new'})
        expected = [current.pk, edge.pk]
        self.assertEqual([p.pk for p in admin.context['page_obj']], expected)
        self.assertEqual([p.pk for p in public.context['page_obj']], expected)

    def test_expiry_removes_only_the_new_filter_match(self):
        program = self.program('Time limited New label')
        self.assertEqual(self.listing().context['page_obj'].paginator.count, 1)
        self.clock.return_value = self.at + timedelta(hours=1)
        # An hour also expires the staff session; reauthenticate to check the filter.
        self.client.logout()
        self.client.force_login(self.admin)
        expired = self.listing()
        self.assertEqual(expired.context['page_obj'].paginator.count, 0)
        self.assertContains(expired, 'No newly published programs found')
        self.assertContains(self.listing(status='published'), program.name)
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.published_at, self.at)

    def test_search_category_registration_and_applications_combine_with_new(self):
        wanted = self.program('Mobility matching', assistance_type='Assistive Devices')
        expired = self.program('Mobility older', age=timedelta(hours=2), assistance_type='Assistive Devices')
        self.program('Mobility no applications', assistance_type='Assistive Devices')
        self.program('Mobility other category', assistance_type='Food & Nutrition')
        member = create_member('SYNTHETIC-NEW-FILTER-MEMBER')
        for index, program in enumerate((wanted, expired)):
            ProgramApplication.objects.create(program=program, member=member,
                public_reference=f'SYNTHETIC-NEW-FILTER-{index}')
        response = self.listing(q='Mobility', assistance_type='Assistive Devices',
                                registration='open', with_applications='1')
        self.assertEqual([p.pk for p in response.context['page_obj']], [wanted.pk])

    def test_pagination_keeps_new_and_other_filters(self):
        programs = [self.program(f'Paged new {index:02}', age=timedelta(minutes=index),
                    assistance_type='Healthcare') for index in range(21)]
        first = self.listing(q='Paged new', assistance_type='Healthcare')
        second = self.listing(q='Paged new', assistance_type='Healthcare', page=2)
        self.assertEqual(first.context['page_obj'].paginator.count, 21)
        self.assertEqual([p.pk for p in first.context['page_obj']], [p.pk for p in programs[:20]])
        self.assertEqual([p.pk for p in second.context['page_obj']], [programs[-1].pk])
        self.assertContains(second, 'status=new')
        self.assertContains(second, 'assistance_type=Healthcare')
        self.assertContains(second, 'q=Paged+new')

    def test_other_statuses_keep_creation_sort_and_registration_closed_behavior(self):
        older = self.program('Older creation', created_at=self.at - timedelta(days=10))
        newer = self.program('Newer creation', age=timedelta(minutes=5))
        closed = self.program('Closed registration', registration_closes_at=self.at - timedelta(minutes=1),
                              created_at=self.at - timedelta(days=20))
        published = self.listing(status='published')
        self.assertEqual([p.pk for p in published.context['page_obj']], [newer.pk, older.pk, closed.pk])
        self.assertEqual(dict(published.context['sort_options'])['newest'], 'Newest created first')
        self.assertEqual([p.pk for p in self.listing(status='closed').context['page_obj']], [closed.pk])

    def test_new_filter_retains_admin_access_and_capacity_permissions(self):
        self.program('Protected admin program')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('program_portfolio'), {'status': 'new'}).status_code, 302)
        viewer = get_user_model().objects.create_user('SYNTHETIC-NEW-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('program_portfolio'), {'status': 'new'}).status_code, 403)
        grant(viewer, 'programs.view_program')
        response = self.listing()
        self.assertContains(response, 'Protected admin program')
        self.assertContains(response, 'Usage restricted')
        self.assertNotContains(response, 'Create program')
