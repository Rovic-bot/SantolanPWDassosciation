"""Retired duplicate profiles keep canonical navigation and protected receipts."""
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from membership.tests import grant
from .models import AssistanceCase, AssistanceLog, AssistanceRelease
from .services import VIEW_PERMISSIONS
from .tests import create_application, private_media, seed_statuses


class RetiredAssistanceDetailTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('retired_detail_admin')
        self.application = create_application()
        self.url = reverse('assistance:detail', args=[self.application.pk])
        self.review_url = reverse('programs:application_detail',
            args=[self.application.program_id, self.application.pk])
        self.member_url = reverse('members:detail', args=[self.application.member_id])
        self.client.force_login(self.admin)

    def test_all_duplicate_profiles_redirect_without_writing_case_data(self):
        for application in (self.application, create_application(member=self.application.member)):
            response = self.client.get(reverse('assistance:detail', args=[application.pk]))
            self.assertRedirects(response, self.member_url)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertTemplateNotUsed(response, 'assistance/detail.html')
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertFalse(AssistanceLog.objects.exists())

    def test_application_review_has_no_duplicate_profile_link(self):
        response = self.client.get(self.review_url)
        self.assertContains(response, self.member_url)
        self.assertNotContains(response, 'Beneficiary decisions and assistance')
        self.assertNotContains(response, f'href="{self.url}"')

    def test_legacy_redirect_does_not_grant_member_access(self):
        viewer = get_user_model().objects.create_user('retired_detail_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *VIEW_PERMISSIONS)
        self.client.force_login(viewer)
        self.assertRedirects(self.client.get(self.url), self.review_url)
        self.assertEqual(self.client.get(self.member_url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)
        self.assertEqual(self.client.get(reverse('assistance:detail', args=[uuid4()])).status_code, 404)
        viewer.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_action_and_release_navigation_never_returns_to_retired_page(self):
        for action in ('decision', 'release'):
            response = self.client.get(reverse(f'assistance:{action}', args=[self.application.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, f'href="{self.url}"')
        response = self.client.get(reverse('assistance:program_releases', args=[self.application.program_id]))
        self.assertContains(response, self.review_url)
        self.assertNotContains(response, f'href="{self.url}"')
