"""Performance boundaries with fictional content and disposable static assets."""
import gzip
import json
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.middleware.gzip import GZipMiddleware
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils import timezone
from PIL import Image

from config.static_storage import StaticStorage
from core.content import DEFAULTS, published_contents
from core.models import PublicContent
from core.portal_models import PortalPage


class ArtworkPerformanceTests(TestCase):
    def setUp(self):
        from core.artwork import _card_image
        self.cache = _card_image
        self.cache.cache_clear()
        self.addCleanup(self.cache.cache_clear)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.settings = override_settings(MEDIA_ROOT=temporary.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        stream = BytesIO()
        Image.new('RGBA', (1500, 1000), (0, 120, 180, 200)).save(stream, 'PNG')
        self.original = stream.getvalue()

    def test_all_public_artwork_rechecks_publication_after_thumbnail_cache_hit(self):
        from announcements.models import Announcement
        from events.models import AnnualObservance, Event
        from programs.models import Program, ProgramPicture
        now = timezone.now()
        common = {'status': 'published', 'published_at': now - timedelta(hours=1)}
        notice = Announcement.objects.create(title='Synthetic notice', **common)
        event = Event.objects.create(title='Synthetic event', starts_at=now,
            ends_at=now + timedelta(hours=1), **common)
        observance = AnnualObservance.objects.create(title='Synthetic observance', month=1,
            recurrence_kind='whole_month', recurrence_rule='January', published_by_label='Fixture staff', **common)
        program = Program.objects.create(name='Synthetic program', assistance_type='Community',
            registration_opens_at=now-timedelta(hours=1), registration_closes_at=now+timedelta(days=1), **common)
        picture = ProgramPicture.objects.create(program=program)
        for owner, item, route in (
            (notice, notice, 'announcements:image'), (event, event, 'events:image'),
            (observance, observance, 'events:observance_image'), (program, picture, 'programs:public_picture'),
        ):
            with self.subTest(route=route):
                item.image.save('artwork.png', ContentFile(self.original))
                url = reverse(route, args=[owner.pk])
                response = self.client.get(url + '?thumbnail=1')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'image/webp')
                self.assertIn('no-store', response['Cache-Control'])
                with Image.open(BytesIO(response.content)) as thumbnail:
                    self.assertEqual(thumbnail.size, (960, 640))
                hits = self.cache.cache_info().hits
                self.assertEqual(self.client.get(url + '?thumbnail=1').content, response.content)
                self.assertEqual(self.cache.cache_info().hits, hits + 1)
                original = self.client.get(url)
                self.assertEqual(b''.join(original.streaming_content), self.original)
                owner.status = 'draft'
                owner.published_at = None
                fields = ['status', 'published_at']
                if isinstance(owner, AnnualObservance):
                    owner.published_by_label = ''
                    fields.append('published_by_label')
                owner.save(update_fields=fields)
                self.assertEqual(self.client.get(url + '?thumbnail=1').status_code, 404)

    def test_replacement_path_never_reuses_an_old_thumbnail(self):
        from core.artwork import card_image_response
        from announcements.models import Announcement
        item = Announcement.objects.create(title='Synthetic notice')
        item.image.save('first.png', ContentFile(self.original))
        original_name = item.image.name
        first = card_image_response(item.image).content
        stream = BytesIO()
        Image.new('RGB', (100, 100), 'red').save(stream, 'PNG')
        item.image.save('second.png', ContentFile(stream.getvalue()))
        self.assertNotEqual(item.image.name, original_name)
        self.assertNotEqual(card_image_response(item.image).content, first)

    def test_portal_artwork_cache_never_exposes_draft_or_withdrawn_image(self):
        from django.core.files.storage import default_storage
        name = default_storage.save('portal/synthetic.png', ContentFile(self.original))
        value = {'token': 'synthetic-token', 'file': name}
        page = PortalPage.objects.create(key='home', content={'picture_1': value})
        url = reverse('core:portal_image', args=['home', 'picture_1', value['token']]) + '?thumbnail=1'
        self.assertEqual(self.client.get(url).status_code, 404)
        page.published = page.content
        page.save(update_fields=['published'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/webp')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get(url + '&preview=1').status_code, 403)
        page.published = {}
        page.save(update_fields=['published'])
        self.assertEqual(self.client.get(url).status_code, 404)


class PublishedContentPerformanceTests(TestCase):
    def test_bulk_lookup_has_one_query_and_excludes_drafts(self):
        PublicContent.objects.create(key='home', title='Private draft title', body='Private draft body',
            published={'title': 'Approved welcome', 'body': 'Approved text', 'version': 1})
        PublicContent.objects.create(key='contact', title='Unpublished office', body='Private instructions')
        with self.assertNumQueries(1):
            result = published_contents(('home', 'contact', 'privacy', 'home'))
        self.assertEqual(result['home']['title'], 'Approved welcome')
        for key in ('contact', 'privacy'):
            self.assertEqual(result[key], {'title': DEFAULTS[key][0], 'body': DEFAULTS[key][1]})
        self.assertNotIn('Private', json.dumps(result))
        PublicContent.objects.filter(key='home').update(published={})
        self.assertEqual(published_contents(('home',))['home']['title'], DEFAULTS['home'][0])

    def test_public_home_keeps_private_no_store_and_responsive_artwork_override(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'home-pavilion-illustration-mobile.webp')
        self.assertContains(response, 'public-utilities.css')
        self.assertNotContains(response, 'cdn.tailwindcss.com')
        PortalPage.objects.create(key='home', published={'picture_1': {'token': 'published-artwork', 'file': 'private-artwork.png'}})
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, '/portal-artwork/home/picture_1/published-artwork/')
        self.assertNotContains(response, 'home-pavilion-illustration-mobile.webp')
        self.assertNotContains(response, 'private-artwork.png')


class StaticPerformanceTests(SimpleTestCase):
    def test_hashed_assets_are_compressed_and_immutable_but_media_is_unserved(self):
        from whitenoise.middleware import WhiteNoiseMiddleware
        with TemporaryDirectory() as temporary, override_settings(
            DEBUG=False, STATIC_ROOT=temporary, STATIC_URL='/static/',
            WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False,
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                      'staticfiles': {'BACKEND': 'config.static_storage.StaticStorage'}},
        ):
            storage = StaticStorage(location=temporary, base_url='/static/')
            body = b'.fixture {color: #333;}\n' * 100
            storage.save('css/site.css', ContentFile(body))
            list(storage.post_process({'css/site.css': (storage, 'css/site.css')}))
            serve = WhiteNoiseMiddleware(lambda request: HttpResponse(status=404))
            request = RequestFactory().get(storage.url('css/site.css'), HTTP_ACCEPT_ENCODING='gzip')
            response = serve(request)
            self.assertEqual(response.status_code, 200)
            self.assertIn('immutable', response['Cache-Control'])
            self.assertEqual(response['Content-Encoding'], 'gzip')
            self.assertEqual(gzip.decompress(b''.join(response.streaming_content)), body)
            response.close()
            self.assertEqual(serve(RequestFactory().get('/media/private.png')).status_code, 404)

    def test_manifest_rewrites_real_assets_and_omits_unshipped_source_maps(self):
        with TemporaryDirectory() as temporary, override_settings(DEBUG=False):
            storage = StaticStorage(location=temporary, base_url='/static/')
            assets = {
                'css/site.css': b'body{background:url("../images/icon.svg")}\n/*# sourceMappingURL=missing.css.map */',
                'images/icon.svg': b'<svg xmlns="http://www.w3.org/2000/svg"/>',
                'js/site.js': b'const ready=true;\n//# sourceMappingURL=missing.js.map',
            }
            for name, content in assets.items():
                storage.save(name, ContentFile(content))
            results = list(storage.post_process({name: (storage, name) for name in assets}))
            self.assertFalse([processed for _, _, processed in results if isinstance(processed, Exception)])
            for name in assets:
                self.assertNotEqual(storage.url(name), '/static/' + name)
            css = (Path(temporary) / storage.stored_name('css/site.css')).read_text()
            self.assertIn(storage.stored_name('images/icon.svg').split('/')[-1], css)
            self.assertTrue((Path(temporary) / 'staticfiles.json').is_file())

    def test_missing_real_css_asset_still_fails_collection(self):
        with TemporaryDirectory() as temporary:
            storage = StaticStorage(location=temporary, base_url='/static/')
            storage.save('style.css', ContentFile(b'body{background:url("missing.png")}'))
            results = list(storage.post_process({'style.css': (storage, 'style.css')}))
            self.assertTrue(any(isinstance(processed, ValueError) for _, _, processed in results))

    def test_compression_preserves_no_store_and_response_content(self):
        body = b'<p>Fictional private page</p>' * 100
        response = HttpResponse(body)
        add_never_cache_headers(response)
        request = RequestFactory().get('/', HTTP_ACCEPT_ENCODING='gzip')
        compressed = GZipMiddleware(lambda request: response)(request)
        self.assertEqual(gzip.decompress(compressed.content), body)
        self.assertLess(len(compressed.content), len(body))
        self.assertIn('no-store', compressed['Cache-Control'])
        self.assertIn('Accept-Encoding', compressed['Vary'])
