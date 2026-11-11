from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_upload_total(files):
    if sum(upload.size for name in files for upload in files.getlist(name)) > settings.MEMBERSHIP_TOTAL_MAX_BYTES:
        raise ValidationError('The combined uploads exceed the limit. Choose smaller files.')


def validate_document(upload):
    allowed = {'.pdf': ('application/pdf', b'%PDF-'),
               '.png': ('image/png', b'\x89PNG\r\n\x1a\n'),
               '.jpg': ('image/jpeg', b'\xff\xd8\xff'),
               '.jpeg': ('image/jpeg', b'\xff\xd8\xff')}
    expected = allowed.get(Path(upload.name).suffix.lower())
    if not expected or upload.content_type != expected[0]:
        raise ValidationError('Upload a PDF, JPG, JPEG, or PNG with its matching file type.')
    if not upload.size or upload.size > settings.MEMBERSHIP_FILE_MAX_BYTES:
        raise ValidationError(f'Each file must be nonempty and no larger than {settings.MEMBERSHIP_FILE_MAX_BYTES // 1048576} MB.')
    header = upload.read(8)
    upload.seek(0)
    if not header.startswith(expected[1]):
        raise ValidationError('The file contents do not match its file type.')
    # Signature checks are not malware scanning. Delivery requires permission;
    # opt-in previews additionally use sandbox, nosniff and no-store headers.
