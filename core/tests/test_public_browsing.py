"""Publication boundaries for public artwork and detail dialogs."""
from dataclasses import asdict
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from announcements.models import Announcement
from announcements.tests import image_upload
from events.models import AnnualObservance
from events.observances import REFERENCE_CATALOGUE
from programs.models import ProgramPicture
from programs.tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class PublicBrowsingTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def test_program_artwork_uses_publication_checked_route_and_initials_fallback(self):
        program = create_program(name='Community Support')
        detail = reverse('programs:detail', args=[program.pk])
        response = self.client.get(detail)
        self.assertContains(response, '>CS</span>')
        asset = ProgramPicture.objects.create(program=program, image=image_upload())
        image_url = reverse('programs:public_picture', args=[program.pk])
        for url in (detail, reverse('core:programs')):
            response = self.client.get(url)
            self.assertContains(response, image_url)
            self.assertNotContains(response, asset.image.name)
        response = self.client.get(image_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        self.assertIn('no-store', response['Cache-Control'])
        for status, date in (('draft', timezone.now()), ('archived', timezone.now()),
                             ('published', timezone.now() + timezone.timedelta(days=1))):
            program.status, program.published_at = status, date
            program.save(update_fields=['status', 'published_at'])
            self.assertEqual(self.client.get(image_url).status_code, 404)
        self.assertEqual(self.client.post(image_url).status_code, 405)

    def test_announcement_fragment_escapes_copy_and_withholds_nonpublic_records(self):
        item = Announcement.objects.create(title='Community <script>bad()</script>',
            content='Public <b>update</b>', status='published', published_at=timezone.now())
        url = reverse('announcements:detail', args=[item.pk])
        response = self.client.get(url, {'popup': '1'})
        self.assertTemplateUsed(response, 'announcements/public_popup.html')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad()')
        self.assertNotContains(response, '<html')
        self.assertIn('no-store', response['Cache-Control'])
        for status, date in (('draft', timezone.now()), ('archived', timezone.now()),
                             ('published', timezone.now() + timezone.timedelta(days=1))):
            Announcement.objects.filter(pk=item.pk).update(status=status, published_at=date)
            self.assertEqual(self.client.get(url, {'popup': '1'}).status_code, 404)
        self.assertEqual(self.client.post(url + '?popup=1').status_code, 405)

    def test_observance_fragment_uses_only_published_content(self):
        reference = REFERENCE_CATALOGUE[0]
        item = AnnualObservance.objects.create(**asdict(reference), recurrence_rule=reference.recurrence_rule,
            status='published', published_at=timezone.now(), published_by_label='Synthetic publisher')
        url = reverse('events:observance_public_detail', args=[item.pk])
        response = self.client.get(url, {'popup': '1'})
        self.assertTemplateUsed(response, 'events/observance_public_popup.html')
        self.assertContains(response, reference.title)
        self.assertContains(response, reference.source_url)
        self.assertNotContains(response, '<html')
        self.assertTemplateUsed(self.client.get(url), 'events/observance_public_detail.html')
        AnnualObservance.objects.filter(pk=item.pk).update(published_at=timezone.now() + timezone.timedelta(days=1))
        self.assertEqual(self.client.get(url, {'popup': '1'}).status_code, 404)
        AnnualObservance.objects.filter(pk=item.pk).update(status='archived', published_at=None, published_by_label='')
        self.assertEqual(self.client.get(url, {'popup': '1'}).status_code, 404)
