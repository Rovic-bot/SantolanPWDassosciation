from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from membership.tests import grant
from .services import save_event
from .tests import event_data


class EventListActionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('list_event_admin')
        self.item = save_event(user=self.admin, data=event_data())
        self.list_url = reverse('events:manage_list')
        self.detail_url = reverse('events:manage_detail', args=[self.item.pk])
        self.client.force_login(self.admin)

    def test_agenda_links_to_full_details_and_retains_publication_action(self):
        self.item = save_event(user=self.admin, pk=self.item.pk,
            data=event_data(version=self.item.version, description='<script>alert(1)</script>'))
        response = self.client.get(self.list_url)
        self.assertContains(response, 'class="event-card-actions"')
        self.assertContains(response, f'href="{self.detail_url}"')
        self.assertNotContains(response, 'data-bs-toggle="modal"')
        self.assertContains(response, 'name="return_to" value="list"')
        detail = self.client.get(self.detail_url)
        self.assertContains(detail, 'data-event-profile')
        for label in ('Event overview', 'Event schedule', 'Event starts', 'Event ends', 'Venue', 'Event image', 'Event history'):
            self.assertContains(detail, label)
        self.assertContains(detail, self.item.location)
        self.assertContains(detail, 'No event image uploaded.')
        self.assertContains(detail, self.item.target_audience)
        self.assertContains(detail, self.item.who_may_participate)
        self.assertContains(detail, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'Reviewed correction.')
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'draft')

    def test_publish_from_row_returns_to_list_and_removes_publish_action(self):
        response = self.client.post(self.detail_url,
            {'action': 'published', 'version': self.item.version, 'return_to': 'list'}, follow=True)
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, 'Event published.')
        self.assertNotContains(response, 'aria-label="Publish event:')
        self.assertContains(response, f'aria-label="Manage {self.item.title}"')
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'published')
        self.assertEqual(self.item.history.filter(action='published').count(), 1)
        response = self.client.post(self.detail_url,
            {'action': 'published', 'version': 1, 'return_to': 'list'}, follow=True)
        self.assertRedirects(response, self.list_url)
        self.assertContains(response, 'Reload the page')
        self.assertEqual(self.item.history.filter(action='published').count(), 1)

    def test_invalid_row_publication_returns_errors_to_list_without_writing(self):
        for version in (0, 'invalid'):
            response = self.client.post(self.detail_url,
                {'action': 'published', 'version': version, 'return_to': 'list'}, follow=True)
            self.assertRedirects(response, self.list_url)
            self.assertContains(response, 'Reload the page' if isinstance(version, int)
                else 'Enter a whole number.')
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.version), ('draft', 1))
        self.assertEqual(self.item.history.count(), 1)

    def test_viewer_can_open_details_but_cannot_publish_from_the_row(self):
        viewer = get_user_model().objects.create_user('list_event_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'events.view_event')
        self.client.force_login(viewer)
        response = self.client.get(self.list_url)
        self.assertContains(response, f'href="{self.detail_url}"')
        self.assertContains(self.client.get(self.detail_url), self.item.description)
        self.assertNotContains(response, 'aria-label="Publish event:')
        self.assertNotContains(response, 'Edit event')
        self.assertEqual(self.client.post(self.detail_url,
            {'action': 'published', 'version': self.item.version, 'return_to': 'list'}).status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'draft')
