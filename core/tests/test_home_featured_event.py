"""Current-event presentation uses publication and time boundaries, never private rows."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from events.models import Event
from members.models import Member
from membership.models import MembershipApplication


class HomeFeaturedEventTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 7, 5, tzinfo=timezone.utc)
        clock = patch('django.utils.timezone.now', return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def event(self, **changes):
        return Event.objects.create(**{
            'title': 'Community Gathering', 'description': 'Published event description.',
            'location': 'Synthetic venue', 'status': Event.Status.PUBLISHED,
            'published_at': self.now - timedelta(days=1),
            'starts_at': self.now - timedelta(hours=1),
            'ends_at': self.now + timedelta(hours=1), **changes,
        })

    def test_feature_is_current_published_event_not_future_or_ended_or_withdrawn(self):
        current = self.event()
        self.event(title='Future activity', starts_at=self.now + timedelta(minutes=1))
        self.event(title='Ended activity', ends_at=self.now)
        self.event(title='Private draft', status=Event.Status.DRAFT)
        self.event(title='Cancelled activity', status=Event.Status.CANCELLED)
        self.event(title='Archived activity', status=Event.Status.ARCHIVED)
        self.event(title='Unreleased activity', published_at=self.now + timedelta(minutes=1))
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['current_event'], current)
        self.assertContains(response, 'href="' + reverse('core:events') + '" aria-label="Browse events: Community Gathering"')
        self.assertNotContains(response, reverse('events:detail', args=[current.pk]))
        for text in ['Future activity', 'Ended activity', 'Private draft', 'Cancelled activity',
                     'Archived activity', 'Unreleased activity']:
            self.assertNotContains(response, text)

    def test_most_recently_started_current_event_wins_including_start_boundary(self):
        self.event(title='Earlier ongoing activity')
        latest = self.event(title='Starting now', starts_at=self.now)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['current_event'], latest)
        self.assertContains(response, 'Starting now')

    def test_no_current_event_has_honest_calendar_fallback(self):
        self.event(title='Future activity', starts_at=self.now + timedelta(minutes=1))
        response = self.client.get(reverse('core:home'))
        self.assertIsNone(response.context['current_event'])
        self.assertContains(response, 'No event happening now')
        self.assertContains(response, 'aria-label="View community calendar"')

    def test_missing_image_uses_title_initials_and_escapes_title(self):
        self.event(title='  Community   Gathering <script>bad()</script>')
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['current_event_initials'], 'CG')
        self.assertContains(response, 'class="home-event-initials" aria-hidden="true">CG</span>')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertNotContains(response, 'community/activities-640.webp')

    def test_event_image_uses_existing_public_image_view_and_description(self):
        event = self.event(image='events/synthetic/banner.png', image_alt='Community gathering banner')
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, reverse('events:image', args=[event.pk]))
        self.assertContains(response, 'alt="Community gathering banner"')
        self.assertNotContains(response, 'class="home-event-initials"')

    def test_member_statistic_is_only_active_unarchived_aggregate(self):
        for number, changes in enumerate(({}, {'is_active': False},
                                         {'is_active': False, 'archived_at': self.now})):
            data = {'full_name': f'Private Synthetic Person {number}', 'birthdate': date(1980, 1, 1),
                    'control_number': f'SYNTHETIC-{number}', 'address': 'Private synthetic address'}
            application = MembershipApplication.objects.create(submission_key=uuid4(), **data)
            Member.objects.create(application=application, **data, **changes)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['public_member_count'], 1)
        self.assertContains(response, '1 active Association members')
        self.assertNotContains(response, 'Private Synthetic Person')
        self.assertNotContains(response, 'Private synthetic address')

    def test_all_six_guidance_cards_preserve_bookmarks_and_published_text(self):
        response = self.client.get(reverse('core:home'))
        for anchor in ['application-information', 'contact', 'faq', 'ewaf', 'privacy', 'accessibility']:
            self.assertContains(response, f'id="{anchor}" tabindex="-1"')
        self.assertContains(response, 'class="public-swipe-card" data-swipe-card id=', count=6)
        self.assertContains(response, 'Member records, application documents and calendar photos are private.')
