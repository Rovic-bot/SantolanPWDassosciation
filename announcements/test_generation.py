from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from . import test_results as legacy
from .generation import generation_preview, generate_results
from .models import Announcement, ProgramResultRevision


class GenerateResultsTests(TestCase):
    setUp = legacy.ProgramResultTests.setUp

    def test_program_grid_preview_and_explicit_publication(self):
        response = self.client.get(reverse('announcements:choose_results'))
        self.assertContains(response, 'program-grid')
        self.assertContains(response, 'Review and publish')
        self.assertNotContains(response, '<select name="program"')
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        response = self.client.get(url)
        self.assertFalse(Announcement.objects.exists())
        plan = response.context['preview']
        self.assertEqual(plan['pending'], [])
        self.assertContains(response, self.application.public_reference, count=2)
        from django.test import Client
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(url, {'action': 'PUBLISH_RECORDED_RESULTS',
            'expected': plan['expected'], 'version': 0}).status_code, 403)
        self.assertFalse(Announcement.objects.exists())
        result = self.client.post(url, {'action': 'PUBLISH_RECORDED_RESULTS', 'expected': plan['expected'], 'version': 0})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(Announcement.objects.get().status, 'published')
        with self.assertRaises(ValidationError):
            generate_results(self.program.pk, user=self.admin, expected=plan['expected'], version=0)

    def test_publication_failure_rolls_back_new_revision(self):
        plan = generation_preview(self.program.pk, user=self.admin)
        with patch('announcements.generation.publish_results', side_effect=RuntimeError('Synthetic failure')):
            with self.assertRaises(RuntimeError):
                generate_results(self.program.pk, user=self.admin, expected=plan['expected'], version=0)
        self.assertFalse(Announcement.objects.exists())
        self.assertFalse(ProgramResultRevision.objects.exists())


class ResultCatalogTests(TestCase):
    setUp = legacy.ProgramResultTests.setUp
    draft = legacy.ProgramResultTests.draft
    publish = legacy.ProgramResultTests.publish

    def catalog(self, label):
        response = self.client.get(reverse('announcements:manage_list'))
        self.assertContains(response, label)
        return response.context['page_obj'][0].result_publication

    def test_landing_shows_results_without_publishing_on_get(self):
        for route in ('announcements:manage_list', 'announcements:choose_results'):
            response = self.client.get(reverse(route))
            self.assertContains(response, 'Prepare and publish program results')
            self.assertContains(response, 'data-results-preview')
            self.assertContains(response, 'Results not published')
            self.assertContains(response, 'Program: Published')
            self.assertNotContains(response, 'Saved announcements')
            self.assertNotContains(response, reverse('announcements:manage_notices'))
            self.assertNotContains(response, 'Association updates')
        self.assertFalse(Announcement.objects.exists())
        self.assertFalse(ProgramResultRevision.objects.exists())
        self.assertContains(self.client.get(reverse('core:announcements'), {'category': 'results'}),
                            'No announcements match this view.')

    def test_results_status_matches_public_visibility_through_publication_and_withdrawal(self):
        item = self.draft()
        self.assertNotIn('url', self.catalog('Results draft'))
        item = self.publish(item)
        detail = reverse('core:result_detail', args=[item.pk])
        self.assertEqual(self.catalog('Results published')['url'], detail)
        self.assertEqual(self.client.get(detail).status_code, 200)
        for status in ('draft', 'archived', 'deleted'):
            item = legacy.change_publication(item.pk, user=self.admin, version=item.version, action=status)
            self.assertNotIn('url', self.catalog('Results ' + status))
            self.assertEqual(self.client.get(detail).status_code, 404)
            if status != 'deleted':
                item = self.publish(item)

    def test_stale_missing_or_corrupt_revision_cannot_display_published_badge(self):
        item = self.publish(self.draft())
        revision = item.result_revision
        ProgramResultRevision.objects.filter(pk=revision.pk).update(
            public_payload={**revision.public_payload, 'unexpected': 'Private data'})
        self.assertNotIn('url', self.catalog('Results need review'))
        self.assertEqual(self.client.get(reverse('core:result_detail', args=[item.pk])).status_code, 404)
        ProgramResultRevision.objects.filter(pk=revision.pk).update(public_payload=revision.public_payload)
        self.member.version += 1
        self.member.save(update_fields=['version'])
        self.assertNotIn('url', self.catalog('Results need review'))
        Announcement.objects.filter(pk=item.pk).update(result_revision=None)
        self.assertNotIn('url', self.catalog('Results need review'))

    def test_future_publication_is_labeled_scheduled_and_has_no_public_link(self):
        item = self.publish(self.draft())
        Announcement.objects.filter(pk=item.pk).update(published_at=timezone.now() + timezone.timedelta(days=1))
        self.assertNotIn('url', self.catalog('Results scheduled'))
        self.assertEqual(self.client.get(reverse('core:result_detail', args=[item.pk])).status_code, 404)

    def test_notice_editor_retains_access_without_private_program_permissions(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        editor = get_user_model().objects.create_user('catalog_notice_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'announcements.view_announcement',
              'announcements.add_announcement', 'announcements.change_announcement')
        self.client.force_login(editor)
        self.assertRedirects(self.client.get(reverse('announcements:manage_list')),
                             reverse('announcements:manage_notices'))
        self.assertEqual(self.client.get(reverse('announcements:choose_results')).status_code, 403)
        self.assertEqual(self.client.get(reverse('announcements:prepare_results', args=[self.program.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('announcements:manage_notices')), self.program.name)

    def test_filters_keep_program_cards_and_result_status_together(self):
        self.draft()
        response = self.client.get(reverse('announcements:manage_list'),
            {'q': self.program.name, 'status': 'published', 'with_applications': '1'})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertContains(response, 'Results draft')
        response = self.client.get(reverse('announcements:manage_list'), {'q': 'No matching program'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertContains(response, 'No programs match your filters.')
