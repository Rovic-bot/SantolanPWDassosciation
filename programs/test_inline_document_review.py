from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from documents.models import DocumentVerification
from documents.services import file_digest, verify_document
from ewaf.operational_testsupport import OperationalHelpers
from membership.tests import grant


class InlineDocumentReviewTests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational(additional=1)
        self.client.force_login(self.officer)
        self.url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])

    def data(self, **changes):
        latest = self.document.verifications.first()
        fields = {'member_version': self.member.version, 'review_id': latest.pk if latest else 0,
                  'document_digest': file_digest(self.document), **changes}
        return {'action': 'document_review', 'document_id': str(self.document.pk),
                **{f'document-{self.document.pk}-{name}': value for name, value in fields.items()}}

    def needs_review(self, *, expires_on=None):
        return verify_document(self.document.pk, user=self.officer, member_version=self.member.version,
            verified=False, expires_on=expires_on, reason='Fictional document awaiting officer review.')

    def test_review_status_saves_on_applicant_page_and_retains_history(self):
        original = self.needs_review(expires_on=timezone.localdate() + timedelta(days=30))
        count = self.document.verifications.count()
        page = self.client.get(self.url)
        self.assertNotContains(page, 'Review document</a>')
        self.assertNotContains(page, 'document-dialog-')
        self.assertNotContains(page, f'id="review-document-{self.document.pk}"')
        self.assertNotContains(page, 'Needs Review</button>')
        self.assertContains(page, reverse('members:document', args=[self.member.pk, self.document.pk]))
        data = self.data(verified='no', expires_on='', reason='Forged text must not replace the action audit.')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header('Location'))
        self.assertTrue(response.context['document_review_saved'])
        reviewed = next(d for d in response.context['membership_documents'] if d.pk == self.document.pk)
        self.assertEqual(reviewed.review_button_label, 'Review')
        self.assertTrue(self.document.verifications.first().verified)
        self.assertEqual(self.document.verifications.count(), count + 1)
        self.assertEqual(self.document.verifications.first().expires_on, original.expires_on)
        self.assertEqual(self.document.verifications.first().reason, 'Document marked reviewed from the applicant page.')
        original.refresh_from_db()
        self.assertFalse(original.verified)
        self.assertEqual(self.document.verifications.first().reviewer_id, self.officer.pk)
        # A retry or repeated click is idempotent and does not invalidate evidence again.
        self.assertTrue(self.client.post(self.url, data).context['document_review_saved'])
        self.assertEqual(self.document.verifications.count(), count + 1)
        self.assertEqual(self.client.get(reverse('documents:review', args=[self.document.pk])).status_code, 200)

    def test_review_requires_current_member_document_and_review(self):
        self.needs_review()
        before = self.document.verifications.count()
        for values in ({'member_version': self.member.version + 1}, {'review_id': 0},
                       {'document_digest': '0' * 64}, {'member_version': ''}):
            response = self.client.post(self.url, self.data(**values))
            self.assertFalse(response.context['document_review_saved'])
            self.assertNotContains(response, 'document-dialog-')
            self.assertContains(response, 'role="alert"')
            self.assertEqual(self.document.verifications.count(), before)

    def test_expired_or_unavailable_document_is_not_marked_reviewed(self):
        self.needs_review(expires_on=timezone.localdate() - timedelta(days=1))
        before = self.document.verifications.count()
        # A client cannot remove a recorded expiry via the quick action.
        response = self.client.post(self.url, self.data(expires_on=''))
        self.assertFalse(response.context['document_review_saved'])
        self.assertContains(response, 'An expired document cannot be marked current and verified.')
        self.assertEqual(self.document.verifications.count(), before)
        data = self.data()
        with patch('documents.services.file_digest', return_value=None):
            response = self.client.post(self.url, data)
        self.assertFalse(response.context['document_review_saved'])
        self.assertContains(response, 'The private document is unavailable.')
        self.assertEqual(self.document.verifications.count(), before)

    def test_cross_member_document_and_invalid_identifiers_cannot_be_reviewed(self):
        before = DocumentVerification.objects.count()
        for document_id in (str(self.helpers[1].document.pk), 'invalid', ''):
            response = self.client.post(self.url, {**self.data(), 'document_id': document_id})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(DocumentVerification.objects.count(), before)

    def test_permissions_csrf_and_hidden_controls(self):
        viewer = get_user_model().objects.create_user('document_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication',
              'members.view_member', 'documents.view_membershipapplicationdocument')
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url), 'data-document-review-form')
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.officer)
        self.assertEqual(protected.post(self.url, self.data()).status_code, 403)
        self.assertEqual(Client().post(self.url, self.data()).status_code, 302)

    def test_source_change_blocks_stale_selection_and_preserves_scores(self):
        self.lock_policy()
        run = self.calculate()
        old_scores = deepcopy(run.calculations)
        self.needs_review()
        response = self.client.post(self.url, self.data())
        self.assertTrue(response.context['document_review_saved'])
        self.assertEqual(response.context['review_result'], 'Review needed')
        with self.assertRaises(ValidationError):
            self.choose(run)
        run.refresh_from_db()
        self.assertEqual(run.calculations, old_scores)
        self.application.refresh_from_db()
        self.assertEqual(self.application.assistance_case.eligibility_id, 'eligible')

    def test_failed_audit_does_not_save_verification(self):
        self.needs_review()
        before = self.document.verifications.count()
        with patch('members.services.record_event', side_effect=ValidationError('Fictional audit failure')):
            response = self.client.post(self.url, self.data())
        self.assertFalse(response.context['document_review_saved'])
        self.assertEqual(self.document.verifications.count(), before)
