"""Fictional PDAO files and a disposable database/storage only."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import pdao_services as services
from .pdao_models import PDAORegistration, PDAORegistrationAttachment
from .test_pdao_registration import PDAOHelpers, actor
from .test_pdf_registration import pdao_data
from .test_pdao_review import review_data


def portrait():
    buffer = BytesIO()
    Image.new('RGB', (32, 32), 'white').save(buffer, format='PNG')
    return SimpleUploadedFile('fictional-portrait.png', buffer.getvalue(), content_type='image/png')


def certificate(text=b'fictional certificate'):
    return SimpleUploadedFile('fictional-certificate.pdf', b'%PDF-1.4\n' + text, content_type='application/pdf')


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAODocumentTests(PDAOHelpers, TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory(prefix='pdao-documents-test-')
        self.addCleanup(self.storage.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.storage.name,
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                      'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.url = reverse('membership:pdao_apply')

    def upload_data(self):
        return {'photo_2x2': portrait(), 'civil_document': certificate(), 'civil_alternative': 'birth',
                'voter_certificate': certificate(b'fictional voter certificate')}

    def test_online_documents_saved_privately_and_staff_can_download(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        for name in ('photo_2x2', 'civil_document', 'voter_certificate', 'civil_alternative'):
            self.assertContains(response, f'name="{name}"')
        data = pdao_data() | {'submission_token': response.context['form'].initial['submission_token']}
        self.assertEqual(self.client.post(self.url, data | self.upload_data()).status_code, 302)
        item = PDAORegistration.objects.get()
        self.assertEqual(item.attachments.count(), 3)
        for field in self.upload_data():
            self.assertNotIn(field, item.data)
        attachment = item.attachments.get(slot='civil_document')
        self.assertEqual(attachment.alternative, 'birth')
        self.assertTrue(attachment.file.name.startswith(f'pdao/{item.pk}/'))
        self.assertNotIn('fictional', attachment.file.name)
        url = reverse('membership:pdao_document', args=[attachment.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = actor(services.VIEW)
        self.client.force_login(staff)
        detail = self.client.get(reverse('membership:pdao_detail', args=[item.pk]))
        self.assertContains(detail, url)
        download = self.client.get(url)
        self.assertEqual(download.status_code, 200)
        self.assertIn(b'fictional certificate', b''.join(download.streaming_content))
        self.assertIn('no-store', download['Cache-Control'])
        self.assertEqual(download['X-Content-Type-Options'], 'nosniff')
        self.assertIn('attachment;', download['Content-Disposition'])
        self.assertTrue(item.events.filter(action='document_downloaded', actor=staff).exists())
        staff.user_permissions.clear()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_onsite_uploads_and_csrf(self):
        staff = actor(services.VIEW, services.ADD)
        client = Client(enforce_csrf_checks=True)
        client.force_login(staff)
        url = reverse('membership:pdao_onsite')
        response = client.get(url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="civil_document"')
        data = pdao_data() | {'submission_token': response.context['form'].initial['submission_token']}
        self.assertEqual(client.post(url, data | self.upload_data()).status_code, 403)
        data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url, data | self.upload_data()).status_code, 302)
        item = PDAORegistration.objects.get()
        self.assertEqual(item.data['intake_channel'], 'walk_in')
        self.assertEqual(item.attachments.count(), 3)

    def test_retry_checks_file_content_and_keeps_only_one_copy(self):
        data = self.prepare()
        self.assertEqual(self.client.post(self.url, data | self.upload_data()).status_code, 302)
        self.assertEqual(self.client.post(self.url, data | self.upload_data()).status_code, 302)
        changed = self.upload_data() | {'voter_certificate': certificate(b'changed')}
        self.assertEqual(self.client.post(self.url, data | changed).status_code, 400)
        self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.assertEqual(PDAORegistration.objects.count(), 1)
        self.assertEqual(PDAORegistrationAttachment.objects.count(), 3)
        self.assertEqual(len([p for p in Path(self.storage.name).rglob('*') if p.is_file()]), 3)

    def test_reject_invalid_duplicate_and_mismatched_files(self):
        data = self.prepare()
        cases = [
            {'photo_2x2': certificate()},
            {'civil_document': certificate()},
            {'civil_alternative': 'marriage'},
            {'voter_certificate': [certificate(), certificate()]},
            {'voter_certificate': SimpleUploadedFile('fake.pdf', b'not a PDF', content_type='application/pdf')},
            {'unlisted_document': certificate()},
        ]
        for extra in cases:
            with self.subTest(fields=list(extra)):
                self.assertEqual(self.client.post(self.url, data | extra).status_code, 400)
        self.assertFalse(PDAORegistration.objects.exists())
        self.assertFalse(PDAORegistrationAttachment.objects.exists())

    def test_file_and_total_limits(self):
        data = self.prepare()
        with self.settings(MEMBERSHIP_FILE_MAX_BYTES=10):
            self.assertEqual(self.client.post(self.url, data | {'voter_certificate': certificate()}).status_code, 400)
        with self.settings(MEMBERSHIP_TOTAL_MAX_BYTES=10):
            response = self.client.post(self.url, data | {'voter_certificate': certificate()})
            self.assertEqual(response.status_code, 400)
        with self.settings(MEMBERSHIP_TOTAL_MAX_BYTES=10):
            response = self.client.post(self.url, data | {'voter_certificate': certificate(b'x' * 70000)})
            self.assertEqual(response.status_code, 413)
        self.assertFalse(PDAORegistration.objects.exists())

    def test_audit_failure_removes_files_and_rolls_back_record(self):
        data = self.prepare()
        with patch.object(services, 'record_event', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, data | self.upload_data())
        self.assertFalse(PDAORegistration.objects.exists())
        self.assertFalse(PDAORegistrationAttachment.objects.exists())
        self.assertFalse(any(p.is_file() for p in Path(self.storage.name).rglob('*')))

    def test_partial_storage_failure_removes_previous_upload(self):
        data = self.prepare()
        from django.core.files.storage import FileSystemStorage
        original = FileSystemStorage.save
        calls = []
        def fail_second(storage, *args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OSError('synthetic storage failure')
            return original(storage, *args, **kwargs)
        with patch.object(FileSystemStorage, 'save', fail_second):
            with self.assertRaises(OSError):
                self.client.post(self.url, data | self.upload_data())
        self.assertFalse(PDAORegistration.objects.exists())
        self.assertFalse(any(p.is_file() for p in Path(self.storage.name).rglob('*')))

    def test_review_correction_retains_documents(self):
        data = self.prepare()
        self.client.post(self.url, data | self.upload_data())
        item = PDAORegistration.objects.get()
        documents = list(item.attachments.values_list('pk', flat=True))
        staff = actor(services.VIEW, services.CORRECT)
        services.correct(item.pk, staff, review_data(item, first_name='Corrected'))
        item.refresh_from_db()
        self.assertEqual(item.current_data['first_name'], 'Corrected')
        self.assertEqual(list(item.attachments.values_list('pk', flat=True)), documents)
