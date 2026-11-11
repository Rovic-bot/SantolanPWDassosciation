"""Scheduled events publish in one click, with automatic audit text."""
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from membership.tests import grant
from .models import Event
from .services import change_publication, publish_event, save_event
from .tests import event_data


class SimpleEventPublicationTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.admin = get_user_model().objects.create_superuser('simple_event_admin')
        self.item = save_event(user=self.admin, data=event_data())
        self.url = reverse('events:manage_detail', args=[self.item.pk])
        self.client.force_login(self.admin)

    def publish(self):
        return publish_event(self.item.pk, user=self.admin, version=self.item.version)

    def test_publish_form_has_only_version_and_one_publish_button(self):
        response = self.client.get(self.url)
        html = response.content.decode().split('id="publish-event-form"', 1)[1].split('</form>', 1)[0]
        self.assertIn('name="version"', html)
        self.assertIn('value="published">Publish event</button>', html)
        for removed in ('name="notes"', 'name="confirm"', '<select'):
            self.assertNotIn(removed, html)
        self.assertNotIn('published', dict(response.context['form'].fields['action'].choices))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'draft')
        self.assertEqual(self.item.history.count(), 1)

    def test_http_button_publishes_without_reason_or_checkbox_and_records_audit(self):
        response = self.client.post(self.url, {'action': 'published', 'version': self.item.version})
        self.assertRedirects(response, self.url)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'published')
        self.assertEqual(self.item.version, 2)
        self.assertIsNotNone(self.item.published_at)
        audit = self.item.history.get(action='published')
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.notes, 'Published from the event review.')
        self.assertEqual(audit.changes['status'], {'before': 'draft', 'after': 'published'})
        self.assertContains(self.client.get(reverse('events:detail', args=[self.item.pk]), {'popup': '1'}), self.item.title)
        self.assertNotContains(self.client.get(self.url), 'id="publish-event-form"')

    def test_publication_generates_reason_and_other_actions_still_require_one(self):
        self.item = self.publish()
        for action in ('draft', 'cancelled', 'archived'):
            with self.subTest(action=action), self.assertRaisesMessage(ValidationError, 'Provide a reason'):
                change_publication(self.item.pk, user=self.admin, version=self.item.version, action=action, notes='')
        self.assertEqual(self.item.history.count(), 2)

    def test_missing_or_invalid_version_and_double_click_cannot_republish(self):
        for version in (None, '', '-1', 'invalid'):
            payload = {'action': 'published'}
            if version is not None:
                payload['version'] = version
            self.assertEqual(self.client.post(self.url, payload).status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.version), ('draft', 1))
        self.publish()
        response = self.client.post(self.url, {'action': 'published', 'version': 1})
        self.assertContains(response, 'Reload the page')
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 2)
        self.assertEqual(self.item.history.count(), 2)

    def test_permission_and_csrf_requirements_remain(self):
        viewer = get_user_model().objects.create_user('simple_event_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'events.view_event')
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url), 'id="publish-event-form"')
        self.assertEqual(self.client.post(self.url, {'action': 'published', 'version': 1}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            publish_event(self.item.pk, user=viewer, version=1)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.url, {'action': 'published', 'version': 1}).status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'draft')

    def test_older_uncategorized_draft_publishes_without_hidden_category_requirement(self):
        Event.objects.filter(pk=self.item.pk).update(event_category='')
        response = self.client.post(self.url, {'action': 'published', 'version': self.item.version})
        self.assertRedirects(response, self.url)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'published')
        self.assertEqual(self.item.event_category, '')
        self.assertEqual(self.item.history.count(), 2)
        self.assertContains(self.client.get(reverse('core:events')), self.item.title)

    def test_missing_photo_and_audit_failure_leave_draft_intact(self):
        item = save_event(user=self.admin, data=event_data(image_alt='Event poster'),
            files=MultiValueDict({'image': [image_upload()]}))
        item.image.storage.delete(item.image.name)
        with self.assertRaisesMessage(ValidationError, 'missing image'):
            publish_event(item.pk, user=self.admin, version=item.version)
        with patch('events.services.record_log', side_effect=RuntimeError('Audit failure')):
            with self.assertRaises(RuntimeError):
                self.publish()
        self.item.refresh_from_db()
        item.refresh_from_db()
        for entry in (self.item, item):
            self.assertEqual((entry.status, entry.version), ('draft', 1))
            self.assertIsNone(entry.published_at)
            self.assertEqual(entry.history.count(), 1)

    def test_other_actions_still_require_reason_and_confirmation(self):
        self.item = self.publish()
        for data in ({'notes': 'Withdraw temporarily'}, {'confirm': 'on'}):
            response = self.client.post(self.url, {'action': 'draft', 'version': self.item.version, **data})
            self.assertEqual(response.status_code, 200)
            self.item.refresh_from_db()
            self.assertEqual(self.item.status, 'published')
        response = self.client.post(self.url, {'action': 'draft', 'version': self.item.version,
            'notes': 'Withdraw temporarily', 'confirm': 'on'})
        self.assertRedirects(response, self.url)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'draft')

    def test_unpublish_buttons_open_a_reasoned_review_and_remove_public_visibility(self):
        self.item = self.publish()
        published_at = self.item.published_at
        history_before = list(self.item.history.values())
        target = self.url + '?action=draft#event-status-form'
        for url in (self.url, reverse('events:manage_list')):
            self.assertContains(self.client.get(url), target)
        review = self.client.get(self.url, {'action': 'draft'})
        self.assertTrue(review.context['unpublishing'])
        self.assertEqual(review.context['form'].initial['action'], 'draft')
        self.assertContains(review, 'I confirm this event should be unpublished.')
        self.assertTrue(review.context['form'].fields['action'].widget.is_hidden)
        self.assertEqual(list(self.item.history.values()), history_before)
        response = self.client.post(self.url, {'action': 'draft', 'version': self.item.version,
            'notes': 'Synthetic schedule needs another review.', 'confirm': 'on'})
        self.assertRedirects(response, self.url)
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.published_at), ('draft', published_at))
        log = self.item.history.get(action='draft')
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.notes, 'Synthetic schedule needs another review.')
        self.assertEqual(log.changes['status'], {'before': 'published', 'after': 'draft'})
        self.assertNotContains(self.client.get(reverse('core:events')), self.item.title)
        self.assertEqual(self.client.get(reverse('events:detail', args=[self.item.pk]), {'popup': '1'}).status_code, 404)
        self.assertNotContains(self.client.get(self.url), target)
        self.assertContains(self.client.get(self.url), 'Publish event')

    def test_unpublish_permission_stale_version_csrf_and_audit_rollback_remain_enforced(self):
        self.item = self.publish()
        payload = {'action': 'draft', 'version': self.item.version, 'notes': 'Synthetic withdrawal.', 'confirm': 'on'}
        viewer = get_user_model().objects.create_user('unpublish_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'events.view_event')
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url), 'Unpublish event')
        self.assertEqual(self.client.post(self.url, payload).status_code, 403)
        self.client.force_login(self.admin)
        stale = self.client.post(self.url, {**payload, 'version': self.item.version - 1})
        self.assertContains(stale, 'Reload the page')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.url, payload).status_code, 403)
        with patch('events.services.record_log', side_effect=RuntimeError('Audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'published')
        self.assertFalse(self.item.history.filter(action='draft').exists())


class SimpleEventPublicationConcurrencyTests(TransactionTestCase):
    def test_concurrent_publish_accepts_one_current_version(self):
        user = get_user_model().objects.create_superuser('event_publish_concurrent')
        item = save_event(user=user, data=event_data())
        barrier = Barrier(2)

        def publish(_):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                try:
                    publish_event(item.pk, user=actor, version=item.version)
                    return 'published'
                except ValidationError:
                    return 'stale'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, range(2)))
        self.assertCountEqual(results, ['published', 'stale'])
        item.refresh_from_db()
        self.assertEqual((item.status, item.version), ('published', 2))
        self.assertEqual(item.history.count(), 2)
