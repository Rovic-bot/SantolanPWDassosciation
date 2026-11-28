"""Synthetic upload checks; no malicious decoder payloads or private files."""
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from announcements.images import prepare_image
from membership.forms import validate_portrait


def upload(kind, mime, name):
    stream = BytesIO()
    Image.new('RGB', (4, 4), 'blue').save(stream, format=kind)
    return SimpleUploadedFile(name, stream.getvalue(), content_type=mime)


class ImageDecoderBoundaryTests(SimpleTestCase):
    def test_portrait_rejects_disguised_gif_and_rewinds_stream(self):
        image = upload('GIF', 'image/png', 'portrait.png')
        with self.assertRaises(ValidationError):
            validate_portrait(image)
        self.assertEqual(image.tell(), 0)

    def test_portrait_accepts_png_and_jpeg_and_rewinds_stream(self):
        for kind, mime, name in [('PNG', 'image/png', 'portrait.png'), ('JPEG', 'image/jpeg', 'portrait.jpg')]:
            image = upload(kind, mime, name)
            validate_portrait(image)
            self.assertEqual(image.tell(), 0)

    def test_announcement_opens_only_the_declared_allowed_decoder(self):
        original = Image.open
        with patch('announcements.images.Image.open', wraps=original) as opened:
            result = prepare_image(upload('PNG', 'image/png', 'notice.png'))
        self.assertTrue(result.size)
        self.assertEqual(len(opened.call_args_list), 2)
        self.assertTrue(all(call.kwargs.get('formats') == ['PNG'] for call in opened.call_args_list))
