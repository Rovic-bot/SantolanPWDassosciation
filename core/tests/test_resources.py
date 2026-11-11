from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from membership.tests import grant
from scripts.durable_test_runner import require_disposable
from core.content import save_content, RESOURCE_KEYS, DEFAULTS
from core.models import PublicContent, ContentRevision


def resource_data(**changes):
    return {'title': 'Synthetic reviewed resource', 'body': 'Synthetic public guidance only.',
        'source_url': 'https://example.org/synthetic-reviewed-source', 'provider': 'Synthetic test provider',
        'reviewed_on': timezone.localdate().isoformat(), 'source_review_confirmed': 'on',
        'action': 'draft', 'version': 0, 'reason': 'Synthetic review for tests only.', **changes}


class ResourceTests(TestCase):
    def setUp(self):
        require_disposable()
        self.actor = get_user_model().objects.create_superuser('synthetic_resource_admin')
        self.key = 'resources-rights'
        self.url = reverse('core:resource_detail', args=[self.key])

    def save(self, **changes):
        return save_content(self.key, user=self.actor, data=resource_data(**changes))

    def test_public_topics_collect_no_data_and_do_not_leak_drafts(self):
        self.save(body='PRIVATE_DRAFT_MARKER', provider='PRIVATE_PROVIDER_MARKER')
        response = self.client.get(reverse('core:resources'))
        self.assertEqual(response.status_code, 200)
        for key in RESOURCE_KEYS:
            if key != 'resources-verification':
                self.assertContains(response, DEFAULTS[key][0])
        self.assertNotContains(response, 'PRIVATE_DRAFT_MARKER')
        self.assertNotContains(response, 'PRIVATE_PROVIDER_MARKER')
        self.assertNotContains(response, '<form')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(reverse('core:resources'), {}).status_code, 405)
        self.assertFalse(response.cookies.get('sessionid'))

    def test_publish_snapshot_remains_stable_during_draft_edit_and_archive_retains_history(self):
        self.save(action='publish')
        self.save(version=1, body='NEW_PRIVATE_DRAFT', provider='NEW_PRIVATE_PROVIDER')
        response = self.client.get(self.url)
        self.assertContains(response, 'Synthetic public guidance only.')
        self.assertNotContains(response, 'NEW_PRIVATE')
        self.assertContains(response, 'Synthetic test provider')
        self.save(version=2, action='archive')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        item = PublicContent.objects.get(key=self.key)
        self.assertTrue(item.archived)
        self.assertEqual(item.revisions.count(), 3)
        self.assertEqual(item.revisions.first().before['published']['provider'], 'Synthetic test provider')
        self.save(version=3, action='publish')
        item.refresh_from_db()
        self.assertFalse(item.archived)

    def test_publication_requires_reviewed_source_provider_date_and_confirmation(self):
        for key in ('source_url', 'provider', 'reviewed_on', 'source_review_confirmed'):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                self.save(action='publish', **{key: ''})
        with self.assertRaises(ValidationError):
            self.save(action='publish', reviewed_on=(timezone.localdate() + timedelta(days=1)).isoformat())
        self.assertFalse(PublicContent.objects.exists())

    def test_url_safety_plain_text_and_unknown_detail_keys(self):
        for value in ('javascript:alert(1)', 'http://example.org', 'https://user:secret@example.org'):
            with self.assertRaises(ValidationError):
                self.save(action='publish', source_url=value)
        self.save(action='publish', body='<script>private()</script>', provider='<b>Provider</b>')
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>private()')
        self.assertContains(response, '&lt;b&gt;Provider&lt;/b&gt;')
        self.assertEqual(self.client.get(reverse('core:resource_detail', args=['privacy'])).status_code, 404)

    def test_draft_editor_cannot_publish_archive_or_retrieve_private_cms_anonymously(self):
        editor = get_user_model().objects.create_user('synthetic_resource_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'core.view_publiccontent', 'core.change_publiccontent')
        for action in ('publish', 'archive', 'withdraw'):
            with self.assertRaises(PermissionDenied):
                save_content(self.key, user=editor, data=resource_data(action=action))
        route = reverse('core:content_edit', args=[self.key])
        self.assertEqual(self.client.get(route).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.actor)
        self.assertEqual(strict.post(route, resource_data(action='publish')).status_code, 403)

    def test_stale_writes_audit_failure_and_permission_revocation(self):
        self.save()
        with self.assertRaises(ValidationError):
            self.save(action='publish')
        with patch('core.content.ContentRevision.objects.create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.save(version=1, action='publish')
        self.assertEqual(PublicContent.objects.get().version, 1)
        self.assertEqual(ContentRevision.objects.count(), 1)
        editor = get_user_model().objects.create_user('synthetic_revoked_publisher', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'core.view_publiccontent', 'core.change_publiccontent', 'core.publish_publiccontent')
        self.assertTrue(editor.has_perm('core.publish_publiccontent'))
        editor.user_permissions.remove(Permission.objects.get(codename='publish_publiccontent'))
        with self.assertRaises(PermissionDenied):
            save_content(self.key, user=editor, data=resource_data(version=1, action='publish'))

    def test_external_verification_is_only_an_explicitly_published_link(self):
        key = 'resources-verification'
        save_content(key, user=self.actor, data=resource_data())
        self.assertNotContains(self.client.get(reverse('core:resources')), 'PWD ID Verification — External Website')
        save_content(key, user=self.actor, data=resource_data(version=1, action='publish'))
        response = self.client.get(reverse('core:resources'))
        self.assertContains(response, 'PWD ID Verification — External Website')
        self.assertContains(response, 'https://example.org/synthetic-reviewed-source')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertNotContains(response, 'type="file"')

    def test_navigation_canonical_guides_results_and_method_do_not_duplicate_private_records(self):
        self.save(action='publish')
        response = self.client.get(self.url)
        nav = response.content.decode().split('aria-label="Main navigation"')[1].split('</nav>')[0]
        self.assertEqual(nav.count('aria-current="page"'), 1)
        self.assertIn('Resources &amp; Help', nav)
        index = self.client.get(reverse('core:resources'))
        self.assertContains(index, reverse('core:membership') + '#pdao-requirements-heading')
        self.assertContains(index, reverse('core:announcements') + '?category=results')
        self.assertIn('does not assign numerical business ranks', DEFAULTS['ewaf'][1])
        self.assertEqual(self.client.get('/referrals/submit/').status_code, 404)
        self.assertEqual(self.client.get('/rsvp/').status_code, 404)
