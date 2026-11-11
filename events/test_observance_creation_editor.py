"""Compact annual-observance authoring on disposable records only."""
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from membership.tests import grant
from .models import AnnualObservance
from .observance_forms import AnnualObservanceEditForm
from .services import save_observance, change_observance_publication
from .test_observance_workflow import draft_data


class ObservanceCreationEditorTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_superuser('SYNTHETIC-OBSERVANCE-CREATE')
        self.client.force_login(self.user)
        self.url = reverse('events:observance_create')

    def data(self, **changes):
        return dict(title='Synthetic annual observance', target_audience='Synthetic focus audience',
                    start_date='2028-02-28', end_date='2028-02-29',
                    description='Synthetic description for testing.', version=0, **changes)

    def create(self, **changes):
        return save_observance(user=self.user, data=self.data() | changes, simplified_editor=True)

    def test_create_uses_shared_layout_and_edit_fields(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Create annual observance')
        self.assertContains(response, 'data-observance-builder')
        self.assertContains(response, 'Save draft')
        self.assertContains(response, f'action="{self.url}"')
        self.assertSetEqual(set(response.context['form'].fields),
            {'title', 'target_audience', 'start_date', 'end_date', 'description', 'image', 'version'})
        self.assertFalse(AnnualObservance.objects.exists())

    def test_http_creates_private_draft_then_publishes_without_invented_reference(self):
        response = self.client.post(self.url, self.data() | {'status': 'published',
            'source_url': 'https://invalid.example/', 'legal_basis': 'Forged reference',
            'who_may_participate': 'Forged policy'})
        item = AnnualObservance.objects.get()
        self.assertRedirects(response, reverse('events:observance_detail', args=[item.pk]))
        self.assertEqual((item.status, item.version, item.month, item.day_start, item.day_end),
                         ('draft', 1, 2, 28, 29))
        self.assertEqual((item.legal_basis, item.source_url, item.who_may_participate), ('', '', ''))
        self.assertEqual(item.recurrence_kind, 'fixed_range')
        self.assertFalse(AnnualObservance.objects.public().exists())
        item = change_observance_publication(item.pk, user=self.user, version=item.version,
            action='published', notes='Synthetic publication review.')
        self.assertEqual(item.revisions.count(), 2)
        self.assertEqual(item.history.count(), 2)
        self.assertContains(self.client.get(reverse('events:observance_public_detail', args=[item.pk])), item.title)

    def test_invalid_dates_and_missing_audience_cannot_create(self):
        for changes in ({'start_date': ''}, {'end_date': ''}, {'end_date': '2028-03-01'},
                        {'end_date': '2028-02-27'}, {'start_date': '2027-02-29'}, {'target_audience': ''}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
        self.assertFalse(AnnualObservance.objects.exists())

    def test_one_day_optional_image_and_image_description(self):
        plain = self.create(end_date='2028-02-28')
        self.assertEqual((plain.recurrence_kind, plain.day_start, plain.day_end), ('fixed_day', 28, None))
        self.assertFalse(plain.image)
        item = save_observance(user=self.user, data=self.data(), simplified_editor=True,
                              files=MultiValueDict({'image': [image_upload()]}))
        self.assertTrue(item.image.storage.exists(item.image.name))
        self.assertEqual(item.image_alt, item.title)
        self.assertEqual(item.revisions.get().image.name, item.image.name)

    def test_permissions_csrf_and_version_are_enforced(self):
        viewer = get_user_model().objects.create_user('SYNTHETIC-OBSERVANCE-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'events.view_annualobservance')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_observance(user=viewer, data=self.data(), simplified_editor=True)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, self.data()).status_code, 403)
        with self.assertRaises(ValidationError):
            self.create(version=3)
        self.assertFalse(AnnualObservance.objects.exists())

    def test_audit_failure_rolls_back_draft(self):
        with patch('events.services._record_observance', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(AnnualObservance.objects.exists())

    def test_existing_metadata_and_history_survive_shared_editor(self):
        item = save_observance(user=self.user, data=draft_data())
        original = item.revisions.get()
        retained = (item.legal_basis, item.source_url, item.who_may_participate)
        item = save_observance(user=self.user, pk=item.pk, publish=True, simplified_editor=True,
            data=self.data() | {'version': item.version, 'title': 'Updated synthetic observance'})
        self.assertEqual((item.legal_basis, item.source_url, item.who_may_participate), retained)
        original.refresh_from_db()
        self.assertEqual(original.title, 'Fictional awareness card')
        self.assertEqual(item.revisions.count(), 2)
        self.assertIn('remove_image', AnnualObservanceEditForm(instance=item).fields)

    def test_partial_or_invalid_official_sources_remain_invalid(self):
        item = self.create()
        for basis, url in [('Incomplete reference', ''), ('', 'https://www.un.org/en/observances/'),
                           ('Invalid source', 'https://example.invalid/')]:
            item.legal_basis, item.source_url = basis, url
            with self.subTest(source=url), self.assertRaises(ValidationError):
                item.full_clean()
