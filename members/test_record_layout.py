"""The redesigned full record retains separate document/history/action access."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from announcements.tests import image_upload
from documents.models import DocumentType, MembershipApplicationDocument, MembershipDocumentRequirement
from membership.tests import grant
from programs.testsupport import private_media
from .models import MemberEvent
from .tests import create_member


class MemberRecordLayoutPermissionsTests(TestCase):
    def test_portrait_history_verification_and_status_actions_keep_their_permissions(self):
        private_media(self)
        member = create_member('RECORD-LAYOUT-001')
        viewer = get_user_model().objects.create_user('record_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'members.view_member')
        requirement, _ = MembershipDocumentRequirement.objects.get_or_create(
            capture_key='photo_1x1', defaults={
                'document_type': DocumentType.objects.get_or_create(name='Synthetic portrait')[0]})
        portrait = MembershipApplicationDocument.objects.create(application=member.application,
            requirement=requirement, label='Private portrait example', file=image_upload(),
            content_type='image/png', size=100)
        MemberEvent.objects.create(member=member, actor=viewer, actor_label='Synthetic reviewer',
            action='profile_updated', notes='Private record timeline example')
        url = reverse('members:detail', args=[member.pk])
        document_url = reverse('members:document', args=[member.pk, portrait.pk])
        self.client.force_login(viewer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Full registration profile')
        self.assertNotContains(response, 'Event activity')
        self.assertNotContains(response, 'href="#member-record-profile"')
        self.assertIsNone(response.context['portrait'])
        for text in (document_url, 'Private record timeline example', 'Private portrait example',
                     'PRPWD: manually verified', 'Update status', 'Edit profile'):
            self.assertNotContains(response, text)
        self.assertEqual(self.client.get(document_url).status_code, 403)

        grant(viewer, 'documents.view_membershipapplicationdocument', 'members.view_memberevent',
              'membership.view_membershipapplication', 'members.change_member_status', 'members.change_member')
        response = self.client.get(url)
        self.assertEqual(response.context['portrait'], portrait)
        for text in (document_url, 'Private record timeline example', 'Private portrait example',
                     'PRPWD: manually verified', 'Update status', 'Edit profile'):
            self.assertContains(response, text)
        self.assertContains(response, 'name="version"')
        self.assertContains(response, 'csrfmiddlewaretoken')
