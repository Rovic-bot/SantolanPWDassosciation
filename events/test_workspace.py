"""Private event workspace presentation without new event or RSVP policy."""
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.tests import create_member
from membership.tests import grant
from programs.models import ProgramApplication
from programs.tests import create_program
from .annual_calendar import publish_annual_calendar
from .models import AnnualObservance, Event, EventLog, EventRegistration
from .tests import create_event


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class EventWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('synthetic_event_workspace')
        now = timezone.now()
        cls.first = create_event(title='Community health orientation', event_category='general', capacity=4,
            location='Santolan community hall')
        cls.program = create_program(slots=2)
        cls.linked = create_event(title='Inclusive training session', event_category='specific',
            application_program=cls.program, capacity=2, starts_at=now + timedelta(days=8), ends_at=now + timedelta(days=8, hours=2))
        cls.past = create_event(title='Earlier gathering', starts_at=now - timedelta(days=8), ends_at=now - timedelta(days=8, hours=-2))
        cls.draft = create_event(title='Draft activity', event_category='general', capacity=None)
        Event.objects.filter(pk=cls.draft.pk).update(status='draft', published_at=None)
        cls.cancelled = create_event(title='Cancelled activity', starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=2))
        Event.objects.filter(pk=cls.cancelled.pk).update(status='cancelled')
        for index, state in enumerate(('registered', 'confirmed', 'cancelled')):
            member = create_member(f'SYNTH-EVENT-{index}')
            EventRegistration.objects.create(event=cls.first, member=member, status=state)
            ProgramApplication.objects.create(program=cls.program, member=member, public_reference=f'SYNTH-EVENT-APP-{index}')
        EventRegistration.objects.create(event=cls.linked, member=member, status='registered')
        publish_annual_calendar(user=cls.admin, notes='Synthetic browser calendar fixture.')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_alias_existing_routes_and_navigation(self):
        for url in (reverse('event_workspace'), '/admin/events/', reverse('events:manage_list')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Community events')
            self.assertContains(response, 'aria-current="page">Events Calendar')
            self.assertContains(response, reverse('program_portfolio'))
            self.assertContains(response, reverse('events:create'))
        self.assertEqual(self.client.post(reverse('event_workspace')).status_code, 405)

    def test_registration_capacity_and_metrics_are_absent_without_deleting_records(self):
        response = self.client.get(reverse('event_workspace'))
        for text in ('Upcoming events', 'Total registrations', 'Average event capacity',
                     'Legacy registrations', 'event-capacity', 'Event readiness', 'event-metrics'):
            self.assertNotContains(response, text)
        self.assertEqual(EventRegistration.objects.count(), 4)
        self.assertEqual(ProgramApplication.objects.count(), 3)
        self.assertEqual(response.context['next_event']['record'].pk, self.first.pk)

    def test_search_category_status_schedule_and_empty_state(self):
        url = reverse('event_workspace')
        result = self.client.get(url, {'q': 'community hall', 'category': 'general', 'status': 'published'})
        self.assertEqual([row.pk for row in result.context['page_obj']], [self.first.pk])
        past = self.client.get(url, {'period': 'past'})
        self.assertEqual([row.pk for row in past.context['page_obj']], [self.past.pk])
        all_dates = self.client.get(url, {'period': 'all'})
        times = [row.starts_at for row in all_dates.context['page_obj']]
        self.assertEqual(times, sorted(times))
        empty = self.client.get(url, {'q': '<script>unknown</script>'})
        self.assertContains(empty, 'No events found')
        self.assertNotContains(empty, '<script>unknown</script>')
        self.assertContains(empty, '&lt;script&gt;unknown&lt;/script&gt;')

    def test_calendar_month_navigation_multiday_and_date_filter(self):
        month = (timezone.localdate().replace(day=28) + timedelta(days=4)).replace(day=1)
        start = timezone.make_aware(datetime.combine(month, time.min))
        item = create_event(title='Three day community activity', starts_at=start, ends_at=start + timedelta(days=3))
        response = self.client.get(reverse('event_workspace'), {'month': month.strftime('%Y-%m'), 'q': 'Three day'})
        active = [day['day'].day for week in response.context['calendar']['weeks'] for day in week if day['active']]
        self.assertEqual(active, [1, 2, 3])  # End at midnight must not highlight day four.
        day = self.client.get(reverse('event_workspace'), {'day': (month + timedelta(days=1)).isoformat()})
        self.assertIn(item.pk, [row.pk for row in day.context['page_obj']])
        self.assertEqual(day.context['period'], 'all')
        self.assertIn('month=', response.context['calendar']['next'])
        invalid = self.client.get(reverse('event_workspace'), {'month': 'bad-input', 'day': '2099-02-31'})
        self.assertEqual(invalid.status_code, 200)
        self.assertIsNone(invalid.context['selected_day'])

    def test_quarters_use_saved_records_and_current_publication_states(self):
        item = AnnualObservance.objects.get(month=5)
        AnnualObservance.objects.filter(pk=item.pk).update(title='Reviewed May title', status='draft',
            published_at=None, published_by=None, published_by_label='')
        count = AnnualObservance.objects.count()
        for route in ('event_workspace', 'events:observances'):
            response = self.client.get(reverse(route))
            self.assertEqual(len(response.context['quarters']), 4)
            self.assertContains(response, 'Reviewed May title')
            self.assertContains(response, 'Third Thursday of May')
            self.assertContains(response, reverse('events:observance_edit', args=[item.pk]))
            self.assertEqual(response.context['observance_count'], 11)
        self.assertEqual(AnnualObservance.objects.count(), count)

    def test_events_and_observances_permissions_remain_separate(self):
        viewer = get_user_model().objects.create_user('synthetic_events_limited', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'events.view_event')
        self.client.force_login(viewer)
        response = self.client.get(reverse('event_workspace'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'National Autism Consciousness Week')
        self.assertNotContains(response, 'Create event')
        self.assertNotContains(response, 'event-capacity')
        self.assertEqual(self.client.get(reverse('events:observances')).status_code, 403)
        observer = get_user_model().objects.create_user('synthetic_observance_only', is_staff=True)
        grant(observer, 'accounts.access_dashboard', 'events.view_annualobservance')
        self.client.force_login(observer)
        response = self.client.get(reverse('event_workspace'))
        self.assertContains(response, 'National Autism Consciousness Week')
        self.assertNotContains(response, self.first.title)
        self.assertNotContains(response, 'data-event-filters')
        self.assertEqual(self.client.get(reverse('events:manage_list')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('event_workspace')).status_code, 302)

    def test_no_fake_readiness_and_no_public_or_other_workspace_asset_changes(self):
        before = EventLog.objects.count()
        response = self.client.get(reverse('event_workspace'))
        self.assertNotContains(response, 'Event readiness')
        self.assertNotContains(response, 'data-readiness="venue" checked')
        self.assertEqual(EventLog.objects.count(), before)
        for route in ('core:home', 'core:events', 'core:dashboard', 'program_portfolio', 'member_directory', 'membership:encode'):
            other = self.client.get(reverse(route))
            self.assertEqual(other.status_code, 200)
            self.assertNotContains(other, 'css/events-workspace.css')
            self.assertNotContains(other, 'js/events-workspace.js')

    def test_missing_observance_storage_and_capacity_are_explicit(self):
        with patch('events.workspace.observance_storage_ready', return_value=False):
            response = self.client.get(reverse('event_workspace'), {'q': self.draft.title})
        self.assertContains(response, 'Setup pending')
        self.assertNotContains(response, 'event-capacity')
        self.assertNotContains(response, 'National Autism Consciousness Week')
