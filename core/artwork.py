"""Small card previews for already-authorized publication artwork only."""
from functools import lru_cache
from io import BytesIO
from threading import RLock

from django.http import Http404, HttpResponse
from PIL import Image, UnidentifiedImageError

_render_lock = RLock()


@lru_cache(maxsize=32)
def _card_image(storage, name, max_size=960):
    # Publication uploads get a new random path on every replacement. Cache
    # only derived bytes, never an authorization decision or a private record.
    with storage.open(name, 'rb') as source, Image.open(source) as image:
        if image.width * image.height > 16000000:
            raise ValueError('Artwork dimensions exceed the supported limit.')
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.convert('RGBA').save(output, format='WEBP', quality=84, method=4)
    return output.getvalue()


def card_image_response(image):
    """Call only after the view checks current publication/access permissions."""
    if not image:
        raise Http404
    return artwork_response(image.storage, image.name)


def artwork_response(storage, name, *, max_size=960):
    if max_size not in (960, 1600):
        raise ValueError('Unsupported artwork preview size.')
    # Keep the production storage adapter's fail-closed bucket verification,
    # including when the encoded preview is already in this worker's memory.
    check_private_bucket = getattr(storage, 'check_private_bucket', None)
    if check_private_bucket is not None:
        check_private_bucket()
    try:
        # Bound concurrent decoding memory on the free instance. The cache
        # contains at most 32 encoded previews; originals are never changed.
        with _render_lock:
            content = _card_image(storage, name, max_size)
    except (FileNotFoundError, UnidentifiedImageError, ValueError, Image.DecompressionBombError):
        raise Http404
    response = HttpResponse(content, content_type='image/webp')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response
