"""Fictional shared-member fan-out, evidence, rollback and locking."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from accounts.tests.test_authority_generation import worker
from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument, DocumentVerification
from documents.services import verify_document
from members import services
from members.models import Member, MemberEvent
from members.tests import create_member
from membership.forms import PROFILE_FIELDS
from membership.tests import profile, pdf
from programs.models import ProgramApplication
from programs.tests import create_program
from programs.testsupport import application_fixture
from . import generation_services as generation
from .generation_models import ProgramSourceState, SourceMutationBatch
from .test_source_writers import SourceHelpers


class MemberWriterTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        self.other = create_program(name='Fictional second retained program')
        self.member = create_member('FICTIONAL-SHARED-001')
        self.member.refresh_from_db()
        for program, status in ((self.program, 'ELIGIBLE'), (self.other, 'CLOSED')):
            application = application_fixture(program, self.member)
            ProgramApplication.objects.filter(pk=application.pk).update(status=status)
        requirement = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Fictional shared evidence'))
        self.document = MembershipApplicationDocument.objects.create(application=self.member.application,
            requirement=requirement, label='Fictional evidence', file=pdf(), content_type='application/pdf', size=34)
        self.bootstrap([self.program.pk, self.other.pk])
        self.register()

    def expected(self):
        return {str(p.pk): self.token(p) for p in (self.program, self.other)}

    def status(self, status='inactive', **kwargs):
        self.member.refresh_from_db()
        return services.change_status(self.member.pk, **{'user': self.officer, 'version': self.member.version,
            'status': status, 'notes': 'Fictional source review', 'source_expected': self.expected(), **kwargs})

    def review(self, **kwargs):
        return verify_document(self.document.pk, **{'user': self.officer, 'member_version': self.member.version,
            'verified': True, 'expires_on': None, 'reason': 'Fictional evidence review',
            'source_expected': self.expected(), **kwargs})

    def check_states(self, value):
        self.assertEqual(list(ProgramSourceState.objects.order_by('program_id').values_list('generation', flat=True)), [value, value])
        for batch in SourceMutationBatch.objects.all():
            generation._validate_batch(batch)
        for state in ProgramSourceState.objects.all():
            generation._state(state)

    def test_profile_update_fans_out_to_closed_and_eligible_inventory(self):
        data = {**profile(), 'control_number': self.member.control_number,
            'disability_type': self.member.disability_type_id, 'full_name': 'Fictional corrected name'}
        old_intake = self.member.application.full_name
        services.update_member(self.member.pk, user=self.officer, version=self.member.version,
            data=data, notes='Fictional profile correction', source_expected=self.expected())
        self.check_states(2)
        self.assertEqual(self.member.application.full_name, old_intake)
        self.assertEqual(SourceMutationBatch.objects.filter(kind='SOURCE_CHANGE').get().scope_count, 2)

    def test_status_changed_restored_does_not_restore_token(self):
        old = self.expected()
        self.status()
        self.status('active')
        self.check_states(3)
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.status(source_expected=old)

    def test_onsite_sources_change_all_retained_program_generations_and_audit_old_values(self):
        from members.profile import INCOME
        data = {**profile(), 'control_number': self.member.control_number,
            'disability_type': self.member.disability_type_id, 'income_category': 'income_5000_10000',
            'employment_status': 'student', 'dependents': '4'}
        services.update_member(self.member.pk, user=self.officer, version=self.member.version,
            data=data, notes='Fictional onsite source review', source_expected=self.expected())
        self.check_states(2)
        self.member.refresh_from_db()
        self.assertEqual(self.member.income_category_label, dict(INCOME)['income_5000_10000'])
        event = self.member.events.get()
        self.assertEqual(event.changes['dependents'], {'before': '0', 'after': '4'})
        self.assertEqual(event.changes['employment_status'], {'before': '', 'after': 'student'})
        self.assertEqual(event.actor_id, self.officer.pk)
        self.assertEqual(self.member.application.income_category, '')

    def test_genuinely_unchanged_status_has_no_batch(self):
        with self.assertRaises(ValidationError):
            self.status('active')
        self.check_states(1)
        self.assertFalse(MemberEvent.objects.exists())

    def test_missing_or_partial_scope_rejected(self):
        for expected in (None, {}, {str(self.program.pk): self.token()}):
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                self.status(source_expected=expected)
        self.check_states(1)

    def test_stale_version_rejected(self):
        with self.assertRaises(ValidationError):
            self.status(version=88)
        self.check_states(1)

    def test_missing_state_denied_without_member_change(self):
        third = create_program(name='Fictional uninitialized program')
        application_fixture(third, self.member)
        expected = {**self.expected(), str(third.pk): self.token()}
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            self.status(source_expected=expected)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_audit_and_second_program_cas_failures_roll_back_entire_fanout(self):
        original = generation._cas_source
        def second_failure(state, event):
            if state.program_id == self.other.pk:
                raise ValidationError('Fictional second scope CAS failure')
            original(state, event)
        for name, target, effect in (('audit', services, lambda *a, **k: None),
                                    ('cas', generation, second_failure)):
            field = 'record_event' if name == 'audit' else '_cas_source'
            with self.subTest(failure=name), patch.object(target, field, side_effect=effect):
                with self.assertRaises(ValidationError):
                    self.status()
            self.member.refresh_from_db()
            self.assertTrue(self.member.is_active)
            self.assertFalse(MemberEvent.objects.exists())
            self.check_states(1)

    def test_native_duplicate_and_wrong_member_are_rejected(self):
        original = services.record_event
        other = create_member('FICTIONAL-OTHER-MEMBER')
        for mode in ('duplicate', 'wrong_member'):
            def corrupt(*args, **kwargs):
                row = original(*args, **kwargs)
                if mode == 'duplicate':
                    original(*args, **kwargs)
                else:
                    MemberEvent.objects.filter(pk=row.pk).update(member=other)
                return row
            with self.subTest(mode=mode), patch.object(services, 'record_event', side_effect=corrupt):
                with self.assertRaises(ValidationError):
                    self.status()
            self.check_states(1)

    def test_current_actor_reauthorization(self):
        type(self.officer).objects.filter(pk=self.officer.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.status()
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_document_review_and_revocation_both_fan_out(self):
        first = self.review()
        self.review(verified=False)
        self.assertEqual(DocumentVerification.objects.count(), 2)
        self.assertTrue(DocumentVerification.objects.get(pk=first.pk).verified)
        self.check_states(3)
        for batch in SourceMutationBatch.objects.filter(source_kind='member_document'):
            self.assertEqual({ref['model'] for ref in batch.source_audits},
                {'members.memberevent', 'documents.documentverification'})

    def test_expired_or_missing_document_cannot_be_verified(self):
        from datetime import timedelta
        with self.assertRaises(ValidationError):
            self.review(expires_on=timezone.localdate() - timedelta(days=1))
        self.document.file.storage.delete(self.document.file.name)
        with self.assertRaises(ValidationError):
            self.review()
        self.check_states(1)

    def test_document_late_failure_rolls_back_review_and_preserves_file(self):
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional audit failure')):
            with self.assertRaises(ValidationError):
                self.review()
        self.assertFalse(DocumentVerification.objects.exists())
        self.assertFalse(MemberEvent.objects.exists())
        self.assertTrue(self.document.file.storage.exists(self.document.file.name))
        self.check_states(1)

    def test_sql_all_programs_before_states_before_applications_before_member(self):
        expected = self.expected()
        with CaptureQueriesContext(connection) as queries:
            self.status(source_expected=expected)
        # status() token helper is evaluated before calling the adapter; exclude its
        # inspection queries by finding the final transaction's Terms prefix.
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        start = max(i for i, q in enumerate(locks) if 'programs_programtermslock' in q)
        locks = locks[start:]
        self.assertIn('ewaf_authoritygeneration', locks[1])
        self.assertTrue(all('FROM `programs_program`' in q for q in locks[2:4]))
        self.assertTrue(all('ewaf_programsourcestate' in q for q in locks[4:6]))
        self.assertIn('programs_programapplication', locks[6])
        self.assertIn('FROM `members_member`', locks[7])
        self.assertNotIn('JOIN', locks[7])

    def test_separate_connections_conflict_across_complete_scope(self):
        expected = self.expected()
        entered, release = Event(), Event()
        original = services.record_event
        def pause(*args, **kwargs):
            row = original(*args, **kwargs)
            entered.set()
            if not release.wait(15):
                raise RuntimeError('Fictional race timeout')
            return row
        with patch.object(services, 'record_event', side_effect=pause), ThreadPoolExecutor(2) as pool:
            first = pool.submit(worker, lambda: self.status(source_expected=expected))
            self.assertTrue(entered.wait(10))
            second = pool.submit(worker, lambda: self.review(source_expected=expected))
            try:
                with self.assertRaises(TimeoutError):
                    second.result(timeout=.25)
            finally:
                release.set()
            first.result(timeout=20)
            with self.assertRaises(ValidationError):
                second.result(timeout=20)
        self.assertFalse(DocumentVerification.objects.exists())
        self.check_states(2)
