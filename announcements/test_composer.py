from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from members.tests import create_member
from membership.tests import grant
from programs.tests import create_program
from programs.models import ProgramPicture
from programs.testsupport import application_fixture, private_media
from .forms import AnnouncementComposerForm
from .models import Announcement
from .results import prepare_results
from .services import change_publication, save_announcement
from .tests import image_upload


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AnnouncementComposerTests(TestCase):
    def setUp(self):
        private_media(self)
        self.admin = get_user_model().objects.create_superuser('composer-admin')
        self.client.force_login(self.admin)
        self.data = {'title': 'Community update', 'content': 'The complete community announcement.', 'version': 0}
        self.url = reverse('announcements:create') + '?popup=1'

    def save(self, **kwargs):
        return save_announcement(user=self.admin, data=self.data, composer=True, **kwargs)

    def test_popup_has_only_three_editor_fields_and_creates_a_private_draft(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'announcements/composer_form.html')
        self.assertEqual([field.name for field in response.context['form'].visible_fields()], ['title', 'content', 'image'])
        response = self.client.post(self.url, {**self.data, 'category': 'results', 'status': 'published',
            'source_office': 'Forged source', 'image_alt': 'Forged description'})
        self.assertEqual(response.status_code, 200)
        item = Announcement.objects.get()
        self.assertEqual(response.json(), {'redirect': reverse('announcements:manage_detail', args=[item.pk])})
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.category, 'general')
        self.assertEqual(item.source_office, 'Barangay Santolan PWD Association')
        self.assertEqual(item.image_alt, '')
        self.assertIsNone(item.published_at)
        self.assertEqual(item.events.get().actor, self.admin)
        self.assertEqual(Client().get(reverse('announcements:detail', args=[item.pk])).status_code, 404)

    def test_required_fields_and_invalid_upload_are_returned_inside_popup(self):
        response = self.client.post(self.url, {'title': '', 'content': '', 'version': 0})
        self.assertEqual(set(response.context['form'].errors), {'title', 'content'})
        self.assertTemplateUsed(response, 'announcements/composer_form.html')
        form = AnnouncementComposerForm(self.data, MultiValueDict({'image': [image_upload(), image_upload()]}))
        self.assertFalse(form.is_valid())
        self.assertIn('Upload one announcement image only.', form.non_field_errors())
        self.assertFalse(Announcement.objects.exists())

    def test_image_is_sanitized_and_edit_preserves_the_existing_description(self):
        response = self.client.post(self.url, {**self.data, 'image': image_upload()})
        self.assertEqual(response.status_code, 200)
        item = Announcement.objects.get()
        self.assertEqual(item.image_alt, 'Image accompanying Community update')
        self.assertTrue(item.image.storage.exists(item.image.name))
        self.assertTrue(item.image.name.endswith('.png'))
        item.image_alt = 'Previously reviewed accessible image description'
        item.save(update_fields=['image_alt'])
        self.data['version'] = item.version
        item = self.save(pk=item.pk)
        self.assertEqual(item.image_alt, 'Previously reviewed accessible image description')
        item = change_publication(item.pk, user=self.admin, version=item.version, action='published')
        response = Client().get(reverse('announcements:image', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        with self.captureOnCommitCallbacks(execute=True):
            item = save_announcement(user=self.admin, composer=True, pk=item.pk,
                data={**self.data, 'version': item.version, 'remove_image': 'on'})
        self.assertFalse(item.image)
        self.assertEqual(item.image_alt, '')
        self.assertEqual(item.status, 'draft')

    def test_popup_enforces_permissions_csrf_and_stale_edits(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.url, self.data).status_code, 403)
        item = self.save()
        url = reverse('announcements:edit', args=[item.pk]) + '?popup=1'
        response = self.client.post(url, self.data)
        self.assertContains(response, 'Another administrator changed this announcement')
        self.assertEqual(item.events.count(), 1)
        editor = get_user_model().objects.create_user('notice-editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'announcements.view_announcement', 'announcements.change_announcement')
        self.client.force_login(editor)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        item = change_publication(item.pk, user=self.admin, version=item.version, action='published')
        self.assertEqual(self.client.post(url, {**self.data, 'version': item.version}).status_code, 403)

    def test_composer_audit_failure_rolls_back_and_cleans_uploaded_file(self):
        with patch('announcements.services.record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.save(files=MultiValueDict({'image': [image_upload()]}))
        self.assertFalse(Announcement.objects.exists())
        from django.conf import settings
        self.assertFalse([path for path in Path(settings.MEDIA_ROOT).rglob('*') if path.is_file()])

    def test_filtered_announcement_shows_complete_escaped_content_without_popup(self):
        self.data['content'] = 'Long announcement. ' * 100 + '\n\nFinal details <script>bad()</script>'
        item = self.save()
        change_publication(item.pk, user=self.admin, version=item.version, action='published')
        response = Client().get(reverse('core:announcements'), {'category': 'announcements'})
        self.assertContains(response, 'Final details &lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertNotContains(response, 'Read more')
        self.assertNotContains(response, 'data-public-popup data-popup-label')
        self.assertContains(response, 'notice-full-card', count=1)
        combined = Client().get(reverse('core:announcements'))
        self.assertContains(combined, 'data-public-popup data-popup-label')
        self.assertContains(combined, 'Read more')
        self.assertNotContains(combined, 'Final details')

    def test_each_topic_withholds_drafts_withdrawals_and_archived_notices(self):
        item = self.save()
        for action in (None, 'published', 'draft', 'published', 'archived', 'published', 'deleted'):
            if action:
                item = change_publication(item.pk, user=self.admin, version=item.version, action=action)
            for category in ('', 'announcements'):
                response = Client().get(reverse('core:announcements'), {'category': category})
                self.assertEqual(response.context['page_obj'].paginator.count, int(item.status == 'published'))

    def test_filtered_results_render_only_authorized_public_projection_and_withdraw_immediately(self):
        program = create_program(ewaf_applicable=True, description='Full result overview. ' * 40 + 'Final results paragraph.')
        member = create_member('COMPOSER-PRIVATE-MEMBER')
        application_fixture(program, member)
        item = prepare_results(program.pk, user=self.admin, version=0, recorded=True,
            reason='Private administrative review reason',
            selection_reason='Synthetic selection based on the published program requirements.')
        item = change_publication(item.pk, user=self.admin, version=item.version, action='published')
        url = reverse('core:announcements') + '?category=results'
        response = Client().get(url)
        self.assertContains(response, 'Final results paragraph.')
        self.assertContains(response, 'Members who applied')
        self.assertContains(response, 'Selected members')
        self.assertContains(response, item.result_revision.public_payload['applicants'][0]['name'])
        for private in (member.full_name, member.control_number, member.contact_number, item.result_revision.reason,
                        item.result_revision.source_digest):
            if private:
                self.assertNotContains(response, private)
        self.assertNotContains(response, 'Read more')
        self.assertNotContains(response, 'data-public-popup data-popup-label')
        self.assertContains(response, 'notice-full-card', count=1)
        self.assertEqual(response.context['page_obj'][0]['results'], item.result_revision.public_payload)
        self.assertEqual(response.context['page_obj'][0]['image_url'], '')
        picture = ProgramPicture.objects.create(program=program, image=image_upload())
        image_url = reverse('programs:public_picture', args=[program.pk])
        for destination in (url, reverse('core:announcements'),
                            reverse('announcements:detail', args=[item.pk]) + '?popup=1'):
            with self.subTest(destination=destination):
                illustrated = Client().get(destination)
                self.assertContains(illustrated, f'src="{image_url}"')
                self.assertNotContains(illustrated, picture.image.name)
                self.assertNotContains(illustrated, '/media/')
        change_publication(item.pk, user=self.admin, version=item.version, action='draft')
        self.assertNotContains(Client().get(url), 'Final results paragraph.')
        self.assertNotContains(Client().get(url), image_url)
