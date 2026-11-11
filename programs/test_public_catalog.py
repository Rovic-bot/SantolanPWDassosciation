from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Program
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class PublicCatalogTests(TestCase):
    def listing(self, **params):
        response = self.client.get(reverse('programs:list'), params)
        self.assertEqual(response.status_code, 200)
        return response

    def counts(self, response):
        return {item['value']: item['count'] for item in response.context['period_filters']}

    def test_search_category_and_period_combine_without_exposing_private_programs(self):
        wanted = create_program(name='Mobility support', assistance_type='Assistive Devices')
        create_program(name='Nutrition support', assistance_type='Food & Nutrition')
        hidden = create_program(name='Private mobility support', assistance_type='Private category')
        Program.objects.filter(pk=hidden.pk).update(status='draft')
        response = self.listing(q='support', category='Assistive Devices', period='available')
        self.assertEqual([row.pk for row in response.context['page_obj']], [wanted.pk])
        self.assertEqual(self.counts(response)['available'], 1)
        self.assertNotContains(response, 'Private category')
        self.assertNotContains(response, 'Private mobility support')
        self.assertContains(response, 'Clear filters')

    def test_counts_follow_filtered_results_and_distinguish_upcoming_from_closed(self):
        now = timezone.now()
        create_program(name='Food support')
        create_program(name='Food support upcoming', registration_opens_at=now + timedelta(hours=1))
        create_program(name='Food support ended', registration_closes_at=now - timedelta(hours=1))
        pending = create_program(name='Food support pending')
        Program.objects.filter(pk=pending.pk).update(policy_authorized_at=None)
        create_program(name='Other program')
        counts = self.counts(self.listing(q='Food support'))
        self.assertEqual(counts, {'all': 4, 'new': 4, 'available': 1, 'upcoming': 1, 'past': 1, 'unavailable': 1})

    def test_filters_persist_in_tabs_and_pagination_and_changing_tab_resets_page(self):
        for index in range(7):
            create_program(name=f'Mobility & care {index}', assistance_type='Assistive Devices')
        response = self.listing(q='Mobility & care', category='Assistive Devices', period='available')
        next_url = response.context['next_page_url']
        params = parse_qs(urlsplit(next_url).query)
        self.assertEqual(params, {'period': ['available'], 'q': ['Mobility & care'],
            'category': ['Assistive Devices'], 'page': ['2']})
        second = self.client.get(reverse('programs:list') + next_url)
        self.assertEqual(len(second.context['page_obj']), 1)
        for tab in second.context['period_filters']:
            params = parse_qs(urlsplit(tab['url']).query)
            self.assertNotIn('page', params)
            self.assertEqual(params['q'], ['Mobility & care'])
            self.assertEqual(params['category'], ['Assistive Devices'])

    def test_unknown_categories_and_empty_search_results_are_safe(self):
        create_program()
        response = self.listing(category='not a public category')
        self.assertEqual(response.context['category'], '')
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        response = self.listing(q='<script>alert(1)</script>')
        self.assertContains(response, 'No programs match your search.')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, 'Browse all programs')

    @override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
    def test_open_count_and_unavailable_filter_honor_application_readiness(self):
        admin = get_user_model().objects.create_superuser('catalog-admin', password='synthetic-only')
        ready = create_program(policy_authorized_by=admin)
        pending = create_program(policy_authorized_by=admin, ewaf_applicable=True)
        response = self.listing()
        self.assertEqual(self.counts(response)['available'], 1)
        self.assertEqual(self.counts(response)['unavailable'], 1)
        self.assertEqual([item.pk for item in self.listing(period='available').context['page_obj']], [ready.pk])
        self.assertEqual([item.pk for item in self.listing(period='unavailable').context['page_obj']], [pending.pk])

    def test_tracking_link_remains_feature_gated(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), override_settings(PROGRAM_TRACKING_ENABLED=enabled):
                response = self.listing()
                self.assertEqual('Track an application' in response.content.decode(), enabled)
                self.assertContains(response, 'Submitting an application does not guarantee selection')
