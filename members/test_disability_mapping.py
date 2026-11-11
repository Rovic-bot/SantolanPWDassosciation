from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from membership.pdf_registration_forms import ASSOCIATION_PDF_KIND, AssociationPDFForm
from membership.registration_decisions import member_values
from programs import application_workflow as workflow
from programs.tests import create_program
from programs.test_ui_cleanup import seed_catalog
from .disability_catalog import ASSOCIATION_LABELS, association_types
from .models import DisabilityType, MemberEvent
from .services import repair_disability_link
from .tests import create_member


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class AssociationClassificationTests(TestCase):
    def setUp(self):
        seed_catalog()
        self.user = get_user_model().objects.create_superuser('synthetic_classification_repair')
        self.member = create_member('SYNTHETIC-LINK')
        self.member.application.decided_by = self.user
        self.member.application.save(update_fields=['decided_by'])
        self.member.disability_type = None
        self.member.disability_information = 'Physical / Orthopedic'
        self.member.registration_profile = {
            'profile_kind': ASSOCIATION_PDF_KIND, 'disability_type': 'Physical / Orthopedic'}
        self.member.contact_number = '09171234567'
        self.member.save()
        self.member.refresh_from_db()

    def repair(self, **changes):
        return repair_disability_link(self.member.pk, **{
            'user': self.user, 'version': self.member.version,
            'notes': 'SYNTHETIC correction of the missing exact Association classification link.', **changes})

    def test_each_association_choice_projects_to_the_same_program_catalog_id(self):
        labels = [label for value, label in AssociationPDFForm().fields['disability_type'].choices if value]
        self.assertEqual(labels, list(ASSOCIATION_LABELS.values()))
        for name, label in ASSOCIATION_LABELS.items():
            with self.subTest(label=label):
                values, classifications = member_values({
                    'profile_kind': ASSOCIATION_PDF_KIND, 'birthdate': '1990-01-01',
                    'disability_type': label}, 'SYNTHETIC-NEW')
                self.assertEqual([item.pk for item in classifications],
                                 [DisabilityType.objects.get(name=name).pk])
                self.assertEqual(values['disability_information'], label)

    def test_unknown_and_inactive_labels_are_not_inferred(self):
        self.assertFalse(association_types('physical / orthopedic').exists())
        self.assertFalse(association_types('Unrecognized declaration').exists())
        DisabilityType.objects.filter(name='Physical Disability (Orthopedic)').update(is_active=False)
        with self.assertRaisesMessage(ValidationError, 'active catalog entry'):
            self.repair()
        self.assertFalse(MemberEvent.objects.exists())

    def test_repair_preserves_profile_and_original_application_and_records_audit(self):
        before = self.member.__class__.objects.filter(pk=self.member.pk).values().get()
        application = self.member.application.__class__.objects.filter(pk=self.member.application_id).values().get()
        result = self.repair()
        after = self.member.__class__.objects.filter(pk=self.member.pk).values().get()
        self.assertEqual({k: v for k, v in before.items() if k not in ('version', 'updated_at')},
                         {k: v for k, v in after.items() if k not in ('version', 'updated_at')})
        self.assertEqual(result.version, before['version'] + 1)
        self.assertEqual(self.member.application.__class__.objects.filter(pk=self.member.application_id).values().get(), application)
        event = result.events.get()
        self.assertEqual(event.action, 'profile_updated')
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.changes, {'disability_types': {'before': '[]', 'after': str(result.disability_ids)}})

    def test_current_mobile_verifies_after_repair_while_wrong_identity_still_fails(self):
        program = create_program(policy_authorized_by=self.user,
            eligible_disability_types=[DisabilityType.objects.get(name='Physical Disability (Orthopedic)').pk])
        identity = {'version': program.version, 'control_number': self.member.control_number,
            'full_name': self.member.full_name, 'birthdate': self.member.birthdate,
            'contact_number': '+63 917 123 4567'}
        self.assertEqual(workflow.verify(program.pk, **identity)[1], 'unable')
        self.repair()
        grant, outcome, _ = workflow.verify(program.pk, **identity)
        self.assertEqual(outcome, 'passed')
        self.assertTrue(workflow.secure_grant(grant, program))
        url = reverse('programs:verify', args=[program.pk])
        self.assertContains(self.client.get(url), 'Mobile number')
        self.assertRedirects(self.client.post(url, identity), reverse('programs:apply', args=[program.pk]))
        for change in ({'contact_number': '09179999999'}, {'full_name': 'Wrong person'}):
            with self.assertRaisesMessage(ValidationError, workflow.FAILED):
                workflow.verify(program.pk, **(identity | change))
        self.assertFalse(program.applications.exists())

    def test_permission_stale_version_and_reason_are_required(self):
        viewer = get_user_model().objects.create_user('synthetic_no_repair_permission', is_staff=True)
        with self.assertRaises(PermissionDenied):
            self.repair(user=viewer)
        for changes in ({'version': self.member.version + 1}, {'notes': ''}):
            with self.assertRaises(ValidationError):
                self.repair(**changes)
        self.assertFalse(MemberEvent.objects.exists())

    def test_existing_classification_cannot_be_overwritten(self):
        self.member.disability_types.add(DisabilityType.objects.get(name='Visual Disability'))
        with self.assertRaisesMessage(ValidationError, 'Review this member manually'):
            self.repair()
        self.assertFalse(MemberEvent.objects.exists())

    def test_conflicting_declaration_requires_manual_review(self):
        self.member.disability_information = 'Hearing'
        self.member.save()
        with self.assertRaisesMessage(ValidationError, 'Review this member manually'):
            self.repair()
        self.assertFalse(MemberEvent.objects.exists())

    def test_audit_failure_rolls_back_link_and_version(self):
        with patch('members.services.record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.repair()
        self.member.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        self.assertFalse(self.member.disability_ids)
