"""Private Supabase S3 adapter. Authorization stays in the existing Django views."""
from contextlib import contextmanager
import json
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from boto3.s3.transfer import TransferConfig
from boto3.exceptions import Boto3Error
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from storages.backends.s3 import S3Storage


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the server API key to a redirected destination.
        return None


class SupabasePrivateStorage(S3Storage):
    def __init__(self, *, project_ref, bucket_api_key, **options):
        self._bucket_api_key = bucket_api_key
        self._bucket_api_url = f'https://{project_ref}.supabase.co/storage/v1/bucket/'
        super().__init__(
            **options,
            endpoint_url=f'https://{project_ref}.storage.supabase.co/storage/v1/s3',
            session_profile=None, security_token=None, custom_domain=None,
            default_acl=None, querystring_auth=True, file_overwrite=False,
            location='', gzip=False, verify=True, use_ssl=True,
            object_parameters={'CacheControl': 'private, no-store'},
            max_memory_size=1024 * 1024,
            transfer_config=TransferConfig(use_threads=False),
            client_config=Config(
                signature_version='s3v4', s3={'addressing_style': 'path'},
                connect_timeout=5, read_timeout=15,
                retries={'mode': 'standard', 'total_max_attempts': 2},
                request_checksum_calculation='when_required',
                response_checksum_validation='when_required',
            ),
        )

    def check_private_bucket(self):
        """Fail closed on a public, missing or unverifiable bucket; never cache approval.

        S3 ACL operations are unsupported by Supabase. Read its bucket metadata
        over verified HTTPS instead. No bucket is created or changed here.
        """
        request = Request(self._bucket_api_url + self.bucket_name,
                          headers={'apikey': self._bucket_api_key, 'Accept': 'application/json'})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=10) as response:
                metadata = json.loads(response.read(65537))
            if (not isinstance(metadata, dict) or metadata.get('id') != self.bucket_name
                    or metadata.get('public') is not False):
                raise ValueError
        except (OSError, URLError, ValueError):
            raise OSError('Private storage bucket could not be verified. Access denied.') from None

    @contextmanager
    def _operation(self):
        self.check_private_bucket()
        try:
            yield
        except FileNotFoundError:
            raise FileNotFoundError('Private file unavailable.') from None
        except (Boto3Error, BotoCoreError, ClientError, OSError):
            # Provider exceptions can contain keys, URLs or request metadata.
            raise OSError('Private storage operation failed. No local fallback is permitted.') from None

    def _open(self, name, mode='rb'):
        if mode != 'rb':
            raise ValueError('Private files are read-only when opened; use storage.save for uploads.')
        source = None
        with self._operation():
            try:
                source = super()._open(name, mode)
                # Complete the remote read before returning HTTP headers. The SDK
                # spools above 1 MiB to a secure temporary file, closed by FileResponse.
                source.file
                return source
            except Exception:
                if source is not None:
                    source.close()
                raise

    def _save(self, name, content):
        with self._operation():
            return super()._save(name, content)

    def exists(self, name):
        with self._operation():
            return super().exists(name)

    def delete(self, name):
        with self._operation():
            return super().delete(name)

    def size(self, name):
        with self._operation():
            return super().size(name)

    def url(self, name, *args, **kwargs):
        raise ValueError('Private files require an authorized application view; storage URLs are disabled.')

    def listdir(self, name):
        raise NotImplementedError('Object listing is not an application interface.')
