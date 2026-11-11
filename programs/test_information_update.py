"""Reported changes are reviewed through audited current-member edits."""
import os
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from assistance.models import AssistanceCase
from documents.models import DocumentVerification
from members import test_registration_edit as member_tests
from members.models import Member, MemberEvent
from membership.tests import grant
from . import application_workflow as workflow, information_confirmation as information
from .information_forms import information_update_form
from .models import ProgramApplication, ProgramLog, PhotoVerification
from .review_forms import ApplicationDecisionForm
from .services import submit_application
from .tests import create_program
from .testsupport import private_media


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ReportedInformationUpdateTests(TestCase):
    def setUp(self):
        private_media(self)
        member_tests.MemberRegistrationEditTests.setUp(self)
        self.intake = self.application
        self.intake.decided_by = self.actor
        self.intake.decided_at = timezone.now()
        self.intake.save(update_fields=['decided_by', 'decided_at'])
        self.member.refresh_from_db()
        self.program = create_program(policy_authorized_by=self.actor)
        verified = workflow.verify(self.program.pk, version=self.program.version,
            control_number=self.member.control_number, full_name=self.member.full_name)[0]
        self.application = submit_application(self.program.pk, grant=verified, data={
            'version': self.program.version, 'applicant_name': self.member.full_name,
            'applicant_contact': self.member.contact_number, 'applicant_email': 'synthetic@example.invalid',
            'pwd_id_number': 'SYNTHETIC-ID', 'current_information': 'changed',
            'change_details': 'My employment information has changed.', 'confirm_information': True},
            files=MultiValueDict())
        # Exercise retained historical reports; new submissions no longer ask
        # for or accept a change declaration.
        report = self.application.source_snapshot['application_confirmation']
        report.pop('information_basis')
        report.update(current_information='changed', change_details='My employment information has changed.')
        self.application.status = 'NEEDS_INFORMATION'
        self.application.save(update_fields=['source_snapshot', 'status'])
        self.url = reverse('programs:information_review', args=[self.application.pk])
        self.detail_url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])

    def update_data(self, **changes):
        self.application.refresh_from_db()
        form = information_update_form(application=self.application)
        values = {name: form[name].value() for name in form.fields}
        return {name: '' if value is None else value for name, value in values.items()} | changes

    def eligible(self):
        self.application.refresh_from_db()
        form = ApplicationDecisionForm(application=self.application)
        return self.client.post(self.detail_url,
            {'action': 'review_decision', **form.initial, 'eligibility': 'eligible', 'notes': ''})

    def test_editor_displays_report_and_current_values_without_evidence_picker(self):
        before = (MemberEvent.objects.count(), ProgramLog.objects.count(), self.application.version)
        response = self.client.get(self.url)
        self.assertContains(response, 'My employment information has changed.')
        self.assertContains(response, 'Save reviewed information')
        self.assertNotContains(response, 'Accepted supporting evidence')
        self.assertNotContains(response, 'name="evidence"')
        self.assertNotContains(response, 'name="confirmed"')
        form = response.context['form']
        self.assertEqual(form['employment_status'].value(), self.member.employment_status)
        self.assertEqual(form['contact_number'].value(), self.member.contact_number)
        self.assertFalse(form.fields['notes'].required)
        self.assertEqual(form.document_fields, [])
        self.assertEqual(self.client.get(self.detail_url).context['member_edit_url'], self.url)
        self.assertEqual(before, (MemberEvent.objects.count(), ProgramLog.objects.count(), self.application.version))
        if os.environ.get('G12_ARTIFACT_DIR'):
            (Path(os.environ['G12_ARTIFACT_DIR']) / 'information-update.html').write_bytes(response.content)

    @override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True)
    def test_edit_resolves_report_without_documents_or_scoring_and_then_allows_eligible(self):
        original = deepcopy(self.application.source_snapshot)
        intake_original = deepcopy(self.intake.registration_profile)
        photo_reviews = PhotoVerification.objects.count()
        self.assertFalse(information.confirmation_context(self.application)['resolved'])
        self.program.ewaf_applicable = True
        self.program.save(update_fields=['ewaf_applicable'])
        self.assertFalse(DocumentVerification.objects.exists())
        data = self.update_data(employment_status='self_employed', contact_number='09171234567')
        with patch('ewaf.operational_services.latest_configuration', side_effect=AssertionError('Scoring is not a profile edit prerequisite')):
            response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.status_code == 200 else '')
        self.assertRedirects(response, self.detail_url)
        self.member.refresh_from_db()
        self.application.refresh_from_db()
        self.intake.refresh_from_db()
        self.assertEqual(self.member.employment_status, 'self_employed')
        self.assertEqual(self.member.contact_number, '09171234567')
        self.assertEqual(self.member.version, 1)
        self.assertEqual(self.intake.registration_profile, intake_original)
        self.assertEqual(self.application.source_snapshot, original)
        self.assertTrue(information.confirmation_context(self.application)['resolved'])
        self.assertEqual(PhotoVerification.objects.count(), photo_reviews)
        review = self.application.history.get(action=information.ACTION)
        self.assertEqual(review.changes['method'], 'member_update')
        self.assertEqual(review.changes['member_event'], self.member.events.get(action='profile_updated').pk)
        self.assertEqual(review.actor, self.actor)
        self.assertRedirects(self.eligible(), self.detail_url)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')
        self.assertEqual(AssistanceCase.objects.get(application=self.application).decision, 'pending')
        self.assertFalse(self.application.criterion_assessments.exists())
        self.assertFalse(DocumentVerification.objects.exists())

    def test_already_current_record_can_be_reviewed_without_fake_member_edit(self):
        self.assertRedirects(self.client.post(self.url, self.update_data()), self.detail_url)
        self.member.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        self.assertFalse(MemberEvent.objects.exists())
        self.assertTrue(information.confirmation_context(self.application)['resolved'])
        self.assertIsNone(self.application.history.get(action=information.ACTION).changes['member_event'])
        self.assertRedirects(self.eligible(), self.detail_url)

    def test_invalid_values_and_duplicate_or_stale_forms_do_not_overwrite(self):
        data = self.update_data(employment_status='employed')
        self.assertEqual(self.client.post(self.url, data | {'household_members': '0'}).status_code, 200)
        self.assertFalse(MemberEvent.objects.exists())
        self.assertRedirects(self.client.post(self.url, data), self.detail_url)
        self.assertContains(self.client.post(self.url, data), 'changed. Reload')
        self.assertEqual(self.application.history.filter(action=information.ACTION).count(), 1)
        self.assertEqual(MemberEvent.objects.count(), 1)

    def test_member_edit_and_resolution_roll_back_if_application_audit_fails(self):
        before = Member.objects.values().get(pk=self.member.pk)
        app_before = ProgramApplication.objects.values().get(pk=self.application.pk)
        with patch('programs.services.record_log', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                information.update_reported_information(self.application.pk, user=self.actor,
                    data=self.update_data(employment_status='employed'))
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertEqual(ProgramApplication.objects.values().get(pk=self.application.pk), app_before)
        self.assertFalse(MemberEvent.objects.exists())

    def test_later_member_change_invalidates_report_review(self):
        self.client.post(self.url, self.update_data())
        self.application.refresh_from_db()
        self.assertTrue(information.confirmation_context(self.application)['resolved'])
        Member.objects.filter(pk=self.member.pk).update(contact_number='09175554444', version=1)
        self.application.refresh_from_db()
        self.assertFalse(information.confirmation_context(self.application)['resolved'])
        self.assertRedirects(self.eligible(), self.detail_url)
        self.assertFalse(information.confirmation_context(self.application)['resolved'])

    def test_eligible_does_not_require_member_edit_or_resolution_of_reported_change(self):
        before = Member.objects.values().get(pk=self.member.pk)
        original = deepcopy(self.application.source_snapshot)
        reviewer = get_user_model().objects.create_user('synthetic_eligibility_only', is_staff=True)
        from .review_services import DIRECT_REVIEW_PERMISSIONS
        grant(reviewer, 'accounts.access_dashboard', *DIRECT_REVIEW_PERMISSIONS)
        self.client.force_login(reviewer)
        self.assertFalse(reviewer.has_perm('members.change_member'))
        self.assertRedirects(self.eligible(), self.detail_url)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertFalse(MemberEvent.objects.exists())
        self.assertEqual(self.application.source_snapshot, original)
        self.assertFalse(self.application.history.filter(action=information.ACTION).exists())
        self.assertFalse(information.confirmation_context(self.application)['resolved'])
        case = AssistanceCase.objects.get(application=self.application)
        pending = next(row for row in case.checklist if row['key'] == 'information_change')
        self.assertFalse(pending['required'])
        self.assertEqual(pending['result'], 'review')
        self.assertEqual(case.reviewed_by, reviewer)
        self.assertEqual(case.decision, 'pending')
        page = self.client.get(self.detail_url)
        self.assertEqual(page.context['review_result'], 'Eligible')
        self.assertContains(page, 'You may mark this application Eligible without changing the member record.')
        self.assertNotContains(page, 'before marking this application Eligible')
        # Eligibility does not claim an onsite information change was confirmed.
        with self.assertRaises(ValidationError):
            information.require_resolved(self.application)

    def test_updating_an_eligible_application_returns_it_for_another_human_decision(self):
        self.client.post(self.url, self.update_data())
        self.assertRedirects(self.eligible(), self.detail_url)
        self.assertRedirects(self.client.post(self.url, self.update_data(employment_status='employed')), self.detail_url)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBILITY_REVIEW')
        self.assertEqual(AssistanceCase.objects.get(application=self.application).eligibility_id, 'review')
        self.assertRedirects(self.eligible(), self.detail_url)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')

    def test_edit_permissions_csrf_and_closed_states_are_enforced(self):
        viewer = get_user_model().objects.create_user('synthetic_report_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *information.VIEW,
              'assistance.view_assistancecase', 'assistance.review_eligibility')
        data = self.update_data(employment_status='employed')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.assertNotContains(self.client.get(self.detail_url), 'Review and update member information')
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.actor)
        self.assertEqual(secured.post(self.url, data).status_code, 403)
        self.client.force_login(self.actor)
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='CLOSED')
        self.assertNotContains(self.client.get(self.url), 'id="reported-information-form"')
        with self.assertRaisesMessage(ValidationError, 'return-for-review'):
            information.update_reported_information(self.application.pk, user=self.actor, data=data)
        self.assertFalse(MemberEvent.objects.exists())


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ReportedInformationConcurrencyTests(TransactionTestCase):
    update_data = ReportedInformationUpdateTests.update_data

    def setUp(self):
        from assistance.tests import seed_statuses
        from scripts.durable_test_runner import require_disposable
        require_disposable()
        seed_statuses()
        ReportedInformationUpdateTests.setUp(self)

    def test_simultaneous_profile_reviews_save_one_update_and_one_resolution(self):
        data = self.update_data(employment_status='employed')
        barrier = Barrier(2)

        def save():
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                barrier.wait(timeout=15)
                information.update_reported_information(self.application.pk, user=actor, data=data)
                return 'saved'
            except ValidationError:
                return 'stale'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: save(), range(2)))
        self.assertCountEqual(results, ['saved', 'stale'])
        self.member.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.member.version, 1)
        self.assertEqual(self.member.events.filter(action='profile_updated').count(), 1)
        self.assertEqual(self.application.history.filter(action=information.ACTION).count(), 1)
        self.assertTrue(information.confirmation_context(self.application)['resolved'])
