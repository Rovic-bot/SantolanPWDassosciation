from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.state import ProjectState
from django.forms.models import model_to_dict
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from announcements.tests import image_upload
from membership.tests import grant
from scripts.durable_test_runner import require_disposable
from .forms import ProgramForm, ProgramSetupForm
from .models import Program, ProgramPicture, ProgramLog
from .services import save_program_with_requirements, change_publication
from .tests import program_data
from .testsupport import private_media


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class ProgramPictureTests(TestCase):
    def setUp(self):
        self.media = private_media(self)
        self.admin = get_user_model().objects.create_superuser('picture_admin')
        self.client.force_login(self.admin)

    def create(self, upload=True):
        return save_program_with_requirements(user=self.admin, setup_only=True,
            data=program_data(name='Rice Distribution', benefit='Food assistance'), requirements=[],
            files={'picture': image_upload()} if upload else {})

    def data(self, program, **overrides):
        data = model_to_dict(program, fields=ProgramForm.Meta.fields)
        data['eligible_disability_types'] = list(program.eligible_disability_types.values_list('pk', flat=True))
        data.update(version=program.version, notes='Update presentation picture.',
                    picture_version=getattr(getattr(program, 'picture_asset', None), 'version', 0))
        data.update(overrides)
        return data

    def save(self, program, *, files=None, **changes):
        return save_program_with_requirements(user=self.admin, pk=program.pk,
            data=self.data(program, **changes), files=files, requirements=[], setup_only=True)

    def test_optional_picture_and_title_initials_in_shared_details(self):
        program = self.create(upload=False)
        self.assertFalse(ProgramPicture.objects.exists())
        self.assertEqual(program.initials, 'RD')
        self.assertEqual(Program(name='  Community   Food Support ').initials, 'CF')
        self.assertEqual(Program(name='Health').initials, 'H')
        response = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertContains(response, '<span class="profile-header-initials">RD</span>', html=True)

    def test_builder_multipart_upload_and_protected_preview(self):
        program = self.create(upload=False)
        data = self.data(program)
        for key, value in list(data.items()):
            if value is None:
                data[key] = ''
            elif hasattr(value, 'tzinfo'):
                data[key] = timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')
        data['picture'] = image_upload()
        response = self.client.post(reverse('programs:edit', args=[program.pk]), data,
                                    HTTP_X_PROGRAM_BUILDER='1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'data-saved="true"')
        picture = ProgramPicture.objects.get(program=program)
        self.assertTrue(picture.image.storage.exists(picture.image.name))
        url = reverse('programs:picture', args=[program.pk])
        preview = self.client.get(url)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview['Content-Type'], 'image/png')
        self.assertEqual(preview['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', preview['Cache-Control'])
        self.assertTrue(b''.join(preview.streaming_content).startswith(b'\x89PNG'))
        page = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertContains(page, url)
        self.assertNotContains(page, '/media/')
        viewer = get_user_model().objects.create_user('picture_limited', is_staff=True)
        grant(viewer, 'accounts.access_dashboard')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_retain_replace_and_remove_picture_without_changing_approved_terms(self):
        program = self.create()
        change_publication(program.pk, user=self.admin, version=program.version, action='published')
        program.refresh_from_db()
        before = Program.objects.values().get(pk=program.pk)
        first = ProgramPicture.objects.get(program=program).image.name
        self.save(program)
        self.assertEqual(ProgramPicture.objects.get(program=program).image.name, first)
        self.save(program, files={'picture': image_upload()})
        program.refresh_from_db()
        second = ProgramPicture.objects.get(program=program)
        self.assertNotEqual(second.image.name, first)
        self.assertTrue(second.image.storage.exists(first))
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        self.save(program, remove_picture=True)
        second.refresh_from_db()
        self.assertFalse(second.image)
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        self.assertEqual(self.client.get(reverse('programs:picture', args=[program.pk])).status_code, 404)
        self.assertEqual(ProgramLog.objects.filter(program=program, action='picture_updated').count(), 3)

    def test_reject_invalid_oversized_and_conflicting_uploads(self):
        invalid = SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')
        for upload in (invalid, SimpleUploadedFile('x.svg', b'<svg/>', content_type='image/svg+xml')):
            with self.assertRaises(ValidationError):
                save_program_with_requirements(user=self.admin, setup_only=True,
                    data=program_data(benefit='Food assistance'), files={'picture': upload}, requirements=[])
        with override_settings(ANNOUNCEMENT_IMAGE_MAX_BYTES=10):
            with self.assertRaises(ValidationError):
                self.create()
        form = ProgramSetupForm(program_data(benefit='Food assistance', remove_picture=True),
                                {'picture': image_upload()})
        self.assertFalse(form.is_valid())
        self.assertIn('picture', form.errors)
        self.assertFalse(Program.objects.exists())

    def test_stale_picture_version_rolls_back_other_edits(self):
        program = self.create()
        before = Program.objects.values().get(pk=program.pk)
        with self.assertRaisesMessage(ValidationError, 'picture changed'):
            self.save(program, files={'picture': image_upload()}, picture_version=0, name='Stale title')
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        self.assertEqual(ProgramPicture.objects.get(program=program).version, 1)

    def test_picture_audit_failure_rolls_back_file_and_program(self):
        from .services import record_log
        def fail_picture(*args, **kwargs):
            if args[1] == 'picture_updated':
                raise RuntimeError('Synthetic audit failure')
            return record_log(*args, **kwargs)
        with patch('programs.services.record_log', side_effect=fail_picture):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(Program.objects.exists())
        self.assertFalse(ProgramPicture.objects.exists())
        self.assertFalse(any(path.is_file() for path in Path(self.media.name).rglob('*')))

    def test_write_requires_program_permission_and_validates_images_in_service(self):
        viewer = get_user_model().objects.create_user('picture_read_only', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        with self.assertRaises(PermissionDenied):
            save_program_with_requirements(user=viewer, setup_only=True,
                data=program_data(benefit='Food assistance'), files={'picture': image_upload()}, requirements=[])
        self.assertFalse(ProgramPicture.objects.exists())


class ProgramPictureMigrationTests(TransactionTestCase):
    def test_additive_picture_table_preserves_programs(self):
        require_disposable()
        from .tests import create_program
        program = create_program()
        before = Program.objects.values().get(pk=program.pk)
        state = ProjectState.from_apps(apps)
        state.remove_model('programs', 'programpicture')
        migration = import_module('programs.migrations.0007_program_picture').Migration('0007_program_picture', 'programs')
        self.assertEqual([type(op).__name__ for op in migration.operations], ['CreateModel'])
        try:
            with connection.schema_editor() as editor:
                editor.delete_model(ProgramPicture)
            with connection.schema_editor() as editor:
                migration.apply(state, editor)
            self.assertEqual(Program.objects.values().get(pk=program.pk), before)
            self.assertFalse(ProgramPicture.objects.exists())
        finally:
            if ProgramPicture._meta.db_table not in connection.introspection.table_names():
                with connection.schema_editor() as editor:
                    editor.create_model(ProgramPicture)
