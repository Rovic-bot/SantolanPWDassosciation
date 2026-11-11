from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from membership.tests import grant
from .models import AnnualObservance, AnnualObservanceRevision, AnnualObservanceLog, Event
from .observances import REFERENCE_CATALOGUE
from .services import save_observance, change_observance_publication, public_observance_calendar
from .tests import create_event


def draft_data(**changes):
    return {**asdict(REFERENCE_CATALOGUE[0]), 'title': 'Fictional awareness card',
            'target_audience': 'Fictional disability awareness audience',
            'who_may_participate': 'Everyone welcome under the organizer rules.',
            'version': 0, 'notes': 'Fictional review reason', 'image_alt': '', **changes}


class ObservanceWorkflowTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.admin = get_user_model().objects.create_superuser('fictional_observance_workflow')
        self.editor = get_user_model().objects.create_user('fictional_editor', is_staff=True)
        grant(self.editor, 'accounts.access_dashboard', 'events.view_annualobservance',
              'events.add_annualobservance', 'events.change_annualobservance')
        self.viewer = get_user_model().objects.create_user('fictional_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'events.view_annualobservance')

    def create(self, photo=False, **changes):
        return save_observance(user=self.admin, data=draft_data(image_alt='Fictional accessible poster' if photo else '', **changes),
            files=MultiValueDict({'image': [image_upload()]}) if photo else None)

    def publish(self, item, **changes):
        return change_observance_publication(item.pk, user=self.admin, version=item.version,
            action='published', notes='Fictional reviewed publication', **changes)

    def test_create_is_draft_ignores_forged_metadata_and_has_atomic_history(self):
        item = self.create(status='published', created_by=self.viewer.pk, published_at=timezone.now())
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.version, 1)
        self.assertEqual(item.created_by, self.admin)
        self.assertIsNone(item.published_at)
        self.assertEqual(item.recurrence_rule, 'Third week of January')
        self.assertEqual(item.revisions.count(), 1)
        self.assertEqual(item.history.count(), 1)
        self.assertEqual(item.history.get().revision, item.revisions.get())
        self.assertEqual(Event.objects.count(), 0)

    def test_service_rbac_for_create_edit_and_publish(self):
        item = self.create()
        for user in (AnonymousUser(), self.viewer):
            with self.subTest(user=str(user)), self.assertRaises(PermissionDenied):
                save_observance(user=user, data=draft_data())
        with self.assertRaises(PermissionDenied):
            save_observance(user=self.viewer, pk=item.pk, data=draft_data(version=1))
        with self.assertRaises(PermissionDenied):
            change_observance_publication(item.pk, user=self.editor, version=1, action='published', notes='Forbidden')
        self.assertEqual(item.history.count(), 1)

    def test_service_rechecks_revoked_permissions_even_with_cached_actor(self):
        self.assertTrue(self.editor.has_perm('events.add_annualobservance'))
        self.editor.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            save_observance(user=self.editor, data=draft_data())
        get_user_model().objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            save_observance(user=self.admin, data=draft_data())

    def test_publish_withdraw_edit_republish_archive_retains_versions(self):
        item = self.create(photo=True)
        item = self.publish(item)
        self.assertEqual(item.published_by, self.admin)
        response = self.client.get(reverse('core:events'))
        self.assertContains(response, item.title)
        self.assertNotContains(response, 'No annual observances have been published yet.')
        for private in ('Fictional reviewed publication', self.admin.username, 'annual-observances/'):
            self.assertNotContains(response, private)
        with self.assertRaises(ValidationError):
            save_observance(user=self.admin, pk=item.pk, data=draft_data(version=item.version))
        item = change_observance_publication(item.pk, user=self.admin, version=2, action='draft', notes='Withdraw')
        self.assertIsNone(item.published_at)
        self.assertIsNone(item.published_by)
        self.assertNotContains(self.client.get(reverse('core:events')), item.title)
        item = save_observance(user=self.editor, pk=item.pk, data=draft_data(version=3,
            title='Fictional updated card', image_alt=item.image_alt))
        item = self.publish(item)
        item = change_observance_publication(item.pk, user=self.admin, version=5, action='archived', notes='Archive')
        self.assertEqual(list(item.revisions.values_list('version', flat=True)), [6, 5, 4, 3, 2, 1])
        self.assertEqual(item.history.count(), 6)
        self.assertNotContains(self.client.get(reverse('core:events')), item.title)
        with self.assertRaises(ValidationError):
            self.publish(item)

    def test_stale_edit_and_publication_leave_no_partial_history(self):
        item = self.create()
        save_observance(user=self.admin, pk=item.pk, data=draft_data(version=1, description='Updated fictional text'))
        with self.assertRaises(ValidationError):
            save_observance(user=self.admin, pk=item.pk, data=draft_data(version=1, title='Stale'))
        with self.assertRaises(ValidationError):
            self.publish(item)
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        self.assertEqual(item.title, 'Fictional awareness card')
        self.assertEqual(item.history.count(), 2)

    def test_audit_failure_rolls_back_create_and_new_photo(self):
        with patch('events.models.AnnualObservanceLog.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.create(photo=True)
        self.assertEqual(AnnualObservance.objects.count(), 0)
        self.assertEqual(AnnualObservanceRevision.objects.count(), 0)
        self.assertEqual(list(Path(self.media.name).rglob('*.png')), [])

    def test_audit_failure_rolls_back_publish(self):
        item = self.create()
        with patch('events.models.AnnualObservanceLog.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.publish(item)
        item.refresh_from_db()
        self.assertEqual((item.status, item.version), ('draft', 1))
        self.assertEqual(item.revisions.count(), 1)

    def test_revision_failure_rolls_back_edit(self):
        item = self.create()
        with patch('events.models.AnnualObservanceRevision.objects.create', side_effect=RuntimeError('revision unavailable')):
            with self.assertRaises(RuntimeError):
                save_observance(user=self.admin, pk=item.pk, data=draft_data(version=1, title='Uncommitted'))
        item.refresh_from_db()
        self.assertEqual(item.title, 'Fictional awareness card')
        self.assertEqual(item.history.count(), 1)

    def test_photo_replace_remove_keeps_history_and_original_bytes(self):
        item = self.create(photo=True)
        original = item.image.name
        original_bytes = Path(self.media.name, original).read_bytes()
        item = save_observance(user=self.admin, pk=item.pk, data=draft_data(version=1, image_alt='Replacement photo'),
            files=MultiValueDict({'image': [image_upload()]}))
        replacement = item.image.name
        self.assertNotEqual(original, replacement)
        item = save_observance(user=self.admin, pk=item.pk, data=draft_data(version=2, remove_image=True))
        self.assertFalse(item.image)
        self.assertEqual(item.image_alt, '')
        self.assertEqual(Path(self.media.name, original).read_bytes(), original_bytes)
        self.assertTrue(Path(self.media.name, replacement).exists())
        self.assertEqual(item.revisions.get(version=1).image.name, original)
        self.assertEqual(item.revisions.get(version=2).image.name, replacement)

    def test_failed_photo_replacement_preserves_old_photo_and_cleans_new_file(self):
        item = self.create(photo=True)
        before = set(Path(self.media.name).rglob('*.png'))
        with patch('events.models.AnnualObservanceLog.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                save_observance(user=self.admin, pk=item.pk, data=draft_data(version=1, image_alt='Replacement'),
                    files=MultiValueDict({'image': [image_upload()]}))
        self.assertEqual(set(Path(self.media.name).rglob('*.png')), before)
        item.refresh_from_db()
        self.assertEqual(item.version, 1)

    def test_invalid_upload_missing_alt_limits_and_conflicting_removal(self):
        for photo, changes in ((SimpleUploadedFile('fake.png', b'not png', content_type='image/png'), {}),
                               (image_upload(), {'image_alt': ''}),
                               (image_upload(), {'remove_image': True})):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                save_observance(user=self.admin, data=draft_data(image_alt='Safe alt', **{k:v for k,v in changes.items() if k!='image_alt'}) if 'image_alt' not in changes else draft_data(**changes),
                    files=MultiValueDict({'image': [photo]}))
        with override_settings(EVENT_IMAGE_MAX_BYTES=1), self.assertRaises(ValidationError):
            self.create(photo=True)
        with override_settings(EVENT_IMAGE_MAX_PIXELS=1), self.assertRaises(ValidationError):
            self.create(photo=True)
        self.assertEqual(AnnualObservance.objects.count(), 0)

    def test_source_url_and_recurrence_are_validated_on_save_and_publication(self):
        for changes in ({'source_url': 'https://ncda.gov.ph.evil.example/source'},
                        {'day_start': 15}, {'month': 13}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
        item = self.create()
        AnnualObservance.objects.filter(pk=item.pk).update(source_url='javascript:alert(1)')
        with self.assertRaises(ValidationError):
            self.publish(item)
        self.assertEqual(item.revisions.count(), 1)

    def test_missing_photo_blocks_publication(self):
        item = self.create(photo=True)
        item.image.storage.delete(item.image.name)
        with self.assertRaises(ValidationError):
            self.publish(item)

    def test_photo_routes_enforce_current_publication_and_private_history(self):
        item = self.create(photo=True)
        public = reverse('events:observance_image', args=[item.pk])
        preview = reverse('events:observance_preview_image', args=[item.pk])
        history = reverse('events:observance_revision_image', args=[item.pk, item.revisions.get().pk])
        self.assertEqual(self.client.get(public).status_code, 404)
        self.assertEqual(self.client.get(preview).status_code, 302)
        item = self.publish(item)
        response = self.client.get(public)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('no-store', response['Cache-Control'])
        b''.join(response.streaming_content)
        self.client.force_login(self.viewer)
        response = self.client.get(preview)
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        self.assertEqual(self.client.get(history).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(history)
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        change_observance_publication(item.pk, user=self.admin, version=item.version, action='draft', notes='Withdraw')
        self.client.logout()
        self.assertEqual(self.client.get(public).status_code, 404)

    def test_future_publication_is_private(self):
        item = self.publish(self.create(photo=True))
        AnnualObservance.objects.filter(pk=item.pk).update(published_at=timezone.now()+timezone.timedelta(days=1))
        self.assertFalse(any(m['observances'] for m in public_observance_calendar()))
        self.assertEqual(self.client.get(reverse('events:observance_image', args=[item.pk])).status_code, 404)

    def test_immutable_revisions_and_logs_and_protected_aggregate(self):
        item = self.create()
        for record in (item.revisions.get(), item.history.get()):
            with self.assertRaises(ValidationError):
                record.save()
            with self.assertRaises(ValidationError):
                record.delete()
            with self.assertRaises(ValidationError):
                type(record).objects.filter(pk=record.pk).update(reason='Tamper')
            with self.assertRaises(ValidationError):
                type(record).objects.filter(pk=record.pk).delete()
        with self.assertRaises(ProtectedError):
            item.delete()
        with self.assertRaises(ProtectedError):
            self.admin.delete()

    def test_detail_history_permissions_and_published_edit_link(self):
        item = self.publish(self.create())
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('events:observance_detail', args=[item.pk]))
        self.assertContains(response, 'Card preview')
        self.assertNotContains(response, 'Revision history')
        self.assertNotContains(response, 'Audit records')
        self.assertNotContains(response, 'Apply publication change')
        self.assertNotContains(response, 'Edit observance')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('events:observance_detail', args=[item.pk]))
        self.assertContains(response, 'Revision history')
        self.assertContains(response, 'Audit records')
        self.assertContains(response, 'Edit observance')

    def test_reference_get_prefills_only_and_http_create_requires_csrf(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('events:observance_create')+'?reference=1')
        self.assertContains(response, 'National Autism Consciousness Week')
        self.assertEqual(AnnualObservance.objects.count(), 0)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.editor)
        payload = {key: value for key, value in draft_data().items() if value is not None}
        self.assertEqual(csrf.post(reverse('events:observance_create'), payload).status_code, 403)
        response = self.client.post(reverse('events:observance_create'), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AnnualObservance.objects.get().status, 'draft')

    def test_publication_requires_confirmation_and_permission(self):
        item = self.create()
        self.client.force_login(self.admin)
        url = reverse('events:observance_detail', args=[item.pk])
        self.assertEqual(self.client.post(url, {'version': 1, 'action': 'published', 'notes': 'Reason'}).status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')
        self.client.force_login(self.editor)
        self.assertEqual(self.client.post(url, {'version': 1, 'action': 'published', 'notes': 'Reason', 'confirm': 'on'}).status_code, 403)

    def test_database_constraints_reject_invalid_month_and_recurrence_shape(self):
        item = self.create()
        for changes in ({'month': 13}, {'day_start': 15}, {'status': 'published'}, {'category': 'invented'}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                AnnualObservance.objects.filter(pk=item.pk).update(**changes)

    def test_unapplied_storage_fails_closed_for_public_and_private_routes(self):
        item = self.create()
        self.client.force_login(self.admin)
        with patch('events.services.observance_storage_ready', return_value=False):
            self.assertContains(self.client.get(reverse('events:observances')), 'Setup pending')
            self.assertEqual(self.client.get(reverse('events:observance_create')).status_code, 503)
            self.assertEqual(self.client.get(reverse('events:observance_detail', args=[item.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse('events:observance_preview_image', args=[item.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse('events:observance_image', args=[item.pk])).status_code, 404)
            self.assertNotContains(self.client.get(reverse('core:events')), item.title)


class ObservanceConcurrencyTests(TransactionTestCase):
    def test_concurrent_edits_serialize_and_one_stale_writer_is_rejected(self):
        user = get_user_model().objects.create_superuser('fictional_concurrent')
        item = save_observance(user=user, data=draft_data())
        barrier = Barrier(2)

        def edit(title):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=15)
                try:
                    save_observance(user=actor, pk=item.pk, data=draft_data(version=1, title=title))
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ['Fictional A', 'Fictional B']))
        self.assertCountEqual(results, ['saved', 'stale'])
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        self.assertEqual(item.revisions.count(), 2)
        self.assertEqual(item.history.count(), 2)


class ObservanceMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_existing_event_and_creates_no_observances(self):
        event = create_event(title='Fictional migration preservation')
        old = {field.attname: getattr(event, field.attname) for field in Event._meta.fields}
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('ewaf', '0004_scoring_diagnostics')])
            MigrationExecutor(connection).migrate([('events', '0005_revised_seventy_workflow')])
            self.assertNotIn('events_annualobservance', connection.introspection.table_names())
            response = self.client.get(reverse('core:events'))
            self.assertNotContains(response, event.title)
            self.assertContains(response, 'No published observances for this month.')
            executor = MigrationExecutor(connection)
            self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in
                executor.migration_plan([('events', '0006_annual_observances')])],
                [('events', '0006_annual_observances', False)])
            executor.migrate([('events', '0006_annual_observances')])
            self.assertNotIn(('ewaf', '0005_durable_development'),
                             MigrationExecutor(connection).loader.applied_migrations)
            event.refresh_from_db()
            self.assertEqual({field.attname: getattr(event, field.attname) for field in Event._meta.fields}, old)
            self.assertEqual(AnnualObservance.objects.count(), 0)
            self.assertEqual(AnnualObservanceRevision.objects.count(), 0)
            self.assertEqual(AnnualObservanceLog.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(leaves)
