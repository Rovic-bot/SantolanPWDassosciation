from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.portal_editor import PAGES, save_page
from core.portal_models import PortalPage, PortalPageRevision
from membership.tests import grant


def artwork():
    stream = BytesIO()
    Image.new('RGB', (16, 16), 'blue').save(stream, format='PNG')
    return SimpleUploadedFile('test.png', stream.getvalue(), content_type='image/png')


class PortalEditorTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('portal_admin')
        self.editor = get_user_model().objects.create_user('portal_editor', is_staff=True)
        grant(self.editor, 'accounts.access_dashboard', 'core.view_publiccontent', 'core.change_publiccontent')
        self.client.force_login(self.admin)
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def save(self, **options):
        values = dict(user=self.admin, version=0, changes={'welcome_heading': 'A reviewed public welcome'}, files={})
        values.update(options)
        return save_page('home', **values)

    def test_all_tabs_use_the_actual_public_templates_and_get_never_saves(self):
        response = self.client.get(reverse('core:content_list'))
        self.assertContains(response, 'Public portal editor')
        self.assertNotIn('results', response.context['editor_config']['pages'])
        self.assertEqual(self.client.get(reverse('core:portal_preview', args=['results'])).status_code, 404)
        for key, label, route in PAGES:
            with self.subTest(page=key):
                preview = self.client.get(reverse('core:portal_preview', args=[key]))
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview['X-Frame-Options'], 'SAMEORIGIN')
                self.assertContains(preview, 'data-portal-field')
                self.assertContains(preview, 'portal-edit-frame.js')
                public = Client().get(reverse(route))
                self.assertEqual(public.status_code, 200)
                self.assertNotContains(public, 'data-portal-field')
                self.assertNotContains(public, 'portal-edit-frame.js')
        self.assertFalse(PortalPage.objects.exists())
        self.assertFalse(PortalPageRevision.objects.exists())
        save_page('programs', user=self.admin, version=0, changes={'hero_title': 'Our public programs'}, files={})
        self.assertContains(Client().get(reverse('core:programs')), 'Our public programs')

    def test_save_escapes_text_preserves_public_records_and_retains_revisions(self):
        item, published = self.save(changes={'welcome_heading': '<script>alert(1)</script>\nA new welcome'})
        self.assertTrue(published)
        response = Client().get(reverse('core:home'))
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(item.revisions.count(), 1)
        self.assertEqual(item.revisions.get().actor, self.admin)
        self.save(version=1, changes={'welcome_heading': 'Another welcome'})
        self.assertEqual(PortalPageRevision.objects.count(), 2)
        self.assertIn('<script>', PortalPageRevision.objects.first().before['published']['welcome_heading'])

    def test_current_home_and_resource_cards_are_editable_and_drafts_stay_private(self):
        fields = {'guidance_heading': 'Reviewed guidance heading',
                  'guidance_application-information': 'Reviewed application card body',
                  'guidance_title_faq': 'Reviewed FAQ title'}
        self.save(user=self.editor, changes=fields, files={'picture_1': artwork()})
        preview = self.client.get(reverse('core:portal_preview', args=['home']))
        for field, value in fields.items():
            self.assertContains(preview, f'data-portal-field="{field}"')
            self.assertContains(preview, value)
            self.assertNotContains(Client().get(reverse('core:home')), value)
        self.assertContains(preview, 'data-portal-picture="picture_1"')
        self.save(version=1, changes={})
        for value in fields.values():
            self.assertContains(Client().get(reverse('core:home')), value)
        resource_fields = {'text_012': 'Reviewed FAQ heading', 'text_015': 'Reviewed FAQ answer',
            'text_028': 'Reviewed resource heading', 'resource_title_resources-work': 'Reviewed work title',
            'resource_body_resources-care': '<script>unsafe()</script> Caregiver information'}
        resource_fields.update({f'faq_{key}_description': f'Reviewed {key} application guidance'
                                for key in ('membership', 'pdao', 'program', 'referral')})
        save_page('resources', user=self.admin, version=0, changes=resource_fields, files={})
        response = Client().get(reverse('core:resources'))
        for field, value in resource_fields.items():
            if field != 'resource_body_resources-care':
                self.assertContains(response, value)
        self.assertContains(response, '&lt;script&gt;unsafe()&lt;/script&gt;')
        self.assertNotContains(response, '<script>unsafe()')
        self.assertEqual(PortalPageRevision.objects.count(), 3)

    def test_draft_is_private_until_an_authorized_save(self):
        self.save(user=self.editor)
        self.assertNotContains(Client().get(reverse('core:home')), 'A reviewed public welcome')
        preview = self.client.get(reverse('core:portal_preview', args=['home']))
        self.assertContains(preview, 'A reviewed public welcome')
        self.save(version=1, changes={})
        self.assertContains(Client().get(reverse('core:home')), 'A reviewed public welcome')

    def test_stale_save_and_unknown_fields_cannot_change_the_page(self):
        self.save()
        with self.assertRaises(ValidationError):
            self.save()
        for changes in ({'member_income': '999'}, {'picture_1': '/media/private.png'}, {'welcome_heading': {'html': 'bad'}}):
            with self.assertRaises(ValidationError):
                self.save(version=1, changes=changes)
        self.assertEqual(PortalPage.objects.get().version, 1)
        self.assertEqual(PortalPageRevision.objects.count(), 1)

    def test_routes_require_permissions_csrf_and_post(self):
        public = Client()
        for name in ('portal_preview', 'portal_state'):
            self.assertEqual(public.get(reverse('core:' + name, args=['home'])).status_code, 302)
        url = reverse('core:portal_save', args=['home'])
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url, {}).status_code, 403)
        self.editor.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            self.save(user=self.editor)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse('core:portal_preview', args=['home'])).status_code, 403)
        self.assertFalse(PortalPage.objects.exists())

    def test_image_validation_publication_replacement_and_reset(self):
        item, _ = self.save(user=self.editor, changes={}, files={'picture_1': artwork()})
        value = item.content['picture_1']
        url = reverse('core:portal_image', args=['home', 'picture_1', value['token']])
        self.assertEqual(Client().get(url).status_code, 404)
        self.assertEqual(Client().get(url + '?preview=1').status_code, 403)
        preview = self.client.get(url + '?preview=1')
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(b''.join(preview.streaming_content).startswith(b'\x89PNG'))
        self.save(version=1)
        response = Client().get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        self.save(version=2, changes={}, files={'picture_1': artwork()})
        self.assertEqual(Client().get(url).status_code, 404)
        self.save(version=3, changes={}, reset=['picture_1'])
        self.assertNotIn('picture_1', PortalPage.objects.get().published)
        self.assertTrue(Path(self.media.name, value['file']).exists())
        with self.assertRaises(ValidationError):
            self.save(version=4, changes={}, files={'picture_1': SimpleUploadedFile('bad.png', b'not an image', content_type='image/png')})

    def test_audit_failure_rolls_back_content_and_removes_new_upload(self):
        with patch('core.portal_editor.PortalPageRevision.objects.create', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.save(files={'picture_1': artwork()})
        self.assertFalse(PortalPage.objects.exists())
        self.assertFalse(PortalPageRevision.objects.exists())
        self.assertFalse(list(Path(self.media.name).rglob('*.png')))

    def test_save_response_and_stale_replay(self):
        url = reverse('core:portal_save', args=['home'])
        data = {'version': 0, 'changes': json.dumps({'welcome_heading': 'Explicitly saved welcome'})}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['published'])
        self.assertEqual(self.client.post(url, data).status_code, 400)
        self.assertEqual(PortalPageRevision.objects.count(), 1)
