"""Private onsite uploads, member replacements, and unchanged source records."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from membership.test_registration_decisions import DecisionHelpers
from membership.tests import grant, pdf
from programs.testsupport import private_media
from ewaf.test_source_writers import SourceHelpers
from .document_models import MemberDocumentUpload
from .models import Member
from .services import update_member
from . import test_registration_edit as registration_fixtures


class OnsiteMemberDocumentTests(DecisionHelpers, TestCase):
    def setUp(self):
        private_media(self)
        self.setup_decisions()
        self.client.force_login(self.actor)

    def test_all_onsite_files_appear_with_their_existing_protected_urls(self):
        intake = self.make(data={'civil_alternative': 'birth'}, files=MultiValueDict({
            'photo_2x2': [image_upload()], 'civil_document': [pdf()], 'voter_certificate': [pdf()]}))
        self.decide(intake)
        member = Member.objects.get()
        self.assertFalse(member.application.documents.exists())
        url = reverse('members:detail', args=[member.pk])
        restricted = self.client.get(url)
        self.assertFalse(restricted.context['membership_documents']['allowed'])
        grant(self.actor, 'membership.view_registration_documents')
        response = self.client.get(url)
        inventory = response.context['membership_documents']
        self.assertEqual(len(inventory['current']), 3)
        self.assertContains(response, '3 attached')
        self.assertContains(response, 'Birth Certificate')
        self.assertNotContains(response, 'No membership documents have been uploaded.')
        for attachment in intake.revisions.get(number=intake.current_revision).attachments.all():
            protected = reverse('membership:registration_document', args=[attachment.pk])
            self.assertContains(response, protected)
            self.assertEqual(Client().get(protected).status_code, 302)
            stream = self.client.get(protected + '?preview=1')
            try:
                self.assertEqual(stream.status_code, 200)
                self.assertTrue(stream['Content-Disposition'].startswith('inline'))
                self.assertIn('no-store', stream['Cache-Control'])
                self.assertEqual(stream['X-Content-Type-Options'], 'nosniff')
                self.assertTrue(b''.join(stream.streaming_content))
            finally:
                if not stream.closed:
                    stream.close()
        self.assertFalse(MemberDocumentUpload.objects.exists())


class MemberDocumentUpdateTests(TestCase):
    post_data = registration_fixtures.MemberRegistrationEditTests.post_data

    def setUp(self):
        private_media(self)
        registration_fixtures.MemberRegistrationEditTests.setUp(self)

    def save(self, files, **changes):
        return update_member(self.member.pk, user=self.actor, version=self.member.version,
            data=self.post_data(**changes), notes='Synthetic document correction.', files=files)

    def files_on_disk(self):
        return sorted(path for path in Path(settings.MEDIA_ROOT).rglob('*') if path.is_file())

    def test_editor_saves_all_slots_and_acknowledgement_without_rewriting_registration(self):
        original = deepcopy(self.application.registration_profile)
        self.save(MultiValueDict({'photo_2x2': [image_upload()], 'civil_document': [pdf()],
            'voter_certificate': [pdf()]}), civil_alternative='marriage')
        self.member.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.application.registration_profile, original)
        self.assertEqual(self.member.document_uploads.count(), 3)
        self.assertTrue(self.member.registration_profile['update_acknowledgement']['confirmed'])
        self.assertIn('member_documents', self.member.events.get().changes)
        self.assertEqual(len(self.files_on_disk()), 3)
        response = self.client.get(reverse('members:detail', args=[self.member.pk]))
        self.assertEqual(len(response.context['membership_documents']['current']), 3)
        self.assertContains(response, 'Marriage Certificate')
        self.assertEqual(response.context['portrait'].slot, 'photo_2x2')
        edit = self.client.get(self.url)
        self.assertContains(edit, 'Current membership documents')
        self.assertFalse(edit.context['form'].initial['acknowledgement'])

    def test_replacements_keep_previous_file_and_download_permissions(self):
        self.save(MultiValueDict({'voter_certificate': [pdf()]}))
        self.member.refresh_from_db()
        original = self.member.document_uploads.get()
        self.save(MultiValueDict({'voter_certificate': [pdf()]}))
        latest = self.member.document_uploads.first()
        self.assertEqual(latest.predecessor_id, original.pk)
        self.assertEqual(len(self.files_on_disk()), 2)
        response = self.client.get(reverse('members:detail', args=[self.member.pk]))
        self.assertEqual(len(response.context['membership_documents']['current']), 1)
        self.assertEqual(len(response.context['membership_documents']['previous']), 1)
        for doc in (original, latest):
            url = reverse('members:uploaded_document', args=[self.member.pk, doc.pk])
            self.assertContains(response, url)
            self.assertEqual(Client().get(url).status_code, 302)
            stream = self.client.get(url + '?preview=1')
            try:
                self.assertEqual(stream.status_code, 200)
                self.assertTrue(stream['Content-Disposition'].startswith('inline'))
                self.assertEqual(stream['Content-Security-Policy'], "sandbox; default-src 'none'")
                self.assertIn('no-store', stream['Cache-Control'])
                self.assertTrue(b''.join(stream.streaming_content))
            finally:
                if not stream.closed:
                    stream.close()
        self.assertEqual(self.client.get(reverse('members:uploaded_document', args=[self.member.pk + 100, latest.pk])).status_code, 404)
        with self.assertRaises(PermissionDenied):
            MemberDocumentUpload.objects.filter(pk=original.pk).delete()
        with self.assertRaises(PermissionDenied):
            MemberDocumentUpload.objects.filter(pk=original.pk).update(alternative='changed')
        with self.assertRaises(PermissionDenied):
            original.save()

    def test_invalid_or_unacknowledged_uploads_never_write(self):
        cases = [({'acknowledgement': ''}, {'voter_certificate': [pdf()]}),
            ({}, {'civil_document': [pdf()]}), ({'civil_alternative': 'birth'}, {}),
            ({}, {'photo_2x2': [pdf()]}), ({}, {'unknown_slot': [pdf()]}),
            ({}, {'voter_certificate': [pdf(), pdf()]})]
        for data, uploads in cases:
            with self.subTest(data=data, slots=list(uploads)), self.assertRaises(ValidationError):
                self.save(MultiValueDict(uploads), **data)
        self.assertFalse(self.member.document_uploads.exists())
        self.assertFalse(self.member.events.exists())
        self.assertEqual(self.files_on_disk(), [])

    def test_audit_failure_and_stale_edit_do_not_leave_files_or_revisions(self):
        with patch('members.services.record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.save(MultiValueDict({'voter_certificate': [pdf()]}))
        self.assertEqual(self.files_on_disk(), [])
        self.assertFalse(MemberDocumentUpload.objects.exists())
        self.member.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        self.save(MultiValueDict({'voter_certificate': [pdf()]}))
        with self.assertRaises(ValidationError):
            self.save(MultiValueDict({'voter_certificate': [pdf()]}))
        self.assertEqual(len(self.files_on_disk()), 1)
        self.assertEqual(MemberDocumentUpload.objects.count(), 1)

    def test_member_edit_permission_alone_does_not_allow_private_file_access_or_upload(self):
        self.save(MultiValueDict({'voter_certificate': [pdf()]}))
        self.member.refresh_from_db()
        upload = self.member.document_uploads.get()
        editor = get_user_model().objects.create_user('synthetic_document_limited', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'members.view_member', 'members.change_member')
        self.client.force_login(editor)
        self.assertNotContains(self.client.get(reverse('members:detail', args=[self.member.pk])), str(upload.pk))
        self.assertEqual(self.client.get(reverse('members:uploaded_document', args=[self.member.pk, upload.pk])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            update_member(self.member.pk, user=editor, version=self.member.version,
                data=self.post_data(), notes='Denied upload', files=MultiValueDict({'voter_certificate': [pdf()]}))
        self.assertEqual(MemberDocumentUpload.objects.count(), 1)
        with patch('members.document_views.record_event', side_effect=RuntimeError('Synthetic access audit failure')):
            self.client.force_login(self.actor)
            with self.assertRaises(RuntimeError):
                self.client.get(reverse('members:uploaded_document', args=[self.member.pk, upload.pk]))


class MemberDocumentSourceTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        from members.tests import create_member
        from membership.test_pdf_registration import association_data
        from programs.testsupport import application_fixture
        self.setup_foundation()
        self.member = create_member('FICTIONAL-DOCUMENT-SOURCE')
        self.member.refresh_from_db()
        application_fixture(self.program, self.member)
        self.data = association_data() | {'pwd_number': self.member.control_number,
            'member_profile_format': 'association_pdf_v1', 'notes': 'Synthetic member document update'}
        self.register()
        self.client.force_login(self.officer)

    def upload(self):
        return update_member(self.member.pk, user=self.officer, version=self.member.version,
            data=self.data, notes=self.data['notes'], source_expected=self.expected(),
            files=MultiValueDict({'voter_certificate': [pdf()]}))

    def test_member_upload_and_private_access_keep_source_audits(self):
        original = deepcopy(self.member.application.registration_profile)
        self.upload()
        self.assert_transition(2)
        self.member.refresh_from_db()
        self.member.application.refresh_from_db()
        self.assertEqual(self.member.application.registration_profile, original)
        document = self.member.document_uploads.get()
        self.assertIn('member_documents', self.member.events.get().changes)
        response = self.client.get(reverse('members:uploaded_document', args=[self.member.pk, document.pk]))
        try:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b''.join(response.streaming_content))
        finally:
            if not response.closed:
                response.close()
        self.assert_transition(3)
        self.assertEqual(self.member.events.filter(action='document_downloaded').count(), 1)

    def test_late_source_failure_removes_new_upload_and_rolls_back_member(self):
        before_files = {path: path.read_bytes() for path in Path(settings.MEDIA_ROOT).rglob('*') if path.is_file()}
        with patch('ewaf.shared_invalidation.finish', side_effect=ValidationError('Synthetic late source failure')):
            with self.assertRaisesMessage(ValidationError, 'Synthetic late source failure'):
                self.upload()
        self.member.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        self.assertFalse(self.member.document_uploads.exists())
        self.assertFalse(self.member.events.exists())
        self.assertEqual({path: path.read_bytes() for path in Path(settings.MEDIA_ROOT).rglob('*') if path.is_file()}, before_files)
        self.assert_transition(1)
