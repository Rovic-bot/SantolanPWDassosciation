"""Synthetic announcement UI fixtures, generated only in a disposable test DB."""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.models import Announcement
from announcements.results import prepare_results
from announcements.services import change_publication, save_announcement
from announcements.tests import image_upload
from members.tests import create_member
from programs.tests import create_program
from programs.models import ProgramPicture
from programs.testsupport import application_fixture, private_media
from scripts.durable_test_runner import require_disposable


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AnnouncementLayoutFixtures(TestCase):
    def test_render_synthetic_fixtures(self):
        require_disposable()
        private_media(self)
        admin = get_user_model().objects.create_superuser('announcement-layout-fixture')
        self.client.force_login(admin)
        program_images = []
        for index in range(2):
            program = create_program(ewaf_applicable=True, name=f'Community support {index + 1}',
                description=('Complete overview of the published program and its support for members.\n\n' * (12 if index else 1)) + 'Final program details.')
            if index:
                # Existing public portal artwork, copied only into disposable fixtures.
                picture = ProgramPicture.objects.create(program=program,
                    image=ContentFile(Path('static/images/community/assistance-supplies.jpg').read_bytes(), name='community.jpg'))
                program_images.append(picture)
            for number in range(4):
                application_fixture(program, create_member(f'LAYOUT-{index}-{number}'))
            item = prepare_results(program.pk, user=admin, version=0, recorded=True, reason='Synthetic private review',
                selection_reason='Synthetic selection based on the published program requirements.')
            change_publication(item.pk, user=admin, version=item.version, action='published')
        for index in range(6):
            item = save_announcement(user=admin, composer=True,
                data={'title': f'Community announcement {index + 1}', 'version': 0,
                    'content': ('Members are invited to visit the Association office for guidance.\n\n' * (6 if index == 5 else 1)) + 'Final announcement details.'},
                files=MultiValueDict({'image': [image_upload()]}) if index == 5 else None)
            change_publication(item.pk, user=admin, version=item.version, action='published')
        output = Path('.local/announcement-layout-synthetic')
        output.mkdir(exist_ok=True)
        manifest = []
        board = reverse('core:announcements')
        urls = [board, board + '?category=announcements', board + '?category=announcements&page=2',
            board + '?category=announcements&q=missing', board + '?category=results', board + '?category=results&page=2',
            reverse('announcements:manage_notices'), reverse('announcements:manage_list'),
            reverse('announcements:create'), reverse('announcements:create') + '?popup=1']
        urls += [reverse('announcements:detail', args=[item.pk]) + '?popup=1' for item in Announcement.objects.all()]
        for index, url in enumerate(urls):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            filename = f'{index:02d}.html'
            output.joinpath(filename).write_bytes(response.content)
            manifest.append({'url': url, 'file': filename})
        error = self.client.post(reverse('announcements:create') + '?popup=1', {'title': '', 'content': '', 'version': 0})
        output.joinpath('errors.html').write_bytes(error.content)
        image = Announcement.objects.exclude(image='').get()
        output.joinpath('image.png').write_bytes(image.image.read())
        image.image.close()
        manifest.append({'url': reverse('announcements:image', args=[image.pk]), 'file': 'image.png'})
        for index, picture in enumerate(program_images):
            filename = f'program-{index}.jpg'
            output.joinpath(filename).write_bytes(picture.image.read())
            picture.image.close()
            manifest.append({'url': reverse('programs:public_picture', args=[picture.program_id]), 'file': filename})
        output.joinpath('manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
