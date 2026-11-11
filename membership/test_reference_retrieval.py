"""Retired list redirects and protected access to retained onsite records."""
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from documents.models import DocumentType, MembershipApplicationDocument, MembershipDocumentRequirement
from members.models import Member
from membership.forms import ApplicationForm
from membership.models import MembershipApplication, MembershipEvent, MembershipSettings
from membership.services import decide_application, record_verification, submit_application
from membership.tests import grant, onsite_profile, pdf


class ReferenceRetrievalTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory(prefix='phase2a-reference-media-')
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        MembershipSettings.objects.update_or_create(pk=1, defaults={
            'registration_open': False, 'prpwd_url': 'https://registry.example.test/verify'})
        self.requirement = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Synthetic private proof'))
        self.encoder = get_user_model().objects.create_superuser('synthetic_encoder')
        self.viewer = get_user_model().objects.create_user('synthetic_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'membership.view_membershipapplication')
        self.pending = self.application('Pending', 'SYNTHETIC-REF-001')
        self.approved = self.application('Approved', 'SYNTHETIC-REF-002')
        self.rejected = self.application('Rejected', 'SYNTHETIC-REF-003')
        self.approved = record_verification(self.approved.reference, user=self.encoder,
            version=0, verified=True, notes='Synthetic onsite verification.')
        self.approved = decide_application(self.approved.reference, user=self.encoder,
            version=1, decision='approved', notes='Synthetic authorized membership decision.')
        self.rejected = decide_application(self.rejected.reference, user=self.encoder,
            version=0, decision='rejected', notes='Synthetic final decision.')
        self.url = reverse('membership:list')
        self.detail = reverse('membership:detail', args=[self.pending.reference])
        self.document = self.pending.documents.get()
        self.download = reverse('membership:document', args=[self.document.pk])
        self.client.force_login(self.viewer)

    def application(self, first_name, control_number):
        form = ApplicationForm({**onsite_profile(), 'first_name': first_name,
            'control_number': control_number,
            'submission_token': ApplicationForm().initial['submission_token']},
            MultiValueDict({f'document_{self.requirement.pk}': [pdf()]}))
        self.assertTrue(form.is_valid(), form.errors)
        return submit_application(form, user=self.encoder)

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values())
                for model in (MembershipApplication, Member, MembershipApplicationDocument, MembershipEvent)}

    def test_retired_list_redirects_and_existing_details_remain_accessible(self):
        for application in (self.pending, self.approved, self.rejected):
            with self.subTest(status=application.status):
                response = self.client.get(self.url, {'reference': str(application.reference)})
                self.assertRedirects(response, reverse('membership:review_home'))
                detail = reverse('membership:detail', args=[application.reference])
                self.assertContains(self.client.get(detail), application.full_name)
                self.assertIn('no-store', response['Cache-Control'])

    def test_old_reference_queries_are_not_forwarded_or_reflected(self):
        for value in ('', 'not-a-reference', '<script>alert(1)</script>',
                      str(self.pending.reference) + 'x', 'a' * 1000,
                      f'  {str(self.pending.reference).upper()}  ', self.pending.reference.hex):
            with self.subTest(value=value[:45]):
                response = self.client.get(self.url, {'reference': value})
                self.assertRedirects(response, reverse('membership:review_home'))
                self.assertNotContains(response, self.pending.full_name, status_code=302)
                self.assertNotContains(response, '<script>alert(1)</script>', status_code=302)

    def test_unknown_reference_redirects_and_missing_detail_is_still_404(self):
        response = self.client.get(self.url, {'reference': str(uuid4())})
        self.assertRedirects(response, reverse('membership:review_home'))
        for application in (self.pending, self.approved, self.rejected):
            self.assertNotContains(response, application.full_name, status_code=302)
        self.assertEqual(self.client.get(reverse('membership:detail', args=[uuid4()])).status_code, 404)

    def test_retired_list_drops_combined_reference_name_and_status_filters(self):
        response = self.client.get(self.url, {'reference': str(self.approved.reference),
            'q': self.pending.full_name, 'status': 'pending'})
        self.assertRedirects(response, reverse('membership:review_home'))
        self.assertRedirects(self.client.get(self.url), reverse('membership:review_home'))

    def test_repeated_get_and_head_do_not_create_or_change_records_or_history(self):
        before = self.snapshot()
        for _ in range(3):
            self.assertRedirects(self.client.get(self.url, {'reference': str(self.approved.reference)}), reverse('membership:review_home'))
            self.assertRedirects(self.client.head(self.url, {'reference': str(self.pending.reference)}), reverse('membership:review_home'))
            self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.client.post(self.url, {'reference': str(self.pending.reference)}).status_code, 405)
        self.assertEqual(before, self.snapshot())

    def test_anonymous_cannot_search_open_details_or_download_with_known_identifiers(self):
        self.client.logout()
        for route, data in ((self.url, {'reference': str(self.pending.reference)}), (self.detail, {}), (self.download, {})):
            response = self.client.get(route, data)
            self.assertEqual(response.status_code, 302)
            self.assertNotContains(response, self.pending.full_name, status_code=302)
            self.assertNotIn(b'%PDF', response.content)

    def test_dashboard_and_membership_permissions_are_both_required_before_lookup(self):
        for permissions in ((), ('accounts.access_dashboard',), ('membership.view_membershipapplication',)):
            user = get_user_model().objects.create_user('restricted_' + str(len(permissions)) + str(uuid4()), is_staff=True)
            grant(user, *permissions)
            self.client.force_login(user)
            for value in (str(self.pending.reference), str(uuid4()), 'invalid'):
                response = self.client.get(self.url, {'reference': value})
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(self.pending.full_name.encode(), response.content)
                self.assertNotIn(str(self.pending.reference).encode(), response.content)
            self.assertEqual(self.client.get(self.detail).status_code, 403)
            self.assertEqual(self.client.get(self.download).status_code, 403)

    def test_nonstaff_inactive_and_revoked_permission_sessions_cannot_retrieve(self):
        for field in ('is_staff', 'is_active'):
            user = get_user_model().objects.get(pk=self.viewer.pk)
            setattr(user, field, False)
            user.save(update_fields=[field])
            self.assertIn(self.client.get(self.url, {'reference': str(self.pending.reference)}).status_code, (302, 403))
            self.assertIn(self.client.get(self.detail).status_code, (302, 403))
            setattr(user, field, True)
            user.save(update_fields=[field])
            self.client.force_login(user)
        self.viewer.user_permissions.remove(Permission.objects.get(
            content_type__app_label='membership', codename='view_membershipapplication'))
        self.assertEqual(self.client.get(self.url, {'reference': str(self.pending.reference)}).status_code, 403)
        self.assertEqual(self.client.get(self.detail).status_code, 403)

    def test_document_permission_is_separate_and_rechecked_after_revocation(self):
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertEqual(self.client.get(self.download).status_code, 403)
        before_events = self.pending.events.count()
        grant(self.viewer, 'documents.view_membershipapplicationdocument')
        response = self.client.get(self.download)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'%PDF-1.4', b''.join(response.streaming_content))
        self.assertTrue(response.closed)  # The test client's iterator closes it safely.
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', response['Content-Security-Policy'])
        self.assertEqual(self.pending.events.count(), before_events + 1)
        self.assertEqual(self.pending.events.last().action, 'document_downloaded')
        self.viewer.user_permissions.remove(Permission.objects.get(
            content_type__app_label='documents', codename='view_membershipapplicationdocument'))
        self.assertEqual(self.client.get(self.download).status_code, 403)
        self.assertEqual(self.pending.events.count(), before_events + 1)

    def test_document_audit_failure_prevents_delivery_and_preserves_records(self):
        grant(self.viewer, 'documents.view_membershipapplicationdocument')
        before = self.snapshot()
        with patch('membership.views.record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'Synthetic audit failure'):
                self.client.get(self.download)
        self.assertEqual(before, self.snapshot())

    def test_view_permission_does_not_allow_verification_or_decision(self):
        before = self.snapshot()
        for action in ('verify', 'decide'):
            self.assertEqual(self.client.post(self.detail, {'action': action,
                'version': 0, 'verified': 'yes', 'decision': 'approved', 'notes': 'Not authorized.'}).status_code, 403)
        self.assertEqual(before, self.snapshot())

    def test_public_guidance_and_retired_receipt_do_not_expose_reference_results(self):
        visitor = Client()
        response = visitor.get(reverse('core:membership'), {'reference': str(self.pending.reference)})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.pending.full_name)
        self.assertNotContains(response, str(self.pending.reference))
        self.assertEqual(visitor.post(reverse('core:membership'), {'reference': str(self.pending.reference)}).status_code, 405)
        response = visitor.get(reverse('membership:submitted'), {'reference': str(self.pending.reference)}, follow=True)
        self.assertNotContains(response, self.pending.full_name)
        self.assertNotContains(response, str(self.pending.reference))
