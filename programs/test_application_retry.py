"""Validation returns errors without replacing the browser's selected file controls."""
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from announcements.tests import image_upload
from .models import ProgramApplication, ProgramDocument, ProgramRequirement
from . import test_application_workflow as workflow_tests


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ApplicationRetryTests(TestCase):
    identity = workflow_tests.ConfirmedApplicationTests.identity
    data = workflow_tests.ConfirmedApplicationTests.data

    def setUp(self):
        workflow_tests.ConfirmedApplicationTests.setUp(self)
        self.document = ProgramRequirement.objects.create(program=self.program, label='Required attachment', kind='document')
        self.statement = ProgramRequirement.objects.create(program=self.program, label='Required statement', kind='text')
        self.document_key = f'requirement_{self.document.pk}'
        self.statement_key = f'requirement_{self.statement.pk}'
        self.client.post(self.verify_url, self.identity())

    def post(self, **changes):
        return self.client.post(self.apply_url, self.data(**{
            self.document_key: image_upload(), self.statement_key: 'Submitted statement', **changes,
        }), HTTP_X_PROGRAM_APPLICATION='1', HTTP_ACCEPT='application/json')

    def test_missing_answer_returns_field_errors_and_retry_saves_one_private_document(self):
        response = self.post(**{self.statement_key: ''})
        self.assertEqual(response.status_code, 422)
        self.assertIn(self.statement_key, response.json()['errors'])
        self.assertFalse(ProgramApplication.objects.exists())
        self.assertFalse(ProgramDocument.objects.exists())
        self.assertFalse(any(path.is_file() for path in Path(settings.MEDIA_ROOT).rglob('*')))
        self.assertIn('program_verification', self.client.session)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'redirect': reverse('programs:submitted', args=[self.program.pk])})
        application = ProgramApplication.objects.get()
        document = application.documents.get()
        self.assertEqual(application.answers[str(self.statement.pk)], 'Submitted statement')
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.assertEqual(self.client.get(reverse('programs:document', args=[self.program.pk, application.pk, document.pk])).status_code, 302)
        self.assertNotIn('program_verification', self.client.session)
        # An uncertain network result cannot create a duplicate application.
        self.assertEqual(self.post().status_code, 302)
        self.client.post(self.verify_url, self.identity())
        self.assertEqual(self.post().json()['redirect'], reverse('programs:submitted', args=[self.program.pk]))
        self.assertEqual(ProgramApplication.objects.count(), 1)
        self.assertEqual(ProgramDocument.objects.count(), 1)

    def test_server_only_validation_keeps_the_verification_grant(self):
        response = self.post(confirm_information=False)
        self.assertEqual(response.status_code, 422)
        self.assertIn('confirm_information', response.json()['errors'])
        self.assertIn('program_verification', self.client.session)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_json_transport_still_requires_the_actual_document(self):
        response = self.post(**{self.document_key: ''})
        self.assertEqual(response.status_code, 422)
        self.assertIn(self.document_key, response.json()['errors'])
        self.assertFalse(ProgramApplication.objects.exists())

    def test_json_transport_preserves_csrf_and_stale_version_checks(self):
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session.update(dict(self.client.session))
        session.save()
        self.assertEqual(client.post(self.apply_url, self.data(), HTTP_X_PROGRAM_APPLICATION='1').status_code, 403)
        response = self.post(version=self.program.version - 1)
        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.json()['errors'])
        self.assertFalse(ProgramApplication.objects.exists())

    def test_expired_verification_redirects_for_reverification_without_accepting_uploads(self):
        session = self.client.session
        session.pop('program_verification')
        session.save()
        response = self.post()
        self.assertRedirects(response, self.verify_url)
        self.assertFalse(ProgramDocument.objects.exists())

    def test_non_javascript_submission_still_returns_the_bound_form(self):
        response = self.client.post(self.apply_url, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'programs/apply.html')
        self.assertIn(self.document_key, response.context['form'].errors)
        self.assertContains(response, 'different@example.invalid')

    def test_public_details_show_requirements_and_keep_actual_schedule_and_eligibility(self):
        response = self.client.get(reverse('programs:detail', args=[self.program.pk]))
        for text in ('Purpose and intended benefit',
                     'How review and selection work', 'How program applications work',
                     'Selection method', 'Photo instructions', self.program.benefit):
            self.assertNotContains(response, text)
        for text in (self.document.label, self.statement.label, 'Program requirements',
                     'Schedule &amp; capacity', 'Registration period', 'Program duration',
                     'Planned beneficiary slots', self.program.description):
            self.assertContains(response, text)
