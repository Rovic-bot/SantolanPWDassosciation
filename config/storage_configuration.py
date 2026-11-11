"""Explicit production inputs; no ambient AWS credentials or endpoint fallback."""
import re

from django.core.exceptions import ImproperlyConfigured
from .environment import required


def supabase_storage_options():
    project = required('SUPABASE_PROJECT_REF')
    bucket = required('SUPABASE_STORAGE_BUCKET')
    region = required('SUPABASE_S3_REGION')
    api_key = required('SUPABASE_SECRET_KEY')
    if not re.fullmatch(r'[a-z0-9]{20}', project):
        raise ImproperlyConfigured('SUPABASE_PROJECT_REF must be the hosted project reference.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', bucket):
        raise ImproperlyConfigured('Use a lowercase, DNS-safe SUPABASE_STORAGE_BUCKET name.')
    if not re.fullmatch(r'[a-z0-9-]+', region):
        raise ImproperlyConfigured('SUPABASE_S3_REGION must be the region from Storage S3 settings.')
    if not api_key.startswith('sb_secret_') or any(c.isspace() for c in api_key):
        raise ImproperlyConfigured('SUPABASE_SECRET_KEY must be a server-only Supabase secret API key.')
    return {
        'project_ref': project, 'bucket_name': bucket, 'region_name': region,
        'access_key': required('SUPABASE_S3_ACCESS_KEY_ID'),
        'secret_key': required('SUPABASE_S3_SECRET_ACCESS_KEY'),
        'bucket_api_key': api_key,
    }
