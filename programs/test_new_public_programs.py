"""Public recency is a one-hour publication window, not application readiness."""
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Program
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class NewPublicProgramTests(TestCase):
    def setUp(self):
        self.at = timezone.now().replace(microsecond=0)
        clock = patch('programs.public_catalog.timezone.now', return_value=self.at)
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    def program(self, name, *, age=timedelta(), **changes):
        program = create_program(name=name, ewaf_applicable=True)
        Program.objects.filter(pk=program.pk).update(published_at=self.at - age, **changes)
        program.refresh_from_db()
        return program

    def listing(self, **params):
        response = self.client.get(reverse('core:programs'), {'period': 'new', **params})
        self.assertEqual(response.status_code, 200)
        return response

    def counts(self, response):
        return {tab['value']: tab['count'] for tab in response.context['period_filters']}

    def test_last_hour_boundaries_and_sort_use_publication_not_creation_or_edits(self):
        oldest = self.program('Just inside the window', age=timedelta(hours=1) - timedelta(microseconds=1))
        minute = self.program('Published a minute ago', age=timedelta(minutes=1))
        newest = self.program('Older draft published now', created_at=self.at - timedelta(days=90))
        self.program('Exactly one hour old', age=timedelta(hours=1))
        self.program('Old publication edited now', age=timedelta(days=1), updated_at=self.at)
        self.program('Future publication', age=-timedelta(microseconds=1))

        response = self.listing()
        self.assertEqual([item.pk for item in response.context['page_obj']], [newest.pk, minute.pk, oldest.pk])
        self.assertEqual(self.counts(response)['new'], 3)
        self.assertContains(response, 'Programs published in the last hour, newest first.')
        self.assertNotContains(response, 'Future publication')

    def test_drafts_archives_and_cancelled_programs_are_never_new(self):
        for status in ('draft', 'archived', 'cancelled'):
            self.program(f'Hidden from New: {status}', status=status)
        response = self.listing()
        self.assertEqual(self.counts(response)['new'], 0)
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertContains(response, 'No programs published in the last hour.')
        self.assertNotContains(response, 'Hidden from New:')

    def test_program_expires_at_one_hour_without_changing_its_publication_or_open_status(self):
        program = self.program('Rolling publication window')
        self.assertEqual(self.counts(self.listing())['new'], 1)
        self.clock.return_value = self.at + timedelta(hours=1)
        expired = self.listing()
        self.assertEqual(self.counts(expired)['new'], 0)
        self.assertEqual(expired.context['page_obj'].paginator.count, 0)
        self.assertContains(self.listing(period='available'), program.name)
        self.assertContains(self.listing(period='all'), program.name)
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.published_at, self.at)

    def test_new_filter_retains_search_category_pagination_and_tab_counts(self):
        wanted = [self.program(f'Mobility & care {index}', age=timedelta(minutes=index),
                              assistance_type='Assistive Devices') for index in range(7)]
        self.program('Mobility & care old', age=timedelta(hours=2), assistance_type='Assistive Devices')
        self.program('Different title', assistance_type='Assistive Devices')
        self.program('Mobility & care in another category', assistance_type='Food & Nutrition')
        response = self.listing(q='Mobility & care', category='Assistive Devices')
        self.assertEqual(self.counts(response)['new'], 7)
        self.assertEqual(self.counts(response)['all'], 8)
        self.assertEqual([item.pk for item in response.context['page_obj']], [item.pk for item in wanted[:6]])
        next_url = response.context['next_page_url']
        self.assertEqual(parse_qs(urlsplit(next_url).query), {
            'period': ['new'], 'q': ['Mobility & care'], 'category': ['Assistive Devices'], 'page': ['2']})
        second = self.client.get(reverse('core:programs') + next_url)
        self.assertEqual([item.pk for item in second.context['page_obj']], [wanted[-1].pk])
        for tab in second.context['period_filters']:
            self.assertNotIn('page', parse_qs(urlsplit(tab['url']).query))

    @override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
    def test_new_does_not_claim_applications_are_open_or_bypass_ewaf_readiness(self):
        pending = self.program('Published but awaiting EWAF readiness')
        upcoming = self.program('Published for next week', registration_opens_at=self.at + timedelta(hours=1))
        ended = self.program('Published after applications closed', registration_closes_at=self.at - timedelta(minutes=1))
        response = self.listing()
        self.assertEqual(self.counts(response)['new'], 3)
        self.assertEqual(self.counts(response)['available'], 0)
        statuses = {item.pk: item.public_application_status for item in response.context['page_obj']}
        self.assertEqual(statuses, {pending.pk: 'unavailable', upcoming.pk: 'upcoming', ended.pk: 'ended'})

    def test_new_tab_is_present_next_to_all_programs_and_keeps_plain_get_fallback(self):
        for route in ('core:programs', 'programs:list'):
            response = self.client.get(reverse(route), {'period': 'available'})
            tabs = response.context['period_filters']
            self.assertEqual([tab['value'] for tab in tabs[:3]], ['all', 'new', 'available'])
            self.assertEqual(tabs[1]['url'], '?period=new')
            self.assertEqual(tabs[1]['count'], 0)
            self.assertContains(response, 'title="Published within the last hour"')
            self.assertEqual(self.client.get(reverse(route), {'period': 'new'}).context['period'], 'new')
