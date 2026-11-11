"""Synthetic remote storage: real adapter/SDK, mocked network, disposable test DB."""
from io import BytesIO
import json
from pathlib import Path
import secrets
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch
from urllib.error import HTTPError, URLError

from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage, FileSystemStorage
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from membership import tests as membership_tests
from membership.models import MembershipApplication
from programs import test_revised_workflow as workflow_tests
from announcements import tests as announcement_tests
from .storage import SupabasePrivateStorage, _NoRedirect


def options():
    return {'project_ref': 'abcdefghijklmnopqrst', 'bucket_name': 'synthetic-private',
            'region_name': 'ap-southeast-1', 'access_key': secrets.token_hex(16),
            'secret_key': secrets.token_urlsafe(32), 'bucket_api_key': 'sb_secret_' + secrets.token_urlsafe(32)}


def private_response():
    return BytesIO(json.dumps({'id': 'synthetic-private', 'public': False}).encode())


def remote_error(code=404):
    return ClientError({'Error': {'Code': str(code), 'Message': 'SENSITIVE_PROVIDER_DETAIL'},
                        'ResponseMetadata': {'HTTPStatusCode': code}}, 'SyntheticOperation')


class StorageContractTests(SimpleTestCase):
    def setUp(self):
        self.storage = SupabasePrivateStorage(**options())
        self.opener = self.enterContext(patch('documents.storage.build_opener')).return_value
        self.opener.open.side_effect = lambda *args, **kwargs: private_response()

    def test_sdk_upload_read_delete_and_private_parameters(self):
        storage = self.storage
        payload = b'%PDF-1.4 synthetic only'
        client = storage.connection.meta.client
        with Stubber(client) as stub:
            stub.add_client_error('head_object', service_error_code='404', http_status_code=404,
                                  expected_params={'Bucket': storage.bucket_name, 'Key': 'evidence.pdf'})
            stub.add_response('put_object', {'ETag': 'synthetic'}, {
                'Bucket': storage.bucket_name, 'Key': 'evidence.pdf', 'Body': ANY,
                'ContentType': 'application/pdf', 'CacheControl': 'private, no-store'})
            self.assertEqual(storage.save('evidence.pdf', ContentFile(payload)), 'evidence.pdf')
            stub.add_response('head_object', {'ContentLength': len(payload)},
                              {'Bucket': storage.bucket_name, 'Key': 'evidence.pdf'})
            stub.add_response('get_object', {'Body': StreamingBody(BytesIO(payload), len(payload)),
                                             'ContentLength': len(payload)},
                              {'Bucket': storage.bucket_name, 'Key': 'evidence.pdf', 'Range': ANY})
            try:
                downloaded = storage.open('evidence.pdf')
            except OSError as error:
                self.fail(f'Synthetic SDK stub mismatch: {error.__context__}')
            with downloaded:
                self.assertEqual(downloaded.read(), payload)
                downloaded.seek(0)
                self.assertEqual(downloaded.read(), payload)
            stub.add_response('delete_object', {}, {'Bucket': storage.bucket_name, 'Key': 'evidence.pdf'})
            storage.delete('evidence.pdf')
            stub.assert_no_pending_responses()
        self.assertEqual(client.meta.config.signature_version, 's3v4')
        self.assertEqual(client.meta.config.s3['addressing_style'], 'path')
        self.assertEqual(client.meta.config.request_checksum_calculation, 'when_required')
        self.assertTrue(storage.verify)
        self.assertFalse(storage.transfer_config.use_threads)

    def test_public_missing_malformed_and_unreachable_bucket_fail_closed(self):
        for metadata in ({'id': 'synthetic-private', 'public': True},
                         {'id': 'other', 'public': False}, {}, [], {'id': 'synthetic-private', 'public': 'false'}):
            self.opener.open.side_effect = lambda *a, **kw: BytesIO(json.dumps(metadata).encode())
            with self.assertRaisesMessage(OSError, 'Access denied'):
                self.storage.exists('private-key')
        for error in (URLError('SENSITIVE_PROVIDER_DETAIL'),
                      HTTPError('https://private.invalid', 403, 'sensitive', {}, None)):
            self.opener.open.side_effect = error
            with self.assertRaises(OSError) as raised:
                self.storage.save('private-key', ContentFile(b'x'))
            self.assertNotIn('SENSITIVE', str(raised.exception))

    def test_metadata_uses_server_key_and_redirects_are_disabled(self):
        self.storage.check_private_bucket()
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.get_header('Apikey'), self.storage._bucket_api_key)
        self.assertTrue(request.full_url.startswith('https://abcdefghijklmnopqrst.supabase.co/'))
        self.assertIsNone(_NoRedirect().redirect_request(request, None, 302, '', {}, 'https://other.invalid'))

    def test_no_direct_urls_paths_listing_or_in_place_mutation(self):
        with self.assertRaises(ValueError):
            self.storage.url('evidence.pdf')
        with self.assertRaises(NotImplementedError):
            self.storage.path('evidence.pdf')
        with self.assertRaises(NotImplementedError):
            self.storage.listdir('')
        with self.assertRaises(ValueError):
            self.storage.open('evidence.pdf', 'wb')
        self.opener.open.assert_not_called()

    def test_sdk_failures_are_sanitized_and_not_reported_as_missing(self):
        with patch.object(type(self.storage), 'connection', new_callable=PropertyMock) as connection:
            client = connection.return_value.meta.client
            for error in (remote_error(403), EndpointConnectionError(endpoint_url='https://sensitive.invalid')):
                client.head_object.side_effect = error
                with self.assertRaisesMessage(OSError, 'No local fallback') as raised:
                    self.storage.exists('private-key')
                self.assertNotIsInstance(raised.exception, FileNotFoundError)
                self.assertNotIn('sensitive', str(raised.exception).lower())

    def test_default_development_storage_remains_filesystem(self):
        self.assertIsInstance(default_storage, FileSystemStorage)


class FakeBucket:
    """Remote object dictionary shared across adapter instances, never local files."""
    def __init__(self):
        self.objects = {}
        self.fail_upload = False

    def head_object(self, Bucket, Key, **kwargs):
        if Key not in self.objects:
            raise remote_error()
        return {'ContentLength': len(self.objects[Key])}

    def Object(self, key):
        bucket = self

        class Object:
            @property
            def content_length(self):
                return bucket.head_object(Bucket='', Key=key)['ContentLength']

            def load(self, **kwargs):
                bucket.head_object(Bucket='', Key=key)

            def upload_fileobj(self, source, **kwargs):
                if bucket.fail_upload:
                    raise remote_error(503)
                bucket.objects[key] = source.read()

            def download_fileobj(self, destination, **kwargs):
                self.load()
                destination.write(bucket.objects[key])

            def delete(self):
                bucket.objects.pop(key, None)

        return Object()


class RemoteStorageMixin:
    def setUp(self):
        super().setUp()
        self.remote = FakeBucket()
        self.enterContext(override_settings(STORAGES={
            'default': {'BACKEND': 'documents.storage.SupabasePrivateStorage', 'OPTIONS': options()},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        }))
        self.enterContext(patch.object(SupabasePrivateStorage, 'bucket', new_callable=PropertyMock,
                                      return_value=self.remote))
        connection = SimpleNamespace(meta=SimpleNamespace(client=self.remote))
        self.enterContext(patch.object(SupabasePrivateStorage, 'connection', new_callable=PropertyMock,
                                      return_value=connection))
        opener = self.enterContext(patch('documents.storage.build_opener')).return_value
        opener.open.side_effect = lambda *args, **kwargs: private_response()


class RemoteMembershipTests(RemoteStorageMixin, membership_tests.MembershipTests):
    # Re-run the existing membership acceptance tests against the real remote
    # adapter. Replace the local-only .url assertion with the stronger contract.
    def test_private_download_attachment_is_audited_and_uncached(self):
        application = self.application()
        document = application.documents.get()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('membership:document', args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertTrue(response.closed)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', response['Content-Security-Policy'])
        self.assertNotIn(document.file.name, str(response.headers))
        self.assertTrue(application.events.filter(action='document_downloaded', actor=self.admin).exists())
        with self.assertRaises(ValueError):
            _ = document.file.url
        with self.assertRaises(NotImplementedError):
            _ = document.file.path
        self.assertEqual(self.client.get('/media/' + document.file.name).status_code, 404)
        detail = self.client.get(reverse('membership:detail', args=[application.reference]))
        self.assertNotContains(detail, document.file.name)
        self.assertNotContains(detail, 'supabase.co')
        self.assertEqual(list(Path(self.media.name).iterdir()), [])
        fresh = SupabasePrivateStorage(**options())
        with fresh.open(document.file.name) as source:
            self.assertTrue(source.read().startswith(b'%PDF-'))

    def test_remote_upload_failure_rolls_back_intake_without_local_fallback(self):
        self.remote.fail_upload = True
        with self.assertRaisesMessage(OSError, 'No local fallback'):
            self.application()
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertEqual(self.remote.objects, {})
        self.assertEqual(list(Path(self.media.name).iterdir()), [])

    def test_unverifiable_bucket_cannot_disclose_evidence_or_record_download(self):
        application = self.application()
        document = application.documents.get()
        client = Client(raise_request_exception=False)
        client.force_login(self.admin)
        with patch('documents.storage.build_opener') as opener, override_settings(DEBUG=False):
            opener.return_value.open.side_effect = URLError('sensitive provider data')
            response = client.get(reverse('membership:document', args=[document.pk]))
        self.assertEqual(response.status_code, 500)
        self.assertNotContains(response, document.file.name, status_code=500)
        self.assertNotContains(response, 'sensitive provider data', status_code=500)
        self.assertFalse(application.events.filter(action='document_downloaded').exists())

    def test_audit_failure_removes_uncommitted_remote_upload(self):
        with patch('membership.services.record_event', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.application()
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertEqual(self.remote.objects, {})

    def test_large_read_spools_and_closes_temporary_file(self):
        storage = default_storage
        name = storage.save('synthetic-large.pdf', ContentFile(b'x' * (1024 * 1024 + 1)))
        source = storage.open(name)
        spool = source.file
        self.assertTrue(spool._rolled)
        source.close()
        self.assertTrue(spool.closed)


class RemoteProgramTests(RemoteStorageMixin, workflow_tests.RevisedWorkflowTests):
    def test_replacement_retains_old_photo_bytes_and_reference(self):
        application = self.submit()
        old_key = application.current_photo.file.name
        old_bytes = self.remote.objects[old_key]
        reference = application.public_reference
        self.photo(application, 'NEEDS_RESUBMISSION')
        from django.utils.datastructures import MultiValueDict
        from announcements.tests import image_upload
        revised = self.correct(application, MultiValueDict({'calendar_photo': [image_upload()]}))
        self.assertEqual(revised.public_reference, reference)
        self.assertNotEqual(revised.current_photo.file.name, old_key)
        self.assertEqual(self.remote.objects[old_key], old_bytes)
        self.assertIn(revised.current_photo.file.name, self.remote.objects)


class RemoteAnnouncementTests(RemoteStorageMixin, TestCase):
    draft = announcement_tests.AnnouncementTests.draft
    change = announcement_tests.AnnouncementTests.change

    def setUp(self):
        announcement_tests.AnnouncementTests.setUp(self)
        super().setUp()

    def test_images_follow_publication_gates_without_disclosing_object_keys(self):
        item = self.draft(image=True)
        route = reverse('announcements:image', args=[item.pk])
        self.assertEqual(Client().get(route).status_code, 404)
        item = self.change(item, 'published')
        response = Client().get(route)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        self.assertIn('image.png', response['Content-Disposition'])
        self.assertNotIn(Path(item.image.name).name, str(response.headers))
        self.change(item, 'draft')
        self.assertEqual(Client().get(route).status_code, 404)

    def test_image_replacement_and_removal_delete_only_after_commit(self):
        from announcements.services import save_announcement
        from django.utils.datastructures import MultiValueDict
        item = self.draft(image=True)
        old_key = item.image.name
        with self.captureOnCommitCallbacks(execute=True):
            item = save_announcement(user=self.admin, pk=item.pk,
                data={**self.data, 'version': item.version, 'image_alt': 'Replacement'},
                files=MultiValueDict({'image': [announcement_tests.image_upload()]}))
            self.assertIn(old_key, self.remote.objects)
        self.assertNotIn(old_key, self.remote.objects)
        new_key = item.image.name
        with self.captureOnCommitCallbacks(execute=True):
            item = save_announcement(user=self.admin, pk=item.pk,
                data={**self.data, 'version': item.version, 'remove_image': 'on'})
            self.assertIn(new_key, self.remote.objects)
        self.assertFalse(item.image)
        self.assertNotIn(new_key, self.remote.objects)
