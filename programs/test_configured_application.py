"""Owner-authorized two-field checking and program-configured evidence."""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from assistance.models import AssistanceCase
from ewaf.evidence import source_context
from ewaf.readiness import evaluate
from .forms import CorrectionForm
from .models import ProgramApplication, ProgramRequirement, PhotoVerification
from .review_context import identity_status
from .review_forms import ApplicationDecisionForm
from .review_services import review_submitted_application
from .services import submit_application
from . import test_application_workflow as workflow_tests
from .workflow import CONFIGURED_EVIDENCE, correct_application, require_verified_photo


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ConfiguredApplicationTests(TestCase):
    setUp = workflow_tests.ConfirmedApplicationTests.setUp
    identity = workflow_tests.ConfirmedApplicationTests.identity
    grant = workflow_tests.ConfirmedApplicationTests.grant
    data = workflow_tests.ConfirmedApplicationTests.data
    submit = workflow_tests.ConfirmedApplicationTests.submit

    def decide(self, application):
        return review_submitted_application(application.pk, user=self.admin,
            data={**ApplicationDecisionForm(application=application).initial, 'eligibility': 'eligible', 'notes': ''})

    def test_no_photo_requirement_can_be_reviewed_without_fabricating_verification(self):
        application = self.submit()
        self.assertEqual(application.source_snapshot['evidence_policy'], CONFIGURED_EVIDENCE)
        self.assertIsNone(require_verified_photo(application))
        self.assertEqual(identity_status(application, self.admin), 'Not required')
        self.decide(application)
        application.refresh_from_db()
        self.assertEqual(application.status, 'ELIGIBLE')
        self.assertIsNone(application.current_photo_id)
        self.assertFalse(PhotoVerification.objects.exists())
        self.assertEqual(application.assistance_case.decision, 'pending')
        context = source_context(application)
        self.assertIs(context['calendar_photo_required'], False)
        self.assertIsNone(context['photo'])
        result = evaluate(application, context=context)
        self.assertNotIn('IDENTITY_REVIEW_REQUIRED', str(result))
        self.assertFalse(application.assistance_releases.exists())

    def test_configured_calendar_upload_is_required_private_and_reviewed_as_submission(self):
        item = ProgramRequirement.objects.create(program=self.program,
            label='Current calendar photo', kind='document', is_required=True,
            instructions='Upload a current photo holding a calendar.')
        with self.assertRaises(ValidationError):
            self.submit()
        self.assertFalse(ProgramApplication.objects.exists())
        application = submit_application(self.program.pk, grant=self.grant(), data=self.data(),
            files=MultiValueDict({f'requirement_{item.pk}': [image_upload()]}))
        document = application.documents.get()
        self.assertEqual(document.requirement_id, item.pk)
        self.assertIsNone(application.current_photo_id)
        url = reverse('programs:document', args=[self.program.pk, application.pk, document.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.decide(application)
        case = AssistanceCase.objects.get(application=application)
        check = next(row for row in case.checklist if row['key'] == str(item.pk))
        self.assertEqual(check['result'], 'pass')
        self.assertEqual(case.reviewed_by, self.admin)
        self.assertFalse(PhotoVerification.objects.exists())

    def test_missing_configured_file_still_blocks_eligibility(self):
        item = ProgramRequirement.objects.create(program=self.program, label='Required evidence', kind='document')
        application = submit_application(self.program.pk, grant=self.grant(), data=self.data(),
            files=MultiValueDict({f'requirement_{item.pk}': [image_upload()]}))
        document = application.documents.get()
        document.file.storage.delete(document.file.name)
        with self.assertRaises(ValidationError):
            self.decide(application)
        self.assertFalse(AssistanceCase.objects.exists())

    def test_new_application_correction_preserves_not_required_policy(self):
        item = ProgramRequirement.objects.create(program=self.program, label='Applicant statement', kind='text')
        application = self.submit(**{f'requirement_{item.pk}': 'First submitted answer'})
        form = CorrectionForm(application=application)
        self.assertNotIn('calendar_photo', form.fields)
        correct_application(application.pk, user=self.admin, data={'version': application.version,
            'reason': 'Synthetic Help Desk correction.', f'requirement_{item.pk}': 'Corrected answer'}, files=MultiValueDict())
        application.refresh_from_db()
        self.assertEqual(application.answers[str(item.pk)], 'Corrected answer')
        self.assertEqual(application.status, 'ELIGIBILITY_REVIEW')
        self.assertEqual(application.source_snapshot['evidence_policy'], CONFIGURED_EVIDENCE)
        self.assertFalse(PhotoVerification.objects.exists())

    def test_old_applications_keep_their_photo_gate_and_context_shape(self):
        application = self.submit()
        application.source_snapshot.pop('evidence_policy')
        application.save(update_fields=['source_snapshot'])
        with self.assertRaises(ValidationError):
            require_verified_photo(application)
        self.assertIn('calendar_photo', CorrectionForm(application=application).fields)
        self.assertNotIn('calendar_photo_required', source_context(application))
        self.assertIn('IDENTITY_REVIEW_REQUIRED', str(evaluate(application)))

    def test_photo_queue_omits_new_not_required_cases_but_keeps_missing_legacy_photos(self):
        application = self.submit()
        self.client.force_login(self.admin)
        url = reverse('programs:photo_queue')
        self.assertEqual(self.client.get(url).context['page_obj'].paginator.count, 0)
        application.source_snapshot.pop('evidence_policy')
        application.save(update_fields=['source_snapshot'])
        self.assertEqual(self.client.get(url).context['page_obj'].paginator.count, 1)

    def test_invalid_csrf_is_still_rejected_and_review_audit_rolls_back(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.verify_url, self.identity()).status_code, 403)
        application = self.submit()
        with patch('assistance.services.record_log', side_effect=RuntimeError('Synthetic audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.decide(application)
        application.refresh_from_db()
        self.assertEqual(application.status, 'ELIGIBILITY_REVIEW')
        self.assertFalse(AssistanceCase.objects.exists())

    def test_applicant_review_excludes_member_profile_and_unrelated_membership_documents(self):
        from documents.models import DocumentType, MembershipApplicationDocument, MembershipDocumentRequirement
        self.member.application.registration_profile = {'profile_kind': 'association_pdf_v1',
            'profile_sections': [('Original private family information', [('Guardian', 'PRIVATE GUARDIAN')])]}
        self.member.application.save(update_fields=['registration_profile'])
        self.member.registration_profile = self.member.application.registration_profile
        self.member.save(update_fields=['registration_profile'])
        requirement = MembershipDocumentRequirement.objects.create(capture_key='private_registration',
            document_type=DocumentType.objects.create(name='Private registration attachment'))
        MembershipApplicationDocument.objects.create(application=self.member.application, requirement=requirement,
            label='PRIVATE REGISTRATION DOCUMENT', file=image_upload(), content_type='image/png', size=100)
        application = self.submit()
        self.client.force_login(self.admin)
        page = self.client.get(reverse('programs:application_detail', args=[self.program.pk, application.pk]))
        self.assertContains(page, 'different@example.invalid')
        self.assertContains(page, reverse('members:detail', args=[self.member.pk]))
        for value in ('PRIVATE GUARDIAN', 'Original private family information', 'PRIVATE REGISTRATION DOCUMENT',
                      'Household and assistance', 'Submitted photograph', 'PWD ID number', 'Member documents on file'):
            self.assertNotContains(page, value)
        self.assertNotIn('profile_sections', page.context)
        self.assertEqual(page.context['membership_documents'], [])
