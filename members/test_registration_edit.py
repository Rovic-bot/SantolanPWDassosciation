"""Current member updates retain onsite field parity and protected history."""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from membership.models import MembershipApplication
from membership.pdf_registration_forms import AssociationPDFForm
from membership.registration_decisions import member_values
from membership.registration_forms import OnsiteRegistrationForm
from membership.test_pdf_registration import association_data, pdf_policy
from ewaf.test_source_writers import SourceHelpers
from .models import Member, DisabilityType
from .registration_form import MemberRegistrationForm
from .services import update_member, change_status


class MemberRegistrationEditTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser('synthetic_profile_editor')
        self.classification = DisabilityType.objects.get_or_create(name='Visual Disability')[0]
        self.data = association_data() | {'pwd_number': '00-1234-000-0000001',
            'contact_number': '09170000000', 'spouse_name': 'Recorded spouse',
            'spouse_contact': '09170000001', 'guardian_name': 'Recorded guardian',
            'guardian_contact': '09170000002', 'zip_code': '01610',
            'philhealth_number': '0001-0002', 'voter_certification_number': '0003-0004'}
        source_form = AssociationPDFForm(self.data)
        self.assertTrue(source_form.is_valid(), source_form.errors)
        self.source = source_form.submitted_data()
        values, types = member_values(self.source, self.data['pwd_number'])
        self.application = MembershipApplication.objects.create(**values,
            submission_key=uuid.uuid4(), status='approved')
        self.member = Member.objects.create(application=self.application, **(values | {
            'monthly_income': Decimal('4321.00'), 'dependents': 2}))
        self.member.disability_types.set(types)
        self.member.refresh_from_db()
        self.url = reverse('members:edit', args=[self.member.pk])
        self.client.force_login(self.actor)

    def post_data(self, **changes):
        form = MemberRegistrationForm(instance=self.member)
        values = {name: form.initial.get(name, '') for name in form.fields if not name.startswith('document_')}
        return {name: '' if value is None else value for name, value in values.items()} | {
            'notes': 'Authorized synthetic profile correction.', 'acknowledgement': 'on', **changes}

    def test_edit_uses_current_onsite_fields_groups_choices_and_prefills(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'membership/onsite/section.html')
        current = response.context['form']
        onsite = OnsiteRegistrationForm(policy=pdf_policy())
        self.assertEqual([(title, [f.name for f in fields]) for title, fields in current.profile_sections],
                         [(title, [f.name for f in fields]) for title, fields in onsite.profile_sections])
        for name in AssociationPDFForm.base_fields:
            self.assertEqual(current.fields[name].label, onsite.fields[name].label, name)
            if name == 'email':
                # New onsite intake requires email; existing member corrections
                # retain the optional email contract for earlier records.
                self.assertFalse(current.fields[name].required)
                self.assertTrue(onsite.fields[name].required)
            else:
                self.assertEqual(current.fields[name].required, onsite.fields[name].required, name)
            self.assertEqual(getattr(current.fields[name], 'choices', None), getattr(onsite.fields[name], 'choices', None), name)
        self.assertEqual(current.initial['guardian_contact'], '09170000002')
        self.assertEqual(current.initial['zip_code'], '01610')
        self.assertEqual(current.initial['pwd_number'], self.member.control_number)
        self.assertContains(response, 'name="acknowledgement"')
        for slot in ('photo_2x2', 'civil_document', 'voter_certificate', 'civil_alternative'):
            self.assertContains(response, f'name="{slot}"')
        self.assertFalse(current.initial['acknowledgement'])
        self.assertNotContains(response, 'name="monthly_income"')
        self.assertContains(response, 'name="notes"')

    def test_family_only_edit_is_saved_audited_and_leaves_original_untouched(self):
        response = self.client.post(self.url, self.post_data(guardian_name='Updated guardian'))
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.member.registration_profile['guardian_name'], 'Updated guardian')
        self.assertEqual(self.application.registration_profile, self.source)
        self.assertEqual(self.member.monthly_income, Decimal('4321.00'))
        self.assertEqual(self.member.dependents, 2)
        self.assertEqual(self.member.disability_ids, [self.classification.pk])
        event = self.member.events.get()
        self.assertIn('registration_profile', event.changes)
        self.assertContains(self.client.get(reverse('members:detail', args=[self.member.pk])), 'Updated guardian')

    def test_household_and_common_fields_update_current_columns_and_history(self):
        update_member(self.member.pk, user=self.actor, version=0,
            data=self.post_data(first_name='Updated', house_street='25 Other Street',
                household_monthly_income='12000.00', household_members=3), notes='Verified correction')
        self.member.refresh_from_db()
        self.assertEqual(self.member.full_name, 'Updated Example')
        self.assertIn('25 Other Street', self.member.address)
        self.assertEqual(self.member.household_monthly_income, Decimal('12000'))
        self.assertEqual(self.member.household_members, 3)
        self.assertEqual(self.member.monthly_income, Decimal('4321'))
        self.assertEqual(self.member.dependents, 2)
        self.assertIn('household_members', self.member.events.get().changes)

    def test_invalid_numbers_dates_household_and_reason_do_not_write(self):
        for changes in ({'pwd_number': ''}, {'pwd_number': 'INVALID-NEW'},
                        {'spouse_contact': '09abc'}, {'birthdate': '2999-01-01'},
                        {'household_monthly_income': '-1'}, {'household_members': '0'}, {'notes': ''}):
            response = self.client.post(self.url, self.post_data(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors, changes)
        self.member.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        self.assertFalse(self.member.events.exists())

    def test_noop_stale_archived_and_audit_failure_preserve_record(self):
        with self.assertRaisesMessage(ValidationError, 'No profile changes'):
            update_member(self.member.pk, user=self.actor, version=0, data=self.post_data(), notes='No change')
        with patch('members.services.record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                update_member(self.member.pk, user=self.actor, version=0,
                    data=self.post_data(spouse_name='Not saved'), notes='Correction')
        self.member.refresh_from_db()
        self.assertEqual(self.member.registration_profile, self.source)
        with self.assertRaises(ValidationError):
            update_member(self.member.pk, user=self.actor, version=99, data=self.post_data(), notes='Stale')
        change_status(self.member.pk, user=self.actor, version=0, status='archived', notes='Archive')
        with self.assertRaisesMessage(ValidationError, 'Restore this archived member'):
            update_member(self.member.pk, user=self.actor, version=1,
                data=self.post_data(spouse_name='Not saved'), notes='Correction')

    def test_legacy_values_are_prefilled_without_inventing_missing_details(self):
        self.member.registration_profile = {}
        self.member.first_name = self.member.last_name = ''
        self.member.household_members = self.member.household_monthly_income = None
        self.member.control_number = 'LEGACY-ID-001'
        form = MemberRegistrationForm(instance=self.member)
        self.assertEqual(form.initial['first_name'], '')
        self.assertIsNone(form.initial['household_members'])
        self.assertNotIn('family_members', form.initial)
        self.assertEqual(form.fields['pwd_number'].recorded_value, 'LEGACY-ID-001')
        self.assertIn(('Recorded full name', self.member.full_name), form.retained_information)

    def test_exact_disability_mapping_preserves_other_edits_and_audits_changes(self):
        physical = DisabilityType.objects.get_or_create(name='Physical Disability (Orthopedic)')[0]
        other = DisabilityType.objects.get_or_create(name='Hearing Disability')[0]
        self.member.disability_types.add(other)
        update_member(self.member.pk, user=self.actor, version=0,
            data=self.post_data(spouse_name='Updated'), notes='Family correction')
        self.member.refresh_from_db()
        self.assertCountEqual(self.member.disability_ids, [self.classification.pk, other.pk])
        update_member(self.member.pk, user=self.actor, version=1,
            data=self.post_data(disability_type='Physical / Orthopedic'), notes='Changed declaration')
        self.member.refresh_from_db()
        self.assertEqual(self.member.disability_information, 'Physical / Orthopedic')
        self.assertEqual(self.member.disability_ids, [physical.pk])
        self.assertEqual(self.member.events.first().changes['disability_types']['before'],
                         str(sorted([self.classification.pk, other.pk])))

    def test_permissions_and_duplicate_formatted_id_remain_enforced(self):
        viewer = get_user_model().objects.create_user('synthetic_no_profile_permission', is_staff=True)
        with self.assertRaises(PermissionDenied):
            update_member(self.member.pk, user=viewer, version=0, data=self.post_data(), notes='Denied')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        other_application = MembershipApplication.objects.create(**{
            key: getattr(self.application, key) for key in ('full_name', 'birthdate', 'address',
                'contact_number', 'disability_information', 'employment_information')},
            control_number='123-456', submission_key=uuid.uuid4())
        Member.objects.create(application=other_application, full_name='Other', birthdate='1990-01-01',
            address='Synthetic', control_number='123-456')
        form = MemberRegistrationForm(self.post_data(pwd_number='123456'), instance=self.member)
        self.assertFalse(form.is_valid())
        self.assertIn('pwd_number', form.errors)

    def test_existing_suffix_and_recorded_choice_survive_a_family_edit(self):
        self.member.suffix = 'Jr.'
        self.member.full_name += ' Jr.'
        self.member.registration_profile['civil_status'] = 'Widowed'
        self.member.civil_status = 'widowed'
        self.member.save()
        form = MemberRegistrationForm(instance=self.member)
        self.assertIn(('Widowed', 'Widowed'), form.fields['civil_status'].choices)
        update_member(self.member.pk, user=self.actor, version=0,
            data=self.post_data(spouse_name='Updated'), notes='Family correction')
        self.member.refresh_from_db()
        self.assertEqual(self.member.full_name, 'Fictional Example Jr.')
        self.assertEqual(self.member.suffix, 'Jr.')
        self.assertEqual(self.member.civil_status, 'widowed')


class MemberRegistrationSourceTests(SourceHelpers, TransactionTestCase):
    def test_current_field_update_uses_existing_source_audit_and_invalidation(self):
        from members.tests import create_member
        from programs.testsupport import application_fixture
        from ewaf.generation_models import ProgramSourceState, SourceMutationBatch
        self.setup_foundation()
        member = create_member('FICTIONAL-RETAINED-ID')
        original = member.application.registration_profile.copy()
        application_fixture(self.program, member)
        self.bootstrap([self.program.pk])
        self.register()
        data = association_data() | {'pwd_number': member.control_number,
            'household_monthly_income': '12000', 'member_profile_format': 'association_pdf_v1',
            'version': member.version, 'notes': 'Fictional current source correction'}
        update_member(member.pk, user=self.officer, version=member.version, data=data,
            notes=data['notes'], source_expected={str(self.program.pk): self.token()})
        member.refresh_from_db()
        member.application.refresh_from_db()
        self.assertEqual(member.household_monthly_income, Decimal('12000.00'))
        self.assertEqual(member.application.registration_profile, original)
        self.assertIn('registration_profile', member.events.get().changes)
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, 2)
        self.assertEqual(SourceMutationBatch.objects.filter(kind='SOURCE_CHANGE').get().scope_count, 1)
