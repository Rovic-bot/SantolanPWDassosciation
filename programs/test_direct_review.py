import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceCase, AssistanceLog
from announcements.tests import image_upload
from membership.tests import grant as permissions
from .models import ProgramApplication, ProgramDocument, ProgramLog, ProgramRequirement, PhotoVerification
from .review_forms import ApplicationDecisionForm
from .review_services import review_submitted_application
from . import test_application_workflow as application_tests


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DirectApplicationReviewTests(TestCase):
    identity = application_tests.ConfirmedApplicationTests.identity
    grant = application_tests.ConfirmedApplicationTests.grant
    data = application_tests.ConfirmedApplicationTests.data
    submit = application_tests.ConfirmedApplicationTests.submit

    def setUp(self):
        application_tests.ConfirmedApplicationTests.setUp(self)
        self.application = self.submit()
        # Retain coverage of applications issued under the earlier mandatory
        # calendar-photo contract, including its rollback and review history.
        from .workflow import store_photo
        self.application.source_snapshot.pop('evidence_policy')
        self.application.save(update_fields=['source_snapshot'])
        store_photo(self.application, image_upload(), [])
        self.url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])
        self.client.force_login(self.admin)

    def decision(self, outcome='eligible', **changes):
        self.application.refresh_from_db()
        form = ApplicationDecisionForm(application=self.application)
        return {'action': 'review_decision', **form.initial, 'eligibility': outcome, 'notes': '', **changes}

    def test_page_shows_submission_without_separate_review_panels_or_required_remarks(self):
        from .forms import snapshot
        written = ProgramRequirement.objects.create(program=self.program, label='Why do you need this assistance?', kind='text')
        consent = ProgramRequirement.objects.create(program=self.program, label='Consent to program conditions', kind='acknowledgement')
        evidence = ProgramRequirement.objects.create(program=self.program, label='Supporting document', kind='document')
        self.application.requirements_snapshot = snapshot(self.program)
        self.application.answers = {str(written.pk): 'Synthetic submitted explanation.', str(consent.pk): True}
        self.application.save(update_fields=['requirements_snapshot', 'answers'])
        document = ProgramDocument.objects.create(application=self.application, requirement=evidence,
            label=evidence.label, file=image_upload(), content_type='image/png', size=100)
        page = self.client.get(self.url)
        self.assertContains(page, 'Submitted photograph')
        self.assertNotContains(page, 'PWD ID number provided')
        self.assertContains(page, 'different@example.invalid')
        self.assertContains(page, 'Synthetic submitted explanation.')
        self.assertContains(page, 'Acknowledged')
        self.assertContains(page, 'Applicant confirmed the submitted information')
        self.assertContains(page, reverse('programs:document', args=[self.program.pk, self.application.pk, document.pk]))
        for removed in ('id="membership-review"', 'id="disability-review"', 'id="photo-review"',
                        'id="program-fit-review"', 'id="program-requirements"', 'name="check_'):
            self.assertNotContains(page, removed)
        self.assertFalse(page.context['decision_form'].fields['notes'].required)
        self.assertEqual(set(page.context['decision_form'].fields),
                         {'version', 'member_version', 'program_version', 'expected_context', 'eligibility', 'notes'})
        if os.environ.get('G12_ARTIFACT_DIR'):
            (Path(os.environ['G12_ARTIFACT_DIR']) / 'direct-review.html').write_bytes(page.content)

    def test_one_click_eligible_records_human_photo_and_automatic_selection(self):
        photo_count = PhotoVerification.objects.count()
        self.assertRedirects(self.client.post(self.url, self.decision()), self.url)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'SELECTED')
        case = AssistanceCase.objects.get(application=self.application)
        self.assertEqual(case.reviewed_by, self.admin)
        self.assertEqual(case.decision, 'approved')
        self.assertEqual(case.eligibility_id, 'eligible')
        self.assertTrue(case.review_notes)
        self.assertEqual(PhotoVerification.objects.count(), photo_count + 1)
        self.assertEqual(self.application.current_photo.reviews.first().outcome, 'VERIFIED')
        self.assertTrue(any(row['key'] == 'admin_review' and row['result'] == 'pass' for row in case.checklist))
        self.assertEqual(AssistanceLog.objects.filter(application=self.application, action='eligibility_reviewed').count(), 1)
        self.assertFalse(self.application.assistance_releases.exists())
        page = self.client.get(self.url)
        self.assertEqual(page.context['review_result'], 'Eligible')

    def test_needs_information_and_ineligible_do_not_fabricate_photo_verification(self):
        count = PhotoVerification.objects.count()
        for outcome, status in (('review', 'NEEDS_INFORMATION'), ('ineligible', 'INELIGIBLE')):
            self.assertRedirects(self.client.post(self.url, self.decision(outcome, notes='Please provide the required qualification evidence.')), self.url)
            self.application.refresh_from_db()
            self.assertEqual(self.application.status, status)
            self.assertEqual(self.application.assistance_case.eligibility_id, outcome)
        self.assertEqual(PhotoVerification.objects.count(), count)
        self.assertEqual(self.application.current_photo.reviews.first().outcome, 'PENDING')

    def test_duplicate_or_stale_application_cannot_record_a_second_decision(self):
        data = self.decision()
        self.client.post(self.url, data)
        before = (PhotoVerification.objects.count(), AssistanceLog.objects.count())
        response = self.client.post(self.url, data)
        self.assertTrue(response.context['decision_form'].errors)
        self.assertEqual((PhotoVerification.objects.count(), AssistanceLog.objects.count()), before)

    def test_member_or_evidence_change_rejects_old_review(self):
        data = self.decision()
        self.member.refresh_from_db()
        self.member.version += 1
        self.member.save(update_fields=['version'])
        self.assertContains(self.client.post(self.url, data), 'changed')
        self.assertFalse(AssistanceCase.objects.exists())
        data = self.decision(expected_context='0' * 64)
        self.assertContains(self.client.post(self.url, data), 'changed')
        self.assertFalse(AssistanceCase.objects.exists())

    def test_required_missing_submission_blocks_eligible_but_allows_needs_information(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Synthetic required answer', kind='text')
        self.application.requirements_snapshot = [{'id': requirement.pk, 'label': requirement.label,
            'kind': 'text', 'instructions': '', 'is_required': True}]
        self.application.save(update_fields=['requirements_snapshot'])
        self.assertContains(self.client.post(self.url, self.decision()), 'required submission is missing')
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertRedirects(self.client.post(self.url, self.decision('review', notes='Provide the required answer.')), self.url)

    def test_missing_photo_blocks_eligible_without_partial_audits(self):
        self.application.current_photo = None
        self.application.save(update_fields=['current_photo'])
        self.assertEqual(self.client.post(self.url, self.decision()).status_code, 200)
        self.assertFalse(AssistanceCase.objects.exists())

    def test_audit_failure_rolls_back_combined_photo_and_eligibility_decision(self):
        before = (self.application.version, PhotoVerification.objects.count(), ProgramLog.objects.count())
        with patch('assistance.services.record_log', side_effect=RuntimeError('Synthetic audit unavailable')):
            with self.assertRaises(RuntimeError):
                review_submitted_application(self.application.pk, user=self.admin, data=self.decision())
        self.application.refresh_from_db()
        self.assertEqual((self.application.version, PhotoVerification.objects.count(), ProgramLog.objects.count()), before)
        self.assertEqual(self.application.status, 'PENDING_PHOTO_VERIFICATION')
        self.assertFalse(AssistanceCase.objects.exists())

    def test_permissions_csrf_and_closed_states_remain_enforced(self):
        data = self.decision()
        user = get_user_model().objects.create_user('synthetic_direct_viewer', is_staff=True)
        permissions(user, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(user)
        self.assertNotContains(self.client.get(self.url), 'id="eligibility-decision-form"')
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.admin)
        self.assertEqual(secured.post(self.url, data).status_code, 403)
        self.client.force_login(self.admin)
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='CLOSED')
        self.assertContains(self.client.post(self.url, self.decision()), 'final or closed')
        self.assertFalse(AssistanceCase.objects.exists())


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DirectReviewConcurrencyTests(TransactionTestCase):
    identity = DirectApplicationReviewTests.identity
    grant = DirectApplicationReviewTests.grant
    data = DirectApplicationReviewTests.data
    submit = DirectApplicationReviewTests.submit
    decision = DirectApplicationReviewTests.decision

    def setUp(self):
        from assistance.tests import seed_statuses
        from scripts.durable_test_runner import require_disposable
        require_disposable()
        seed_statuses()
        application_tests.ConfirmedApplicationTests.setUp(self)
        self.application = self.submit()

    def test_simultaneous_decisions_save_only_once(self):
        data = self.decision()
        barrier = Barrier(2)
        before = PhotoVerification.objects.count()

        def decide():
            try:
                user = get_user_model().objects.get(pk=self.admin.pk)
                barrier.wait(timeout=15)
                review_submitted_application(self.application.pk, user=user, data=data)
                return 'saved'
            except ValidationError:
                return 'stale'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: decide(), range(2)))
        self.assertCountEqual(results, ['saved', 'stale'])
        self.assertEqual(AssistanceLog.objects.filter(action='eligibility_reviewed').count(), 1)
        self.assertEqual(self.application.decision_emails.count(), 1)
        self.assertEqual(PhotoVerification.objects.count(), before)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'SELECTED')
