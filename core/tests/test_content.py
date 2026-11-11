from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from membership.tests import grant
from core.content import save_content, published_content
from core.models import PublicContent, ContentRevision


class ContentTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('cms_admin')

    def save(self, **changes):
        return save_content('contact', user=self.admin, data={'title': 'Confirmed Help Desk',
            'body': 'Synthetic office instructions.', 'version': 0, 'reason': 'Authorized content update.',
            'action': 'draft', **changes})

    def test_draft_publish_edit_and_withdraw_have_retained_versions(self):
        draft = self.save()
        self.assertNotEqual(published_content('contact')['body'], draft.body)
        self.save(version=1, action='publish')
        self.assertEqual(published_content('contact')['body'], 'Synthetic office instructions.')
        self.save(version=2, body='Unpublished changed instructions.')
        self.assertEqual(published_content('contact')['body'], 'Synthetic office instructions.')
        self.save(version=3, action='withdraw')
        self.assertNotEqual(published_content('contact')['body'], 'Synthetic office instructions.')
        self.assertEqual(ContentRevision.objects.count(), 4)
        self.assertEqual(ContentRevision.objects.first().before['published']['version'], 2)

    def test_permissions_stale_content_and_audit_rollback(self):
        editor = get_user_model().objects.create_user('cms_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'core.view_publiccontent', 'core.change_publiccontent')
        with self.assertRaises(PermissionDenied):
            save_content('contact', user=editor, data={'title':'Title', 'body':'Body', 'version':0, 'reason':'Reason', 'action':'publish'})
        self.save()
        with self.assertRaises(ValidationError):
            self.save()
        with patch('core.content.ContentRevision.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                self.save(version=1, action='publish')
        self.assertEqual(PublicContent.objects.get().version, 1)
        self.assertEqual(ContentRevision.objects.count(), 1)

    def test_all_page_keys_render_escaped_content_and_private_cms_routes(self):
        self.save(action='publish', body='<script>privatePayload()</script>')
        response = self.client.get(reverse('core:contact'), follow=True)
        self.assertContains(response, '&lt;script&gt;privatePayload()&lt;/script&gt;')
        self.assertNotContains(response, '<script>privatePayload()')
        for key in PublicContent.Key.values:
            route = reverse('core:content_edit', args=[key])
            self.client.logout()
            self.assertEqual(self.client.get(route).status_code, 302)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:content_list')).status_code, 200)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('core:content_edit', args=['contact']), {}).status_code, 403)

    def test_reason_and_supported_key_are_required(self):
        with self.assertRaises(ValidationError):
            self.save(reason='')
        with self.assertRaises(ValidationError):
            save_content('audit_logs', user=self.admin, data={})
        self.assertFalse(PublicContent.objects.exists())

    def test_about_formats_only_published_text_and_escapes_headings_lists_and_paragraphs(self):
        data = {'title': 'Reviewed About page', 'body': '## <script>heading()</script>\n\n'
                '- <img src=x onerror=bad()>\n- Approved objective\n\n<script>paragraph()</script>',
                'version': 0, 'reason': 'Reviewed public About copy.', 'action': 'publish'}
        item = save_content('about', user=self.admin, data=data)
        save_content('about', user=self.admin, data={**data, 'version': item.version,
                     'body': 'Unpublished About revision.', 'action': 'draft'})
        response = self.client.get(reverse('core:about'))
        self.assertContains(response, 'Mission and background')
        self.assertContains(response, '&lt;script&gt;heading()&lt;/script&gt;</h3>')
        self.assertContains(response, '<li>Approved objective</li>', html=True)
        self.assertContains(response, '&lt;img src=x onerror=bad()&gt;')
        self.assertContains(response, '&lt;script&gt;paragraph()&lt;/script&gt;')
        for private_or_unsafe in ('Unpublished About revision.', '<script>heading()', '<script>paragraph()', '<img src=x'):
            self.assertNotContains(response, private_or_unsafe)
        self.assertContains(response, reverse('core:resources'))

    def test_home_uses_only_published_support_content_and_withdrawal_fallbacks(self):
        keys = ('application-information', 'contact', 'faq', 'ewaf', 'privacy', 'accessibility')
        for key in keys:
            save_content(key, user=self.admin, data={
                'title': f'Approved {key}', 'body': f'Published instructions for {key}.',
                'version': 0, 'reason': 'Approved public guidance.', 'action': 'publish',
            })
            save_content(key, user=self.admin, data={
                'title': f'Draft {key}', 'body': f'Unpublished instructions for {key}.',
                'version': 1, 'reason': 'Pending review.', 'action': 'draft',
            })
        response = self.client.get(reverse('core:home'))
        for key in keys:
            self.assertContains(response, f'Published instructions for {key}.')
            self.assertNotContains(response, f'Unpublished instructions for {key}.')
        save_content('privacy', user=self.admin, data={
            'title': 'Privacy draft', 'body': 'Private draft.', 'version': 2,
            'reason': 'Withdraw outdated notice.', 'action': 'withdraw',
        })
        response = self.client.get(reverse('core:home'))
        self.assertNotContains(response, 'Published instructions for privacy.')
        self.assertNotContains(response, 'Private draft.')
        self.assertContains(response, 'Member records, application documents and calendar photos are private.')
