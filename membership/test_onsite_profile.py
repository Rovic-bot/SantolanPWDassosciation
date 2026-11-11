from copy import deepcopy
from decimal import Decimal
from importlib import import_module
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from documents.models import MembershipDocumentRequirement, DocumentType, DocumentVerification
from documents.services import verify_document
from members.models import DisabilityType, Member
from members.profile import income_category_for, INCOME
from members.services import update_member
from members.tests import create_member
from programs.testsupport import private_media
from programs.tests import create_program
from programs.services import disability_matches
from .forms import ApplicationForm
from .models import MembershipSettings
from .services import submit_application, record_verification, decide_application
from .tests import onsite_profile, profile, pdf, grant


def seed_capture_slots():
    import_module('documents.migrations.0004_onsite_profile_capture').capture_slots(apps, SimpleNamespace(connection=connection))


def portrait():
    buffer = BytesIO()
    Image.new('RGB', (120, 120), '#c5ded8').save(buffer, format='PNG')
    return SimpleUploadedFile('fictional-photo.png', buffer.getvalue(), content_type='image/png')


class IncomeBoundaryTests(SimpleTestCase):
    def test_lower_inclusive_upper_exclusive_ranges(self):
        for index, (_, _) in enumerate(INCOME):
            self.assertEqual(income_category_for(index * 5000), INCOME[index][0])
            if index:
                self.assertEqual(income_category_for(Decimal(index * 5000) - Decimal('.01')), INCOME[index - 1][0])
        for value in ('-1', 'NaN', 'Infinity', 'invalid'):
            with self.assertRaises(ValidationError):
                income_category_for(value)


class OnsiteProfileTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_capture_slots()
        self.admin = get_user_model().objects.create_superuser('onsite_profile_admin')
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        self.data = {**onsite_profile(), 'submission_token': ApplicationForm().initial['submission_token']}
        self.other = DisabilityType.objects.get_or_create(name='Deaf or Hard of Hearing')[0]
        self.data['disability_types'].append(self.other.pk)
        self.client.force_login(self.admin)

    def uploads(self):
        return MultiValueDict({f'document_{item.pk}': [
            portrait() if item.capture_key == 'photo_1x1' else pdf()]
            for item in MembershipDocumentRequirement.objects.filter(capture_key__isnull=False)})

    def member(self, with_uploads=False):
        form = ApplicationForm(self.data, self.uploads() if with_uploads else None)
        self.assertTrue(form.is_valid(), form.errors)
        item = submit_application(form, user=self.admin)
        record_verification(item.reference, user=self.admin, version=0, verified=True, notes='Fictional manual PRPWD check')
        decide_application(item.reference, user=self.admin, version=1, decision='approved', notes='Fictional onsite decision')
        return Member.objects.get(application=item)

    def test_onsite_creation_preserves_structured_sources_without_invented_values(self):
        member = self.member(True)
        self.assertEqual(member.disability_ids, sorted(self.data['disability_types']))
        self.assertEqual(member.disability_ids, member.application.disability_ids)
        self.assertEqual(member.full_name, 'Sample Applicant')
        self.assertEqual(member.middle_name, '')
        self.assertTrue(member.no_middle_name)
        self.assertIn('Test Street', member.address)
        self.assertEqual(member.income_category_label, dict(INCOME)[member.income_category])
        self.assertIsNone(member.monthly_income)
        self.assertEqual(member.employment_information, '')
        self.assertEqual(member.application.documents.count(), 5)
        self.assertFalse(DocumentVerification.objects.exists())
        from ewaf.operational_models import OperationalRun
        self.assertFalse(OperationalRun.objects.exists())

    def test_name_suffix_choices_dependents_and_managed_disabilities_validate(self):
        for changes, field in [
            ({'no_middle_name': '', 'middle_name': ''}, 'middle_name'),
            ({'suffix': 'other', 'suffix_other': ''}, 'suffix_other'),
            ({'sex': 'invented'}, 'sex'), ({'civil_status': 'invented'}, 'civil_status'),
            ({'employment_status': 'unemployed'}, 'employment_status'),
            ({'education': 'invented'}, 'education'), ({'income_category': '5000'}, 'income_category'),
            ({'disability_types': []}, 'disability_types'), ({'disability_types': [999999]}, 'disability_types'),
            *[({'dependents': value}, 'dependents') for value in ('-1', '1.5', '1.0', 'abc', '65536')],
        ]:
            with self.subTest(changes=changes):
                form = ApplicationForm({**self.data, **changes})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        form = ApplicationForm({**self.data, 'suffix': 'other', 'suffix_other': 'VII', 'middle_name': 'Ignored'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['full_name'], 'Sample Applicant VII')
        self.assertEqual(form.cleaned_data['middle_name'], '')
        self.other.is_active = False
        self.other.save()
        self.assertFalse(ApplicationForm(self.data).is_valid())

    def test_required_documents_are_configurable_and_portrait_is_a_real_image(self):
        requirement = MembershipDocumentRequirement.objects.get(capture_key='photo_1x1')
        requirement.is_required = True
        requirement.save()
        data = {**self.data, 'submission_token': ApplicationForm().initial['submission_token']}
        self.assertTrue(ApplicationForm(data).is_valid())  # Inactive requirements stay optional.
        requirement.is_active = True
        requirement.save()
        data = {**self.data, 'submission_token': ApplicationForm().initial['submission_token']}
        self.assertFalse(ApplicationForm(data).is_valid())
        self.assertFalse(ApplicationForm(data, MultiValueDict({f'document_{requirement.pk}': [pdf()]})).is_valid())
        self.assertTrue(ApplicationForm(data, self.uploads()).is_valid())

    def test_legacy_edit_keeps_original_values_and_history_and_can_add_documents(self):
        member = create_member('LEGACY-PRESERVE')
        member.refresh_from_db()
        member.application.refresh_from_db()
        original = deepcopy(member.application.__dict__)
        old_income, old_address = member.monthly_income, member.address
        data = {**profile(), 'control_number': member.control_number, 'disability_type': member.disability_type_id,
                'employment_status': 'retired', 'income_category': 'income_5000_10000',
                'disability_types': [self.other.pk]}
        changed = update_member(member.pk, user=self.admin, version=0, data=data, files=self.uploads(), notes='Fictional supplementary capture')
        self.assertEqual(changed.monthly_income, old_income)
        self.assertEqual(changed.address, old_address)
        self.assertEqual(changed.employment_information, 'Test employment description')
        self.assertEqual(changed.application.documents.count(), 5)
        changed.application.refresh_from_db()
        for name in ('address', 'full_name', 'employment_information', 'monthly_income'):
            self.assertEqual(getattr(changed.application, name), original[name])
        event = changed.events.get(action='profile_updated')
        self.assertEqual(event.changes['employment_status'], {'before': '', 'after': 'retired'})
        self.assertIn('supporting_documents', event.changes)
        with self.assertRaises(ValidationError):
            update_member(member.pk, user=self.admin, version=1, data=data, files=self.uploads(), notes='Cannot overwrite')
        self.assertEqual(changed.application.documents.count(), 5)
        old_caller = {name: value for name, value in data.items() if name != 'disability_types'}
        old_caller['dependents'] = '2'
        updated = update_member(member.pk, user=self.admin, version=1, data=old_caller, notes='Fictional legacy caller')
        self.assertEqual(updated.disability_ids, [self.other.pk])
        cleared = update_member(member.pk, user=self.admin, version=2,
            data={**old_caller, 'disability_selection_present': True, 'income_category': '',
                  'income_category_label': 'Untrusted label'}, notes='Fictional legacy details require fresh review')
        self.assertEqual(cleared.disability_ids, [])
        self.assertIsNotNone(cleared.application.disability_type_id)
        self.assertEqual(cleared.income_category_label, '')

    def test_edit_audit_rollback_and_multiple_disability_eligibility(self):
        member = self.member()
        program = create_program()
        program.eligible_disability_types.set([self.other])
        self.assertTrue(disability_matches(program, member))
        updated = {**self.data, 'disability_types': [self.other.pk], 'dependents': '3'}
        with patch('members.services.record_event', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                update_member(member.pk, user=self.admin, version=0, data=updated, notes='Fictional update')
        member.refresh_from_db()
        self.assertEqual(member.dependents, 0)
        self.assertEqual(len(member.disability_ids), 2)
        changed = update_member(member.pk, user=self.admin, version=0, data=updated, notes='Fictional update')
        self.assertEqual(changed.disability_ids, [self.other.pk])
        self.assertEqual(changed.application.disability_ids, sorted(self.data['disability_types']))
        self.assertEqual(changed.events.get().changes['dependents'], {'before': '0', 'after': '3'})

    def test_private_previews_review_history_profile_and_public_boundaries(self):
        member = self.member(True)
        document = member.application.documents.get(requirement__capture_key='photo_1x1')
        url = reverse('members:document', args=[member.pk, document.pk]) + '?preview=1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('inline'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        self.assertEqual(Client().get(url).status_code, 302)
        viewer = get_user_model().objects.create_user('profile_only', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'members.view_member')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        detail = self.client.get(reverse('members:detail', args=[member.pk]))
        self.assertContains(detail, self.other.name)
        self.assertContains(detail, 'Address Information')
        self.assertNotContains(detail, '?preview=1')
        self.client.force_login(self.admin)
        for verified in (True, False):
            verify_document(document.pk, user=self.admin, member_version=member.version,
                verified=verified, expires_on=None, reason='Fictional document review')
        self.assertEqual(document.verifications.count(), 2)
        self.assertEqual(self.client.post(reverse('core:membership'), self.data).status_code, 405)
        self.assertNotContains(Client().get(reverse('core:membership')), 'name="first_name"')

    def test_failed_profile_audit_removes_uncommitted_uploads(self):
        member = self.member()
        with patch('members.services.record_event', side_effect=RuntimeError('Fictional audit failure')):
            with self.assertRaises(RuntimeError):
                update_member(member.pk, user=self.admin, version=0, data=self.data, files=self.uploads(),
                    notes='Fictional additional evidence capture')
        member.refresh_from_db()
        self.assertEqual(member.version, 0)
        self.assertFalse(member.application.documents.exists())
        self.assertFalse(any(path.is_file() for path in Path(settings.MEDIA_ROOT).rglob('*')))

    @override_settings(MEMBERSHIP_TOTAL_MAX_BYTES=10)
    def test_over_limit_edit_rejects_partial_profile_and_service_uploads(self):
        member = self.member()
        uploads = self.uploads()
        data = {**self.data, 'version': 0, 'notes': 'Fictional size rejection', 'dependents': '4',
                **{key: values[0] for key, values in uploads.lists()}}
        response = self.client.post(reverse('members:edit', args=[member.pk]), data)
        self.assertEqual(response.status_code, 413)
        with self.assertRaises(ValidationError):
            update_member(member.pk, user=self.admin, version=0, data=self.data, files=self.uploads(),
                notes='Fictional service size rejection')
        member.refresh_from_db()
        self.assertEqual(member.dependents, 0)
        self.assertEqual(member.version, 0)
        self.assertFalse(member.application.documents.exists())
