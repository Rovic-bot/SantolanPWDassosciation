"""Direct calendar editing publishes atomically with the existing access controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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
from .models import AnnualObservance
from .services import change_observance_publication, save_observance
from .test_observance_workflow import draft_data


class ObservanceUpdateTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.media = Path(media.name)
        override = override_settings(MEDIA_ROOT=media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.admin = get_user_model().objects.create_superuser('calendar_update_admin')
        self.item = save_observance(user=self.admin, data=draft_data())
        self.item = change_observance_publication(self.item.pk, user=self.admin,
            version=self.item.version, action='published', notes='Initial reviewed publication.')
        self.url = reverse('events:observance_edit', args=[self.item.pk])

    def update(self, **changes):
        return save_observance(user=self.admin, pk=self.item.pk, publish=True,
            data=draft_data(version=self.item.version, **changes))

    def test_edit_publishes_once_and_preserves_original_published_revision(self):
        original = self.item.revisions.get(version=2)
        item = self.update(title='Updated annual observance', status='draft',
            published_by_label='Forged actor')
        self.assertEqual((item.title, item.status, item.version), ('Updated annual observance', 'published', 3))
        self.assertEqual(item.published_by, self.admin)
        self.assertEqual(item.published_by_label, self.admin.username)
        self.assertGreaterEqual(item.published_at, original.published_at)
        original.refresh_from_db()
        self.assertEqual(original.title, 'Fictional awareness card')
        self.assertEqual(original.status, 'published')
        self.assertEqual(item.revisions.count(), 3)
        log = item.history.get(version=3)
        self.assertEqual(log.changes['title']['after'], item.title)
        self.assertEqual(log.actor, self.admin)
        self.assertContains(self.client.get(reverse('events:observance_public_detail', args=[item.pk])), item.title)

    def test_draft_can_be_updated_and_published_but_archived_requires_restoration(self):
        self.item = change_observance_publication(self.item.pk, user=self.admin,
            version=self.item.version, action='draft', notes='Withdraw temporarily.')
        self.item = self.update(title='Reviewed draft update')
        self.assertEqual(self.item.status, 'published')
        self.item = change_observance_publication(self.item.pk, user=self.admin,
            version=self.item.version, action='archived', notes='Archive this entry.')
        with self.assertRaises(ValidationError):
            self.update()
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(self.url), reverse('events:observance_detail', args=[self.item.pk]))

    def test_publish_requires_both_change_and_publication_permissions(self):
        for permission in ('events.change_annualobservance', 'events.publish_annualobservance'):
            actor = get_user_model().objects.create_user(permission.split('.')[1], is_staff=True)
            grant(actor, 'accounts.access_dashboard', 'events.view_annualobservance', permission)
            with self.subTest(permission=permission), self.assertRaises(PermissionDenied):
                save_observance(user=actor, pk=self.item.pk, publish=True,
                    data=draft_data(version=self.item.version))
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 2)

    def test_stale_submission_does_not_overwrite_published_changes(self):
        self.update(title='First editor change')
        with self.assertRaisesMessage(ValidationError, 'Reload the page'):
            self.update(title='Stale editor change')
        self.item.refresh_from_db()
        self.assertEqual((self.item.title, self.item.version), ('First editor change', 3))
        self.assertEqual(self.item.history.count(), 3)

    def test_invalid_details_leave_current_publication_and_history_unchanged(self):
        for changes in ({'who_may_participate': ''}, {'source_url': 'https://invalid.example/source'},
                        {'notes': ''}, {'day_start': 15}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.update(**changes)
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.version), ('published', 2))
        self.assertEqual(self.item.revisions.count(), 2)

    def test_audit_failure_rolls_back_update_and_removes_new_photo(self):
        with patch('events.models.AnnualObservanceLog.objects.create', side_effect=RuntimeError('Audit failure')):
            with self.assertRaises(RuntimeError):
                save_observance(user=self.admin, pk=self.item.pk, publish=True,
                    data=draft_data(version=self.item.version, title='Failed update', image_alt='Accessible poster'),
                    files=MultiValueDict({'image': [image_upload()]}))
        self.item.refresh_from_db()
        self.assertEqual((self.item.title, self.item.status, self.item.version), ('Fictional awareness card', 'published', 2))
        self.assertFalse(list(self.media.rglob('*.png')))
        self.assertEqual(self.item.revisions.count(), 2)
        self.assertEqual(self.item.history.count(), 2)

    def test_photo_replacement_keeps_history_and_missing_photo_blocks_update(self):
        self.item = save_observance(user=self.admin, pk=self.item.pk, publish=True,
            data=draft_data(version=self.item.version, image_alt='Original poster'),
            files=MultiValueDict({'image': [image_upload()]}))
        old_name = self.item.image.name
        self.item = save_observance(user=self.admin, pk=self.item.pk, publish=True,
            data=draft_data(version=self.item.version, image_alt='Replacement poster'),
            files=MultiValueDict({'image': [image_upload()]}))
        self.assertNotEqual(self.item.image.name, old_name)
        self.assertTrue(self.item.image.storage.exists(old_name))
        self.assertEqual(self.item.revisions.get(version=3).image.name, old_name)
        self.item.image.storage.delete(self.item.image.name)
        with self.assertRaisesMessage(ValidationError, 'missing photo'):
            self.update(image_alt='Replacement poster')
        self.item = self.update(remove_image=True)
        self.assertFalse(self.item.image)
        self.assertEqual(self.item.status, 'published')

    def payload(self, **changes):
        return {key: value for key, value in draft_data(version=self.item.version, **changes).items()
                if value is not None}

    def test_admin_list_opens_editor_and_offers_event_creation_without_reference_controls(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('events:observances'))
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, f'href="{reverse("events:create")}"')
        for removed in ('Annual calendar reference', 'Verified annual references', 'Create observance',
                        'Manage scheduled General and Specific Events'):
            self.assertNotContains(response, removed)
        response = self.client.get(self.url)
        self.assertContains(response, 'Save and publish')
        self.assertNotContains(response, 'Save draft')
        for field in ('target_audience', 'who_may_participate'):
            self.assertTrue(response.context['form'].fields[field].required)
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 2)
        self.assertEqual(AnnualObservance.objects.count(), 1)

    def test_http_save_publishes_and_returns_to_calendar(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self.payload(title='Updated from the calendar'))
        self.assertRedirects(response, reverse('events:observances'))
        self.item.refresh_from_db()
        self.assertEqual((self.item.title, self.item.status, self.item.version), ('Updated from the calendar', 'published', 3))
        self.assertContains(self.client.get(reverse('core:events')), self.item.title)
        response = self.client.post(self.url, {**self.payload(), 'version': 2})
        self.assertContains(response, 'Reload the page')
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 3)

    def test_http_update_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, self.payload()).status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 2)


class ObservanceUpdateConcurrencyTests(TransactionTestCase):
    def test_two_public_updates_accept_only_one_editor_version(self):
        user = get_user_model().objects.create_superuser('calendar_concurrent_admin')
        item = save_observance(user=user, data=draft_data(), publish=True)
        barrier = Barrier(2)

        def update(title):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                try:
                    save_observance(user=actor, pk=item.pk, publish=True,
                        data=draft_data(version=item.version, title=title))
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ['First update', 'Second update']))
        self.assertCountEqual(results, ['saved', 'stale'])
        item.refresh_from_db()
        self.assertEqual((item.status, item.version), ('published', 2))
        self.assertEqual(item.revisions.count(), 2)
        self.assertEqual(item.history.count(), 2)
