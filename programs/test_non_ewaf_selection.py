"""Owner-confirmed unlimited, eligibility-only selection; disposable fixtures only."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceCase, AssistanceLog, AssistanceRelease
from assistance.services import AUTO_SELECTION_POLICY, VIEW_PERMISSIONS, review_eligibility
from assistance.tests import review_data, seed_statuses
from announcements.certificate_delivery import certificate_context, deliver_certificate, deliver_pending, retry_certificates
from announcements.certificate_models import SelectionCertificateEmail, SelectionCertificateAttempt, certificate_write
from announcements.models import Announcement
from announcements.recorded_results import publish_recorded_results, recorded_preview
from members.tests import create_member
from membership.tests import grant
from ewaf.test_source_writers import SourceHelpers
from .forms import ProgramSetupForm
from .models import Program, ProgramApplication
from .services import change_publication, save_program
from .tests import create_program, program_data
from .testsupport import application_fixture, private_media


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   CERTIFICATE_RESEND_ENABLED=False, CERTIFICATE_EMAIL_BACKGROUND=False)
class NonEWAFSelectionTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('SYNTHETIC-ELIGIBILITY')
        self.program = create_program(ewaf_applicable=False, slots=1, eligible_disability_types=[])
        self.application = application_fixture(self.program, create_member('SYNTHETIC-UNLIMITED-1'))
        intake = self.application.member.application
        intake.decided_by = self.admin
        intake.save(update_fields=['decided_by'])

    def review(self, application=None, **changes):
        application = application or self.application
        return review_eligibility(application.pk, user=self.admin, data=review_data(application, **changes))

    def publish(self):
        plan = recorded_preview(self.program.pk, user=self.admin)
        return publish_recorded_results(self.program.pk, user=self.admin,
            expected=plan['expected'], version=plan['version'])

    def test_non_ewaf_creation_discards_slot_limit_and_publishes_without_optional_text(self):
        for slots in (None, '', 7, 'invalid ignored value'):
            with self.subTest(slots=slots):
                program = save_program(user=self.admin, setup_only=True,
                    data=program_data(ewaf_applicable=False, slots=slots, description='', benefit=''))
                self.assertIsNone(program.slots)
                self.assertIsNone(program.slot_limit)
                self.assertEqual(program.capacity_label, 'Unlimited')
                change_publication(program.pk, user=self.admin, version=program.version, action='published')
                program.refresh_from_db()
                self.assertEqual(program.status, 'published')
                self.assertTrue(program.registration_available)

    def test_ewaf_requires_slots_to_publish_but_incomplete_draft_can_save(self):
        program = save_program(user=self.admin, setup_only=True,
            data=program_data(ewaf_applicable=True, slots=''))
        self.assertEqual(program.status, 'draft')
        self.assertIn('slots', program.publication_errors())
        with self.assertRaises(ValidationError):
            change_publication(program.pk, user=self.admin, version=program.version, action='published')
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')
        self.assertIsNone(program.policy_authorized_at)
        program = save_program(pk=program.pk, user=self.admin, setup_only=True,
            data=program_data(ewaf_applicable=True, slots=5, version=program.version))
        self.assertEqual(program.slot_limit, 5)
        self.assertNotIn('slots', program.publication_errors())

    def test_retained_non_ewaf_slot_count_is_history_only_and_edit_does_not_erase_it(self):
        form = ProgramSetupForm(program_data(ewaf_applicable=False, slots='',
            eligible_disability_types=[], version=self.program.version), instance=self.program)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.fields['slots'].disabled)
        self.assertFalse(form.fields['slots'].required)
        self.assertEqual(form.cleaned_data['slots'], 1)
        self.assertIsNone(self.program.slot_limit)

    def test_every_eligible_non_ewaf_applicant_is_selected_while_registration_is_open(self):
        other = application_fixture(self.program, create_member('SYNTHETIC-UNLIMITED-2'))
        reviewer = get_user_model().objects.create_user('SYNTHETIC-REVIEWER', is_staff=True)
        grant(reviewer, 'accounts.access_dashboard', *VIEW_PERMISSIONS, 'assistance.review_eligibility')
        self.assertFalse(reviewer.has_perm('assistance.decide_assistance'))
        for application in (self.application, other):
            before_version = application.version
            case = review_eligibility(application.pk, user=reviewer, data=review_data(application))
            application.refresh_from_db()
            self.assertEqual(application.status, 'SELECTED')
            self.assertEqual(application.version, before_version + 1)
            self.assertEqual((case.eligibility_id, case.decision), ('eligible', 'approved'))
            self.assertEqual(case.decided_by, reviewer)
            self.assertEqual(case.decided_at, case.reviewed_at)
            self.assertEqual(application.assistance_history.get().snapshot['automatic_selection'], AUTO_SELECTION_POLICY)
        self.assertGreater(self.program.registration_closes_at, timezone.now())
        self.assertEqual(ProgramApplication.objects.filter(program=self.program, status='SELECTED').count(), 2)
        self.assertFalse(AssistanceRelease.objects.exists())
        from ewaf.operational_models import OperationalDecision
        self.assertFalse(OperationalDecision.objects.exists())

    def test_ewaf_eligibility_keeps_separate_selection_and_does_not_generate_ranking(self):
        program = create_program(ewaf_applicable=True, slots=1, eligible_disability_types=[])
        application = application_fixture(program, create_member('SYNTHETIC-EWAF-1'))
        case = self.review(application)
        application.refresh_from_db()
        self.assertEqual(application.status, 'ELIGIBLE')
        self.assertEqual(case.decision, 'pending')
        self.assertIsNone(case.decided_at)
        self.assertNotIn('automatic_selection', AssistanceLog.objects.get(application=application).snapshot)

    def test_ineligible_and_needs_information_are_never_selected(self):
        for eligibility, result, status in (('review', 'review', 'NEEDS_INFORMATION'),
                                            ('ineligible', 'fail', 'INELIGIBLE')):
            case = self.review(eligibility=eligibility, other_requirements=result)
            self.application.refresh_from_db()
            self.assertEqual(self.application.status, status)
            self.assertEqual(case.decision, 'pending')

    def test_unresolved_reported_information_cannot_be_automatically_selected(self):
        from .application_workflow import CONTRACT
        from .review_forms import ApplicationDecisionForm
        from .review_services import review_submitted_application
        self.application.source_snapshot['application_confirmation'] = {
            'contract': CONTRACT, 'current_information': 'changed', 'confirm_information': True,
            'change_details': 'Synthetic household change awaiting evidence review.'}
        self.application.save(update_fields=['source_snapshot'])
        form = ApplicationDecisionForm(application=self.application)
        with self.assertRaisesMessage(ValidationError, 'Review and save the reported changes'):
            review_submitted_application(self.application.pk, user=self.admin,
                data={**form.initial, 'eligibility': 'eligible', 'notes': ''})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'PHOTO_VERIFIED')
        self.assertFalse(AssistanceCase.objects.exists())

    def test_automatic_selection_is_readable_in_audit_and_approval_filter(self):
        self.review()
        self.client.force_login(self.admin)
        label = 'Member marked eligible and automatically selected'
        page = self.client.get(reverse('admin:admin_logentry_changelist'),
            {'activity': label, 'kind': 'approval'})
        self.assertContains(page, label)
        self.assertEqual(page.context['page'].paginator.count, 1)

    def test_permissions_stale_versions_and_failed_audit_cannot_partially_select(self):
        viewer = get_user_model().objects.create_user('SYNTHETIC-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *VIEW_PERMISSIONS)
        data = review_data(self.application)
        with self.assertRaises(PermissionDenied):
            review_eligibility(self.application.pk, user=viewer, data=data)
        with self.assertRaises(ValidationError):
            self.review(version=data['version'] + 1)
        with patch('assistance.services.record_log', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.review()
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'PHOTO_VERIFIED')
        self.assertEqual(self.application.version, data['version'])
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertFalse(AssistanceLog.objects.exists())

    def test_review_and_publish_has_selected_results_without_certificate_documents_or_emails(self):
        self.review()
        with patch('announcements.certificate_delivery.certificate_pdfs') as pdf, patch(
                'announcements.certificate_delivery.kick_delivery') as kick:
            with self.captureOnCommitCallbacks(execute=True):
                item = self.publish()
        self.assertEqual(item.status, 'published')
        self.assertEqual(len(item.result_revision.public_payload['rows']), 1)
        self.assertFalse(SelectionCertificateEmail.objects.exists())
        self.assertFalse(SelectionCertificateAttempt.objects.exists())

        pdf.assert_not_called()
        kick.assert_not_called()
        self.assertFalse(AssistanceRelease.objects.exists())
        self.client.force_login(self.admin)
        page = self.client.get(reverse('announcements:prepare_results', args=[self.program.pk]))
        self.assertContains(page, 'No certificate emails are sent for this non-EWAF program.')
        self.assertNotContains(page, 'Retry pending emails')
        self.assertFalse(certificate_context(self.program, self.admin)['certificate_emails_enabled'])

    def test_retained_non_ewaf_certificate_job_cannot_be_retried_or_sent_and_is_unchanged(self):
        self.review()
        item = self.publish()
        with certificate_write():
            job = SelectionCertificateEmail.objects.create(application=self.application,
                revision=item.result_revision, member_name='SYNTHETIC', program_name='SYNTHETIC',
                issued_on=timezone.localdate(), document=b'%PDF synthetic retained history',
                document_sha256='a' * 64, recipient='synthetic@example.invalid',
                subject='Retained certificate', body='Retained body', requested_by_label='SYNTHETIC')
        before = SelectionCertificateEmail.objects.get(pk=job.pk).__dict__.copy()
        before.pop('_state')
        with patch('announcements.certificate_delivery.send_certificate') as send:
            self.assertFalse(deliver_certificate(job.pk))
            deliver_pending()
            with self.assertRaisesMessage(ValidationError, 'not sent for non-EWAF'):
                retry_certificates(self.program.pk, user=self.admin)
        send.assert_not_called()
        after = SelectionCertificateEmail.objects.get(pk=job.pk).__dict__.copy()
        after.pop('_state')
        self.assertEqual(before, after)
        self.assertFalse(SelectionCertificateAttempt.objects.exists())


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class NonEWAFRegisteredSourceTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        NonEWAFSelectionTests.setUp(self)
        self.officer = self.admin
        self.register()

    def test_automatic_selection_passes_native_audit_and_source_generation_validation(self):
        before_generation = self.token()['source_generation']
        case = review_eligibility(self.application.pk, user=self.admin,
            data=review_data(self.application), source_expected=self.expected())
        self.application.refresh_from_db()
        self.assertEqual((self.application.status, case.decision), ('SELECTED', 'approved'))
        self.assertEqual(AssistanceLog.objects.count(), 1)
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assert_transition(before_generation + 1)
