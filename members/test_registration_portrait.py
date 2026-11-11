"""Approved records reuse the active private 2x2 upload and retain initials."""
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from membership import registration_services
from membership.test_pdf_registration import association_data
from membership.test_registration_decisions import DecisionHelpers
from membership.tests import grant
from .models import Member


class RegistrationPortraitTests(DecisionHelpers, TestCase):
    def setUp(self):
        self.setup_decisions()
        self.client.force_login(self.actor)

    def approve_photo(self, **changes):
        intake = self.make(files=MultiValueDict({'photo_2x2': [image_upload()]}))
        photo = intake.revisions.get().attachments.get()
        self.decide(intake, self.data(intake, **changes))
        return intake, photo, Member.objects.get()

    def test_uploaded_photo_survives_review_correction_and_is_permission_checked(self):
        intake, photo, member = self.approve_photo(first_name='Corrected')
        record_url = reverse('members:detail', args=[member.pk])
        photo_url = reverse('membership:registration_document', args=[photo.pk])
        response = self.client.get(record_url)
        self.assertIsNone(response.context['portrait'])
        self.assertContains(response, 'member-record-avatar')
        self.assertNotContains(response, photo_url)
        self.assertEqual(self.client.get(photo_url + '?preview=1').status_code, 403)

        grant(self.actor, 'membership.view_registration_documents')
        response = self.client.get(record_url)
        self.assertEqual(response.context['portrait'], photo)
        self.assertContains(response, f'src="{photo_url}?preview=1"')
        self.assertNotContains(response, 'member-record-avatar')
        self.assertFalse(member.application.documents.exists())
        self.assertEqual(intake.revisions.count(), 2)
        for query, disposition in (('', 'attachment'), ('?preview=1', 'inline')):
            downloaded = self.client.get(photo_url + query)
            try:
                self.assertEqual(downloaded.status_code, 200)
                self.assertTrue(downloaded['Content-Disposition'].startswith(disposition))
                self.assertEqual(downloaded['Content-Type'], photo.content_type)
                self.assertIn('no-store', downloaded['Cache-Control'])
                self.assertTrue(b''.join(downloaded.streaming_content))
            finally:
                if not downloaded.closed:
                    downloaded.close()
        self.assertEqual(intake.actions.filter(action='private_document_downloaded').count(), 2)
        self.actor.user_permissions.remove(Permission.objects.get(
            content_type__app_label='membership', codename='view_registration_documents'))
        self.assertIsNone(self.client.get(record_url).context['portrait'])
        self.assertEqual(self.client.get(photo_url + '?preview=1').status_code, 403)

    def test_missing_photo_uses_initials_and_other_upload_is_not_a_portrait(self):
        intake = self.make(files=MultiValueDict({'voter_certificate': [image_upload()]}))
        self.decide(intake)
        grant(self.actor, 'membership.view_registration_documents')
        response = self.client.get(reverse('members:detail', args=[Member.objects.get().pk]))
        self.assertIsNone(response.context['portrait'])
        self.assertEqual(response.context['record_summary']['initials'], 'FE')
        self.assertContains(response, 'member-record-avatar')

    def test_latest_photo_is_used_and_audit_failure_prevents_delivery(self):
        intake = self.make(files=MultiValueDict({'photo_2x2': [image_upload()]}))
        old = intake.revisions.get().attachments.get()
        registration_services.correct_registration(intake.reference, user=self.actor, version=intake.version,
            reason='Replace synthetic photo before approval.',
            data=association_data() | {'pwd_number': '00-0000-000-0000001'},
            files=MultiValueDict({'photo_2x2': [image_upload()]}))
        intake.refresh_from_db()
        current = intake.revisions.get(number=intake.current_revision).attachments.get()
        self.decide(intake)
        grant(self.actor, 'membership.view_registration_documents')
        response = self.client.get(reverse('members:detail', args=[Member.objects.get().pk]))
        self.assertEqual(response.context['portrait'], current)
        self.assertNotContains(response, str(old.pk))
        with patch('membership.registration_services.record_action', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaisesMessage(RuntimeError, 'Audit unavailable'):
                self.client.get(reverse('membership:registration_document', args=[current.pk]) + '?preview=1')
