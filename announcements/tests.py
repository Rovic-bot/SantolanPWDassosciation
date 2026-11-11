from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from membership.tests import grant
from .forms import AnnouncementForm
from .models import Announcement
from .services import change_publication, save_announcement


def image_upload():
    output = BytesIO()
    Image.new('RGB', (80, 60), '#176e65').save(output, format='PNG')
    return SimpleUploadedFile('notice.png', output.getvalue(), content_type='image/png')


class AnnouncementTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.admin = get_user_model().objects.create_superuser('publisher', password='test-only-password')
        self.editor = get_user_model().objects.create_user('editor', is_staff=True)
        grant(self.editor, 'accounts.access_dashboard', 'announcements.view_announcement',
              'announcements.add_announcement', 'announcements.change_announcement')
        self.data = {'category': 'general', 'source_office': 'Santolan PWD Association', 'title': 'Community notice', 'content': 'A real notice.\n\nSecond paragraph.',
                     'image_alt': '', 'version': 0}
        self.client.force_login(self.admin)

    def draft(self, image=False):
        return save_announcement(user=self.admin, data={**self.data, 'image_alt': 'Notice illustration' if image else ''},
            files=MultiValueDict({'image': [image_upload()]}) if image else None)

    def change(self, item, action):
        return change_publication(item.pk, user=self.admin, version=item.version, action=action)

    def test_create_is_draft_even_when_post_forges_published_status(self):
        response = self.client.post(reverse('announcements:create'), {**self.data, 'status': 'published', 'created_by': self.editor.pk})
        item = Announcement.objects.get()
        self.assertRedirects(response, reverse('announcements:manage_detail', args=[item.pk]))
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.created_by, self.admin)
        self.assertIsNone(item.published_at)
        self.assertEqual(item.events.get().action, 'created')

    def test_public_visibility_tracks_publish_withdraw_archive_delete(self):
        item = self.draft(image=True)
        routes = [reverse('announcements:detail', args=[item.pk]), reverse('announcements:image', args=[item.pk])]
        for action in [None, 'published', 'draft', 'published', 'archived', 'published', 'deleted']:
            if action:
                item = self.change(item, action)
            visible = item.status == 'published'
            for url in routes:
                response = Client().get(url)
                self.assertEqual(response.status_code, 200 if visible else 404)
                if response.streaming:
                    b''.join(response.streaming_content)
                if visible:
                    self.assertIn('no-store', response['Cache-Control'])
            for url in [reverse('core:home'), reverse('core:announcements')]:
                response = Client().get(url)
                (self.assertContains if visible else self.assertNotContains)(response, item.title)
        self.assertEqual(Announcement.objects.count(), 1)
        self.assertEqual(item.events.count(), 7)
        with self.assertRaises(ValidationError):
            self.change(item, 'published')

    def test_future_publication_timestamp_does_not_leak_content(self):
        item = self.draft()
        Announcement.objects.filter(pk=item.pk).update(status='published', published_at=timezone.now()+timedelta(days=1))
        self.assertNotContains(Client().get(reverse('core:announcements')), item.title)
        self.assertEqual(Client().get(reverse('announcements:detail', args=[item.pk])).status_code, 404)

    def test_editor_can_create_edit_draft_but_cannot_publish_or_edit_live(self):
        item = self.draft()
        self.client.force_login(self.editor)
        edit_url = reverse('announcements:edit', args=[item.pk])
        detail_url = reverse('announcements:manage_detail', args=[item.pk])
        self.assertEqual(self.client.post(edit_url, {**self.data, 'version': item.version}).status_code, 302)
        self.assertEqual(self.client.post(detail_url, {'version': 2, 'action': 'published', 'confirm': 'on'}).status_code, 403)
        item.refresh_from_db()
        item = self.change(item, 'published')
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.post(edit_url, {**self.data, 'version': item.version}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_announcement(user=self.editor, pk=item.pk, data={**self.data, 'version': item.version})

    def test_publish_and_delete_permissions_are_separate(self):
        grant(self.editor, 'announcements.publish_announcement')
        self.client.force_login(self.editor)
        item = self.draft()
        url = reverse('announcements:manage_detail', args=[item.pk])
        self.assertEqual(self.client.post(url, {'version': item.version, 'action': 'published', 'confirm': 'on'}).status_code, 302)
        self.assertEqual(self.client.post(url, {'version': 2, 'action': 'deleted', 'confirm': 'on'}).status_code, 403)

    def test_private_routes_and_services_enforce_staff_and_permissions(self):
        item = self.draft(image=True)
        for url in [reverse('announcements:manage_list'), reverse('announcements:create'),
                    reverse('announcements:manage_detail', args=[item.pk]), reverse('announcements:preview_image', args=[item.pk])]:
            self.assertEqual(Client().get(url).status_code, 302)
        with self.assertRaises(PermissionDenied):
            save_announcement(user=AnonymousUser(), data=self.data)
        with self.assertRaises(PermissionDenied):
            change_publication(item.pk, user=self.editor, version=item.version, action='published')
        user = get_user_model().objects.create_user('no_access', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('announcements:manage_list')).status_code, 403)

    def test_stale_edits_and_publication_actions_rejected(self):
        item = self.draft()
        live = self.change(item, 'published')
        with self.assertRaises(ValidationError):
            save_announcement(user=self.admin, pk=item.pk, data={**self.data, 'version': item.version})
        with self.assertRaises(ValidationError):
            self.change(item, 'archived')
        live.refresh_from_db()
        self.assertEqual(live.status, 'published')
        self.assertEqual(live.events.count(), 2)

    def test_csrf_confirmation_and_get_requests_do_not_publish(self):
        item = self.draft()
        url = reverse('announcements:manage_detail', args=[item.pk])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url, {'version': 1, 'action': 'published', 'confirm': 'on'}).status_code, 403)
        self.assertEqual(self.client.post(url, {'version': 1, 'action': 'published'}).status_code, 200)
        self.client.get(url, {'action': 'published'})
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')

    def test_xss_is_escaped_in_public_and_admin_content(self):
        item = save_announcement(user=self.admin, data={**self.data, 'title': '<script>bad()</script>',
                                                      'content': '<img src=x onerror=bad()>'})
        item = self.change(item, 'published')
        for url in [reverse('core:home'), reverse('core:announcements'),
                    reverse('announcements:detail', args=[item.pk]), reverse('announcements:manage_detail', args=[item.pk])]:
            response = self.client.get(url)
            self.assertNotContains(response, '<script>bad()</script>')
            self.assertNotContains(response, '<img src=x onerror=bad()>')
            self.assertContains(response, '&lt;script&gt;')

    def test_search_pagination_and_homepage_latest_three(self):
        for number in range(12):
            item = save_announcement(user=self.admin, data={**self.data, 'title': f'Notice {number:02}'})
            self.change(item, 'published')
        home = Client().get(reverse('core:home'))
        self.assertEqual(len(home.context['announcements']), 3)
        self.assertContains(home, 'Notice 11')
        self.assertNotContains(home, 'Notice 08')
        page = Client().get(reverse('core:announcements'), {'page': 2}).context['page_obj']
        self.assertEqual(len(page), 5)
        self.assertEqual(len(Client().get(reverse('core:announcements'), {'page': 3}).context['page_obj']), 2)
        filtered = self.client.get(reverse('announcements:manage_notices'), {'q': 'Notice 03', 'status': 'published'})
        self.assertEqual(filtered.context['page_obj'].paginator.count, 1)

    def test_images_are_reencoded_and_served_without_raw_media_exposure(self):
        upload = image_upload()
        upload.file = BytesIO(upload.read() + b'<script>hidden payload</script>')
        item = save_announcement(user=self.admin, data={**self.data, 'image_alt': 'Accessible image'},
                                 files=MultiValueDict({'image': [upload]}))
        self.assertNotIn(b'<script>', Path(item.image.path).read_bytes())
        self.assertEqual(Client().get(item.image.url).status_code, 404)
        item = self.change(item, 'published')
        response = Client().get(reverse('announcements:image', args=[item.pk]))
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))

    def test_invalid_images_alt_text_and_multiple_uploads_are_rejected(self):
        bad = [SimpleUploadedFile('bad.svg', b'<svg/>', content_type='image/svg+xml'),
               SimpleUploadedFile('bad.png', b'\x89PNG\r\n\x1a\nnot an image', content_type='image/png'),
               SimpleUploadedFile('bad.jpg', image_upload().read(), content_type='image/jpeg')]
        for upload in bad:
            form = AnnouncementForm({**self.data, 'image_alt': 'Test'}, MultiValueDict({'image': [upload]}))
            self.assertFalse(form.is_valid())
        self.assertFalse(AnnouncementForm(self.data, MultiValueDict({'image': [image_upload()]})).is_valid())
        self.assertFalse(AnnouncementForm({**self.data, 'image_alt': 'Test'},
            MultiValueDict({'image': [image_upload(), image_upload()]})).is_valid())
        with override_settings(ANNOUNCEMENT_IMAGE_MAX_BYTES=1):
            self.assertFalse(AnnouncementForm({**self.data, 'image_alt': 'Test'}, MultiValueDict({'image': [image_upload()]})).is_valid())
        with override_settings(ANNOUNCEMENT_IMAGE_MAX_PIXELS=10):
            self.assertFalse(AnnouncementForm({**self.data, 'image_alt': 'Test'}, MultiValueDict({'image': [image_upload()]})).is_valid())

    def test_audit_failure_rolls_back_content_and_cleans_upload(self):
        with patch('announcements.services.record_event', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.draft(image=True)
        self.assertFalse(Announcement.objects.exists())
        self.assertEqual([p for p in Path(self.media.name).rglob('*') if p.is_file()], [])
        item = self.draft()
        with patch('announcements.services.record_event', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.change(item, 'published')
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')

    def test_image_replacement_and_removal_cleanup_after_commit(self):
        item = self.draft(image=True)
        original = Path(item.image.path)
        with self.captureOnCommitCallbacks(execute=True):
            item = save_announcement(user=self.admin, pk=item.pk,
                data={**self.data, 'version': item.version, 'image_alt': 'Replacement'},
                files=MultiValueDict({'image': [image_upload()]}))
        self.assertFalse(original.exists())
        replacement = Path(item.image.path)
        with self.captureOnCommitCallbacks(execute=True):
            item = save_announcement(user=self.admin, pk=item.pk,
                data={**self.data, 'version': item.version, 'remove_image': 'on'})
        self.assertFalse(item.image)
        self.assertFalse(replacement.exists())

    def test_missing_image_blocks_publication(self):
        item = self.draft(image=True)
        Path(item.image.path).unlink()
        with self.assertRaises(ValidationError):
            self.change(item, 'published')

    def test_publication_history_requires_separate_permission(self):
        item = self.draft()
        self.client.force_login(self.editor)
        route = reverse('announcements:manage_detail', args=[item.pk])
        self.assertNotContains(self.client.get(route), 'Announcement saved as a private draft.')
        grant(self.editor, 'announcements.view_announcementevent')
        self.assertContains(self.client.get(route), 'Announcement saved as a private draft.')
