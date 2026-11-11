"""Actual fictional Django Admin requests and diagnostic audit dependencies."""
from unittest.mock import patch

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.urls import reverse

from documents.models import DocumentType, MembershipDocumentRequirement
from members.models import DisabilityType
from membership.models import MembershipSettings
from programs.models import ProgramLog
from . import generation_services as generation
from .generation_models import SourceMutationBatch
from .test_source_writers import SourceHelpers
from .durable_testsupport import DurableHelpers


class ReferenceWriterTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        self.document_type = DocumentType.objects.create(name='Fictional independent document type')
        self.requirement = MembershipDocumentRequirement.objects.create(document_type=self.document_type)
        self.category = DisabilityType.objects.create(name='Fictional unlinked category')
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/old'})
        self.client.force_login(self.officer)
        self.register()

    def post(self, model, pk, data):
        name = f'admin:{model._meta.app_label}_{model._meta.model_name}_change' if pk else f'admin:{model._meta.app_label}_{model._meta.model_name}_add'
        return self.client.post(reverse(name, args=[pk] if pk else []), data)

    def test_all_four_reference_forms_invalidate_with_native_log(self):
        forms = [(DocumentType, self.document_type.pk, {'name': 'Fictional renamed evidence', 'description': ''}),
                 (MembershipDocumentRequirement, self.requirement.pk, {'document_type': self.document_type.pk,
                     'is_active': 'on', 'is_required': 'on', 'position': 1, 'instructions': 'Fictional revised instruction'}),
                 (DisabilityType, self.category.pk, {'name': 'Fictional revised category', 'is_active': 'on'}),
                 (MembershipSettings, 1, {'prpwd_url': 'https://registry.example.test/revised'})]
        for index, (model, pk, data) in enumerate(forms, 2):
            with self.subTest(model=model.__name__):
                self.assertEqual(self.post(model, pk, data).status_code, 302)
                self.assert_transition(index)
        self.assertEqual(SourceMutationBatch.objects.filter(source_kind='reference').count(), 4)

    def test_add_and_unchanged_edit(self):
        self.assertEqual(self.post(DocumentType, None, {'name': 'Fictional added type', 'description': ''}).status_code, 302)
        self.assert_transition(2)
        self.assertEqual(self.post(DocumentType, self.document_type.pk,
            {'name': self.document_type.name, 'description': ''}).status_code, 302)
        self.assert_transition(2)

    def test_failed_validation_has_no_invalidation(self):
        self.assertEqual(self.post(DocumentType, self.document_type.pk, {'name': '', 'description': ''}).status_code, 200)
        self.assert_transition(1)

    def test_protected_program_reference_rules_preserved(self):
        category = self.program.eligible_disability_types.get()
        self.assertEqual(self.post(DisabilityType, category.pk, {'name': 'Forbidden fictional rename', 'is_active': 'on'}).status_code, 200)
        self.assert_transition(1)

    def test_native_audit_missing_or_duplicated_rolls_back(self):
        model_admin = admin.site._registry[DocumentType]
        original = model_admin.log_change
        for mode in ('missing', 'duplicate'):
            def corrupt(*args, **kwargs):
                if mode == 'duplicate':
                    original(*args, **kwargs)
                    return original(*args, **kwargs)
            with self.subTest(mode=mode), patch.object(model_admin, 'log_change', side_effect=corrupt):
                with self.assertRaises(ValidationError):
                    self.post(DocumentType, self.document_type.pk, {'name': 'Fictional attempted rename', 'description': ''})
            self.document_type.refresh_from_db()
            self.assertEqual(self.document_type.name, 'Fictional independent document type')
            self.assert_transition(1)

    def test_generation_audit_failure_rolls_back_reference_and_native_log(self):
        before = LogEntry.objects.count()
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional invalidation failure')):
            with self.assertRaises(ValidationError):
                self.post(DocumentType, self.document_type.pk, {'name': 'Fictional failed rename', 'description': ''})
        self.assertEqual(LogEntry.objects.count(), before)
        self.document_type.refresh_from_db()
        self.assertEqual(self.document_type.name, 'Fictional independent document type')
        self.assert_transition(1)

    def test_permission_recheck_and_bulk_actions_fail_closed(self):
        type(self.officer).objects.filter(pk=self.officer.pk).update(is_superuser=False)
        self.assertEqual(self.post(DocumentType, self.document_type.pk,
            {'name': 'Fictional unauthorized rename', 'description': ''}).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:documents_documenttype_changelist'),
            {'action': 'delete_selected', '_selected_action': self.document_type.pk}).status_code, 403)

    def test_guarded_reference_mutations_cannot_bypass_admin_fence(self):
        actions = [lambda: DocumentType.objects.filter(pk=self.document_type.pk).update(description='Fictional bypass'),
                   lambda: self.document_type.save(),
                   lambda: DocumentType.objects.bulk_create([DocumentType(name='Fictional bulk bypass')]),
                   lambda: DocumentType.objects.bulk_update([self.document_type], ['description']),
                   lambda: self.document_type.delete()]
        for action in actions:
            with self.assertRaises(ValidationError):
                action()
        self.assert_transition(1)


class DiagnosticWriterTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.register()

    def readiness(self):
        from .readiness import evaluate
        from .evidence_services import record_readiness
        result = evaluate(self.application)
        return record_readiness(self.application.pk, user=self.officer,
            expected_context=result['context_digest'], expected_assessments={r['criterion']: r['assessment'] for r in result['criteria']},
            reason='Fictional readiness inspection', confirmed=True, source_expected=self.expected())

    def diagnostic(self):
        from .scoring_inputs import evaluate_application
        from .scoring_services import record_applicant_diagnostic
        result = evaluate_application(self.application, user=self.officer)
        return record_applicant_diagnostic(self.application.pk, program_id=self.program.pk, user=self.officer,
            expected_context=result['context_digest'], reason='Fictional scoring readiness inspection',
            confirmed=True, source_expected=self.expected())

    def test_readiness_native_audit_invalidates_conservatively(self):
        first = self.readiness()
        second = self.readiness()
        self.assertNotEqual(first.pk, second.pk)
        self.assert_transition(3)

    def test_complete_diagnostic_graph_has_seven_native_audits(self):
        self.diagnostic()
        self.assertEqual(len(SourceMutationBatch.objects.get(source_kind='diagnostic').source_audits), 7)
        self.assert_transition(2)

    def test_diagnostic_late_failure_rolls_back_all_artifacts_and_audits(self):
        from .models import CalculationDiagnosticRun
        before = (CalculationDiagnosticRun.objects.count(), ProgramLog.objects.count())
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional audit failure')):
            with self.assertRaises(ValidationError):
                self.diagnostic()
        self.assertEqual(before, (CalculationDiagnosticRun.objects.count(), ProgramLog.objects.count()))
        self.assert_transition(1)
