from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from core.templatetags.workspace_navigation import workspace_navigation
from membership.tests import grant
from .models import Event, EventLog
from .observances import REFERENCE_CATALOGUE, calendar_months, validate_source_url
from .services import observance_reference_calendar, public_observance_calendar
from .tests import create_event, event_data


class ObservanceReferenceTests(SimpleTestCase):
    def test_reference_catalogue_has_twelve_monthly_observances(self):
        self.assertEqual(len(REFERENCE_CATALOGUE), 12)
        self.assertEqual([item.month for item in REFERENCE_CATALOGUE], list(range(1, 13)))
        months = calendar_months(REFERENCE_CATALOGUE)
        self.assertEqual(len(months), 12)
        self.assertEqual(months[4]['observances'][0]['title'], 'Global Accessibility Awareness Day')
        self.assertEqual(months[5]['observances'][0]['category_label'], 'Health related — not PWD-specific')
        self.assertEqual(months[6]['observances'][0]['title'], 'National Disability Rights Week')

    def test_recurrences_are_explicit_and_never_year_specific(self):
        self.assertEqual([item.recurrence_rule for item in REFERENCE_CATALOGUE], [
            'Third week of January', 'Whole month of February', 'Last Monday of March',
            'April 2', 'Third Thursday of May', 'Whole month of June', 'July 17–23', 'August 1', 'September 16–22',
            'Third week of October', 'November 10–16', 'December 3',
        ])
        for item in REFERENCE_CATALOGUE:
            if item.recurrence_kind in ('third_week', 'last_monday', 'whole_month', 'third_thursday'):
                self.assertIsNone(item.day_start)
                self.assertIsNone(item.day_end)

    def test_invalid_or_invented_recurrence_dates_are_rejected(self):
        candidate = REFERENCE_CATALOGUE[0]
        cases = [dict(month=0), dict(month=13), dict(month=True), dict(recurrence_kind='weekly'),
                 dict(day_start=15), dict(day_end=21), dict(category='program'),
                 dict(month=4, recurrence_kind='fixed_day', day_start=31),
                 dict(recurrence_kind='fixed_day', day_start=1, day_end=2),
                 dict(recurrence_kind='fixed_range', day_start=23, day_end=17),
                 dict(recurrence_kind='fixed_range', day_start=17, day_end=17),
                 dict(recurrence_kind='fixed_day', day_start=True)]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                replace(candidate, **changes)

    def test_source_links_require_direct_reviewed_https_hosts(self):
        for item in REFERENCE_CATALOGUE:
            validate_source_url(item.source_url)
        for url in ('javascript:alert(1)', 'http://ncda.gov.ph/source', '//ncda.gov.ph/source',
                    'https://ncda.gov.ph.evil.example/source', 'https://evil.example/ncda.gov.ph',
                    'https://ncda.gov.ph@evil.example/source', 'https://user@ncda.gov.ph/source',
                    'https://ncda.gov.ph:443/source', 'https://127.0.0.1/source',
                    'https://ncda.gov.ph/source?redirect=https://evil.example',
                    'https://ncda.gov.ph/source#tracking', 'https://ncda.gov.ph/\nsource',
                    'https://ncda.gov.ph/\\evil.example', 'https://unreviewed.gov.ph/source'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_source_url(url)

    def test_reference_text_is_required_and_bounded(self):
        for field, value in (('title', ' '), ('title', 'a' * 201), ('legal_basis', ''),
                             ('description', 'a' * 2001), ('source_url', '')):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                replace(REFERENCE_CATALOGUE[0], **{field: value})

    @patch('events.services.observance_storage_ready', return_value=False)
    def test_public_service_never_falls_back_to_reference_candidates(self, readiness):
        self.assertEqual(len(public_observance_calendar()), 12)
        self.assertTrue(all(not month['observances'] for month in public_observance_calendar()))

    def test_card_renderer_escapes_content_and_has_named_sources(self):
        fictional = replace(REFERENCE_CATALOGUE[0], title='<script>fictional</script>',
                            description='<img src=x onerror=alert(1)>')
        html = render_to_string('events/observance_calendar.html', {
            'observance_months': calendar_months((fictional,)), 'reference_preview': True,
        })
        self.assertIn('&lt;script&gt;fictional&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)
        self.assertIn('aria-label="Observance months"', html)
        self.assertIn('aria-labelledby="observance-title-1-1"', html)
        self.assertIn('Official source<span class="visually-hidden"> for ', html)
        self.assertNotIn('<time', html)
        self.assertIn('No selected observance for May.', html)


class ObservanceAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user('fictional_observance_viewer', is_staff=True)
        grant(cls.viewer, 'accounts.access_dashboard', 'events.view_annualobservance')
        cls.staff = get_user_model().objects.create_user('fictional_other_staff', is_staff=True)
        grant(cls.staff, 'accounts.access_dashboard')
        cls.admin = get_user_model().objects.create_superuser('fictional_observance_admin')

    def test_anonymous_request_redirects_and_direct_service_denies(self):
        response = self.client.get(reverse('events:observances'))
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(PermissionDenied):
            observance_reference_calendar(user=AnonymousUser())

    def test_staff_without_event_view_permission_is_denied_at_both_boundaries(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('events:observances')).status_code, 403)
        with self.assertRaises(PermissionDenied):
            observance_reference_calendar(user=self.staff)

    def test_nonstaff_inactive_and_missing_dashboard_users_cannot_use_service(self):
        for changes in ({'is_staff': False}, {'is_active': False}):
            user = get_user_model().objects.get(pk=self.viewer.pk)
            for name, value in changes.items():
                setattr(user, name, value)
            with self.subTest(changes=changes), self.assertRaises(PermissionDenied):
                observance_reference_calendar(user=user)
        user = get_user_model().objects.create_user('fictional_no_dashboard', is_staff=True)
        grant(user, 'events.view_annualobservance')
        with self.assertRaises(PermissionDenied):
            observance_reference_calendar(user=user)

    def test_authorized_viewer_sees_calendar_without_reference_or_write_controls(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('events:observances'))
        self.assertNotContains(response, 'Verified annual references')
        self.assertNotContains(response, 'Annual calendar reference')
        self.assertNotContains(response, 'Create event')
        self.assertNotContains(response, 'Create observance')
        self.assertEqual(response.content.count(b'class="event-quarter event-glass"'), 4)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(EventLog.objects.count(), 0)
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_mutation_methods_are_unavailable_even_to_superuser(self):
        self.client.force_login(self.admin)
        for method in ('post', 'put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse('events:observances'), {
                    'action': 'published', 'version': 0, 'title': 'Forged observance',
                })
                self.assertEqual(response.status_code, 405)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(EventLog.objects.count(), 0)

    def test_public_requests_cannot_enable_preview_or_publication(self):
        for query in ('', '?preview=1', '?status=published', '?period=past&reference_preview=true'):
            response = self.client.get(reverse('core:events') + query)
            self.assertContains(response, 'aria-label="Yearly awareness calendar"')
            self.assertNotContains(response, 'DATES FOR AWARENESS')
            for item in REFERENCE_CATALOGUE:
                self.assertNotContains(response, item.title)
                self.assertNotContains(response, item.source_url)
            self.assertNotContains(response, 'fictional_observance')

    def test_historical_events_are_retained_outside_the_annual_calendar(self):
        now = timezone.now()
        for index in range(11):
            create_event(title=f'Fictional upcoming {index:02d}')
        past = create_event(title='Fictional past activity', starts_at=now - timedelta(days=2),
                            ends_at=now - timedelta(days=1))
        for status in ('draft', 'archived'):
            data = event_data(title=f'Private {status} activity')
            data.pop('notes')
            Event.objects.create(**data, status=status)
        response = self.client.get(reverse('core:events'))
        self.assertEqual(len(response.context['observance_months']), 12)
        self.assertNotContains(response, past.title)
        self.assertNotContains(response, 'Private draft activity')
        self.assertNotContains(response, 'Private archived activity')
        # Every event is reachable in the swipe row, beyond the former ten-item page.
        self.assertContains(response, 'Fictional upcoming 10')
        self.assertNotContains(response, 'id="event-period"')
        self.assertNotContains(response, '?period=upcoming&amp;page=2')
        response = self.client.get(reverse('core:events'), {'period': 'past'})
        self.assertContains(response, past.title)
        self.assertNotContains(response, 'Fictional upcoming')
        self.assertEqual(Event.objects.count(), 14)
        response = self.client.get(reverse('core:events'), {'period': 'invalid', 'page': 2})
        self.assertEqual(len(response.context['observance_months']), 12)

    def test_existing_eight_groups_contain_one_active_observance_link(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('events:observances'))
        groups = workspace_navigation({'request': response.wsgi_request})
        self.assertEqual(len(groups), 8)
        active = [(group['key'], link['label']) for group in groups for link in group['links'] if link['active']]
        self.assertEqual(active, [('programs', 'Events Calendar')])
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotContains(response, reverse('events:observances'))

    def test_new_permissions_exist_but_are_not_granted_to_existing_event_staff(self):
        self.assertTrue(any('observance' in model._meta.model_name for model in apps.get_app_config('events').get_models()))
        self.assertTrue(Permission.objects.filter(content_type__app_label='events', codename='publish_annualobservance').exists())
        self.assertFalse(self.staff.has_perm('events.publish_annualobservance'))
        grant(self.staff, 'events.view_event', 'events.publish_event')
        self.staff = get_user_model().objects.get(pk=self.staff.pk)
        self.assertFalse(self.staff.has_perm('events.view_annualobservance'))
