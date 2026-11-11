from io import BytesIO
from pathlib import Path
import warnings
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def prepare_image(upload, *, max_bytes=None, max_pixels=None):
    max_bytes = max_bytes or settings.ANNOUNCEMENT_IMAGE_MAX_BYTES
    max_pixels = max_pixels or settings.ANNOUNCEMENT_IMAGE_MAX_PIXELS
    expected = {'.png': ('PNG', 'image/png'), '.jpg': ('JPEG', 'image/jpeg'), '.jpeg': ('JPEG', 'image/jpeg')}
    kind = expected.get(Path(upload.name).suffix.lower())
    if not kind or getattr(upload, 'content_type', '') != kind[1]:
        raise ValidationError('Choose a PNG or JPEG image with its matching file type.')
    if not upload.size or upload.size > max_bytes:
        raise ValidationError(f'Images must be nonempty and no larger than {max_bytes // 1048576} MB.')
    data = upload.read()
    upload.seek(0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as probe:
                if probe.format != kind[0] or probe.width * probe.height > max_pixels:
                    raise ValidationError('The image format or dimensions are not supported.')
                if getattr(probe, 'n_frames', 1) != 1:
                    raise ValidationError('Choose a still image, not an animation.')
                probe.verify()
            with Image.open(BytesIO(data)) as original:
                oriented = ImageOps.exif_transpose(original)
                oriented.thumbnail((1920, 1920))
                # Copy pixels into a fresh image, excluding source metadata and appended bytes.
                pixels = oriented.convert('RGBA')
                clean = Image.new('RGBA', pixels.size)
                clean.paste(pixels)
                output = BytesIO()
                clean.save(output, format='PNG')
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError('This image could not be read. Choose a valid PNG or JPEG.') from error
    return ContentFile(output.getvalue(), name='announcement.png')
