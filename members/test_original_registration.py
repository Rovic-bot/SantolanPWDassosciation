from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from . import test_registration_edit as registration_tests


class OriginalRegistrationRecordTests(TestCase):
    setUp = registration_tests.MemberRegistrationEditTests.setUp

    def test_complete_original_registration_is_inline_and_distinct_from_later_changes(self):
        self.client.force_login(self.actor)
        self.member.registration_profile = {**self.source, 'guardian_name': 'Later edited guardian'}
        self.member.save(update_fields=['registration_profile'])
        response = self.client.get(reverse('members:detail', args=[self.member.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registration information')
        self.assertEqual(response.context['original_registration_sections'],
                         self.source['profile_sections'] + self.source['digital_sections'])
        for value in ('Recorded guardian', '09170000002', 'Recorded spouse', '0001-0002', '0003-0004', '01610'):
            self.assertContains(response, value)
        self.assertNotContains(response, 'Later edited guardian')
        self.application.refresh_from_db()
        self.assertEqual(self.application.registration_profile, self.source)

    def test_linked_intake_access_is_not_bypassed_by_member_permission(self):
        self.client.force_login(self.actor)
        with patch('members.views.require_linked_access', side_effect=PermissionDenied):
            response = self.client.get(reverse('members:detail', args=[self.member.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['original_registration_sections'])
        self.assertNotContains(response, 'Recorded guardian')
        self.assertNotContains(response, 'Registration information')
