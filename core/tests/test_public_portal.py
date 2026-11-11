from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from config.environment import env_positive_int
from core.context_processors import navigation


class PublicPortalTests(TestCase):
    def test_primary_navigation_has_seven_sections_with_results_under_announcements(self):
        self.assertEqual(navigation(None)['public_navigation'], [
            ('core:home', 'Home'), ('core:about', 'About'),
            ('core:announcements', 'Announcements'), ('core:events', 'Events'),
            ('core:programs', 'Programs'),
            ('core:membership', 'Membership & PWD ID'),
            ('core:resources', 'Resources & Help'),
        ])

    def test_support_bookmarks_redirect_to_accessible_home_sections(self):
        routes = {
            'application_information': 'application-information',
            'privacy': 'privacy', 'accessibility': 'accessibility',
            'ewaf_information': 'ewaf', 'faq': 'faq',
        }
        home = self.client.get(reverse('core:home'))
        for route, anchor in routes.items():
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(reverse(f'core:{route}')), f'/#{anchor}')
                self.assertEqual(self.client.head(reverse(f'core:{route}')).status_code, 302)
                self.assertEqual(self.client.post(reverse(f'core:{route}')).status_code, 405)
                self.assertContains(home, f'id="{anchor}" tabindex="-1"')

    def test_help_desk_and_retired_referral_page_redirect_to_community_assistance(self):
        destination = reverse('core:resources') + '#referral-support'
        for route in ('core:contact', 'assistance:referral_information'):
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(reverse(route)), destination)
                self.assertEqual(self.client.head(reverse(route)).status_code, 302)
                self.assertEqual(self.client.post(reverse(route)).status_code, 405)
        resources = self.client.get(reverse('core:resources'))
        self.assertContains(resources, 'id="referral-support"')
        self.assertNotContains(resources, 'Read the guidance first')

    def test_every_public_page_is_accessible_and_marks_only_current_link(self):
        routes = navigation(None)['public_navigation']
        for route, label in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                main_navigation = response.content.decode().split('aria-label="Main navigation"', 1)[1].split('</nav>', 1)[0]
                self.assertEqual(main_navigation.count('aria-current="page"'), 1)
                for linked_route, _ in routes:
                    self.assertContains(response, f'href="{reverse(linked_route)}"')
                self.assertNotContains(response, 'type="password"')
                self.assertEqual(self.client.head(reverse(route)).status_code, 200)
                self.assertEqual(self.client.post(reverse(route)).status_code, 405)

    def test_home_features_current_activity_regardless_of_old_category(self):
        from datetime import timedelta
        from django.utils import timezone
        from events.models import Event
        now = timezone.now()

        def activity(title, days, **changes):
            return Event.objects.create(**{
                'title': title, 'event_category': 'general', 'status': 'published',
                'published_at': now - timedelta(days=4),
                'starts_at': now + timedelta(days=days), 'ends_at': now + timedelta(days=days,hours=2),
                **changes,
            })

        future = [activity('First public date', 1), activity('Second public date', 2)]
        activity('Later date', 3)
        activity('Past date', -1)
        activity('Draft date', 0, status='draft')
        legacy = activity('Uncategorized date', 0, event_category='')
        activity('Not released yet', 1, published_at=now + timedelta(hours=1))
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['current_event'], legacy)
        self.assertContains(response, 'href="' + reverse('core:events') + '" aria-label="Browse events: Uncategorized date"')
        self.assertNotContains(response, reverse('events:detail', args=[legacy.pk]))
        for event in future:
            self.assertNotContains(response, reverse('events:detail', args=[event.pk]))

    def test_registration_does_not_collect_data_until_opened(self):
        response = self.client.get(reverse('core:membership'))
        self.assertContains(response, 'Visit the Association Help Desk')
        # The shared help dialog has a close-only form; it is not an intake form.
        self.assertNotRegex(response.content.decode(), r'<form\b(?![^>]*method="dialog")')
        self.assertNotContains(response, 'type="file"')

    def test_contact_does_not_invent_address_or_phone_number(self):
        response = self.client.get(reverse('core:contact'), follow=True)
        self.assertContains(response, 'Confirm the address')
        self.assertNotContains(response, 'tel:')
        self.assertNotContains(response, 'mailto:')

    def test_login_limits_reject_disabled_or_invalid_configuration(self):
        for value in ('0', '-1', 'wrong', ''):
            with self.subTest(value=value), patch.dict('os.environ', {'TEST_LIMIT': value}):
                with self.assertRaises(ImproperlyConfigured):
                    env_positive_int('TEST_LIMIT', 10)
