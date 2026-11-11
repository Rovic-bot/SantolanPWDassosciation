import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
from membership.models import MembershipApplication
from membership.tests import grant, profile, pdf
from .models import Member, MemberEvent, DisabilityType
from .services import change_status, update_member


def create_member(code='MEM-001'):
    data = {**profile(), 'control_number': code, 'disability_type': DisabilityType.objects.get_or_create(name='Visual Disability')[0]}
    application = MembershipApplication.objects.create(**data, submission_key=uuid.uuid4(), status='approved',
        prpwd_verified=True, prpwd_verified_at=timezone.now(), decided_at=timezone.now())
    return Member.objects.create(application=application, **data)


class MemberManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('member_admin', password='test-only-password')
        self.viewer = get_user_model().objects.create_user('member_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'members.view_member')
        self.member = create_member()
        self.member.refresh_from_db()
        self.detail = reverse('members:detail', args=[self.member.pk])
        self.edit = reverse('members:edit', args=[self.member.pk])
        self.data = {**profile(), 'control_number': self.member.control_number, 'disability_type': self.member.disability_type_id,
                     'full_name': 'Updated Test Member', 'version': 0, 'notes': 'Corrected the member record.'}
        self.client.force_login(self.admin)

    def test_private_directory_and_details_require_active_staff_permissions(self):
        for route in [reverse('members:list'), self.detail, self.edit]:
            self.assertEqual(Client().get(route).status_code, 302)
        unprivileged = get_user_model().objects.create_user('other', is_staff=True)
        self.client.force_login(unprivileged)
        self.assertEqual(self.client.get(self.detail).status_code, 403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertEqual(self.client.get(self.edit).status_code, 403)
        self.assertEqual(self.client.post(self.edit, self.data).status_code, 403)
        self.assertEqual(self.client.post(self.detail, {'version': 0, 'status': 'archived', 'notes': 'No'}).status_code, 403)

    def test_profile_update_keeps_original_application_and_records_before_after(self):
        response = self.client.post(self.edit, {**self.data, 'is_active': False, 'application': 999})
        self.assertRedirects(response, self.detail)
        self.member.refresh_from_db()
        self.assertEqual(self.member.full_name, 'Updated Test Member')
        self.assertEqual(self.member.application.full_name, 'Sample Applicant')
        self.assertTrue(self.member.is_active)
        event = self.member.events.get()
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.changes['full_name'], {'before': 'Sample Applicant', 'after': 'Updated Test Member'})
        self.assertIn('no-store', response['Cache-Control'])

    def test_edit_permission_does_not_allow_status_changes(self):
        grant(self.viewer, 'members.change_member')
        self.client.force_login(self.viewer)
        self.assertRedirects(self.client.post(self.edit, self.data), self.detail)
        self.assertEqual(self.client.post(self.detail, {'version': 1, 'status': 'archived', 'notes': 'No'}).status_code, 403)

    def test_archive_restore_and_inactive_preserve_history(self):
        for version, status in enumerate(['archived', 'inactive', 'active']):
            response = self.client.post(self.detail, {'version': version, 'status': status, 'notes': 'Authorized status update.'})
            self.assertRedirects(response, self.detail)
            self.member.refresh_from_db()
            self.assertEqual(self.member.status, status)
            self.assertEqual(self.member.is_active, status == 'active')
        self.assertEqual(self.member.events.count(), 3)
        self.assertEqual(MembershipApplication.objects.count(), 1)
        with self.assertRaises(ProtectedError):
            self.member.delete()

    def test_archived_profile_cannot_be_edited(self):
        change_status(self.member.pk, user=self.admin, version=0, status='archived', notes='Archive')
        self.assertContains(self.client.post(self.edit, {**self.data, 'version': 1}), 'Restore this archived member')
        self.member.refresh_from_db()
        self.assertEqual(self.member.full_name, 'Sample Applicant')

    def test_stale_forms_and_missing_reason_do_not_overwrite(self):
        self.client.post(self.edit, self.data)
        response = self.client.post(self.edit, {**self.data, 'full_name': 'Stale edit'})
        self.assertContains(response, 'Another administrator changed this member')
        self.assertContains(self.client.post(self.detail, {'version': 0, 'status': 'inactive', 'notes': 'Stale'}), 'Reload the page')
        self.assertEqual(self.member.events.count(), 1)
        self.assertContains(self.client.post(self.edit, {**self.data, 'version': 1, 'notes': ' '}), 'This field is required')

    def test_validation_and_duplicate_control_number(self):
        create_member('OTHER')
        for change in [{'control_number': ' other '}, {'birthdate': '2999-01-01'}, {'monthly_income': '-1'}, {'dependents': '-1'}]:
            response = self.client.post(self.edit, {**self.data, **change})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(self.member.events.exists())

    def test_changes_roll_back_when_audit_fails(self):
        with patch('members.services.record_event', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                update_member(self.member.pk, user=self.admin, version=0, data=self.data, notes='Update')
            with self.assertRaises(RuntimeError):
                change_status(self.member.pk, user=self.admin, version=0, status='inactive', notes='Update')
        self.member.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        self.assertEqual(self.member.full_name, 'Sample Applicant')
        self.assertTrue(self.member.is_active)

    def test_service_cannot_bypass_permissions(self):
        for user in [AnonymousUser(), self.viewer]:
            with self.assertRaises(PermissionDenied):
                update_member(self.member.pk, user=user, version=0, data=self.data, notes='No')
            with self.assertRaises(PermissionDenied):
                change_status(self.member.pk, user=user, version=0, status='inactive', notes='No')

    def test_history_requires_separate_permission(self):
        change_status(self.member.pk, user=self.admin, version=0, status='inactive', notes='Private history note')
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(self.detail), 'Private history note')
        grant(self.viewer, 'members.view_memberevent')
        self.assertContains(self.client.get(self.detail), 'Private history note')

    def test_search_filters_and_pagination(self):
        archived = create_member('ARCHIVED')
        change_status(archived.pk, user=self.admin, version=0, status='archived', notes='Archive')
        listing = reverse('members:list')
        self.assertEqual(self.client.get(listing).context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(listing, {'status': 'archived'}).context['page_obj'].object_list[0].pk, archived.pk)
        self.assertEqual(self.client.get(listing, {'status': '', 'q': 'MEM-001'}).context['page_obj'].paginator.count, 1)
        for number in range(21):
            create_member(f'PAGE-{number}')
        page = self.client.get(listing, {'page': 2}).context['page_obj']
        self.assertEqual(page.number, 2)
        self.assertEqual(len(page), 2)

    def test_csrf_and_get_requests_cannot_change_state(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.edit, self.data).status_code, 403)
        self.assertEqual(client.post(self.detail, {'status': 'archived'}).status_code, 403)
        self.client.get(self.detail, {'status': 'archived', 'version': 0})
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_member_content_is_escaped_and_not_public(self):
        self.client.post(self.edit, {**self.data, 'full_name': '<script>alert(1)</script>'})
        response = self.client.get(self.detail)
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(Client().get(reverse('core:home')), 'Test address, Santolan')

    def test_document_permission_ownership_download_and_missing_file(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            requirement = MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(name='Proof'))
            document = MembershipApplicationDocument.objects.create(application=self.member.application,
                requirement=requirement, label='Proof', file=pdf(), content_type='application/pdf', size=25)
            url = reverse('members:document', args=[self.member.pk, document.pk])
            self.client.force_login(self.viewer)
            self.assertEqual(self.client.get(url).status_code, 403)
            grant(self.viewer, 'documents.view_membershipapplicationdocument')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
            self.assertIn('no-store', response['Cache-Control'])
            self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
            self.assertEqual(MemberEvent.objects.get().action, 'document_downloaded')
            other = create_member('OTHER')
            self.assertEqual(self.client.get(reverse('members:document', args=[other.pk, document.pk])).status_code, 404)
            Path(document.file.path).unlink()
            self.assertEqual(self.client.get(url).status_code, 404)
