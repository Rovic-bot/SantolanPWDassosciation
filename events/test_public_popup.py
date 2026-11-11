"""Event details are popups; old full-page links return to the public list."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event
from .tests import create_event


class PublicEventPopupTests(TestCase):
    def test_fragment_includes_public_details_and_escapes_editor_text(self):
        item = create_event(title='Community <script>event()</script>',
                            description='Public <b>description</b>', location='Community Hall')
        url = reverse('events:detail', args=[item.pk])
        response = self.client.get(url, {'popup': '1'})
        self.assertTemplateUsed(response, 'events/public_popup.html')
        self.assertContains(response, '&lt;script&gt;event()&lt;/script&gt;')
        self.assertContains(response, '&lt;b&gt;description&lt;/b&gt;')
        self.assertContains(response, 'Community Hall')
        self.assertContains(response, item.who_may_participate)
        self.assertNotContains(response, '<script>event()')
        self.assertNotContains(response, '<html')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertRedirects(self.client.get(url), reverse('core:events') + '#scheduled-events')
        self.assertEqual(self.client.head(url, {'popup': '1'}).status_code, 200)
        self.assertEqual(self.client.post(url + '?popup=1').status_code, 405)

    def test_old_detail_links_open_the_matching_events_list_without_a_detail_page(self):
        now = timezone.now()
        current = create_event()
        past = create_event(starts_at=now - timezone.timedelta(days=2),
                            ends_at=now - timezone.timedelta(days=1))
        for event, suffix in ((current, ''), (past, '?period=past')):
            with self.subTest(event=event.pk):
                url = reverse('events:detail', args=[event.pk])
                response = self.client.get(url)
                self.assertRedirects(response, reverse('core:events') + suffix + '#scheduled-events')
                self.assertIn('no-store', response['Cache-Control'])
                self.assertEqual(self.client.head(url).status_code, 302)
                self.assertEqual(self.client.post(url, {}).status_code, 405)
                Event.objects.filter(pk=event.pk).update(status='draft')
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_fragment_rechecks_publication_and_preserves_cancellation_notice(self):
        item = create_event()
        url = reverse('events:detail', args=[item.pk])
        for status, published_at, expected in (
            ('published', timezone.now(), 200),
            ('draft', timezone.now(), 404),
            ('archived', timezone.now(), 404),
            ('published', timezone.now() + timezone.timedelta(days=1), 404),
            ('cancelled', timezone.now(), 200),
        ):
            with self.subTest(status=status, published_at=published_at):
                Event.objects.filter(pk=item.pk).update(status=status, published_at=published_at)
                response = self.client.get(url, {'popup': '1'})
                self.assertEqual(response.status_code, expected)
                if status == 'cancelled':
                    self.assertContains(response, 'This event has been cancelled.')
                if expected == 404:
                    self.assertNotContains(response, item.title, status_code=404)

    def test_image_uses_the_permission_checked_endpoint_and_accessible_fallback(self):
        item = create_event(image='events/synthetic-private-path.png', image_alt='')
        response = self.client.get(reverse('events:detail', args=[item.pk]), {'popup': '1'})
        self.assertContains(response, reverse('events:image', args=[item.pk]))
        self.assertContains(response, 'alt="Event image for Community gathering"')
        self.assertNotContains(response, item.image.name)
