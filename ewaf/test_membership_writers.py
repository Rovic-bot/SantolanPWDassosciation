"""Fictional onsite intake, native audits, and disposable generation boundary."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils.datastructures import MultiValueDict

from accounts.tests.test_authority_generation import worker
from documents.models import DocumentType, MembershipDocumentRequirement
from members.models import DisabilityType, Member
from membership import services
from membership.forms import ApplicationForm
from membership.models import MembershipSettings, MembershipApplication, MembershipEvent
from membership.tests import onsite_profile, profile, pdf
from . import generation_services as generation
from .generation_models import SourceMutationBatch
from .test_source_writers import SourceHelpers


class MembershipWriterTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/manual'})
        self.requirement = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Fictional intake evidence'))
        self.disability = DisabilityType.objects.create(name='Fictional intake category')
        self.register()

    def form(self):
        form = ApplicationForm({**onsite_profile(), 'disability_type': self.disability.pk,
            'submission_token': ApplicationForm().initial['submission_token']},
            MultiValueDict({f'document_{self.requirement.pk}': [pdf()]}))
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def submit(self, form=None):
        return services.submit_application(form or self.form(), user=self.officer, source_expected={})

    def verify(self, application, **changes):
        return services.record_verification(application.reference, **{
            'user': self.officer, 'version': application.version, 'verified': True,
            'notes': 'Fictional manual verification', 'source_expected': {}, **changes})

    def batches(self, count):
        rows = SourceMutationBatch.objects.filter(source_kind='membership')
        self.assertEqual(rows.count(), count)
        for row in rows:
            self.assertEqual(row.scope_count, 0)
            self.assertEqual(len(row.source_audits), 1)
            generation._validate_batch(row)
        self.assert_transition(1)

    def test_submission_review_approval_zero_program_batches(self):
        application = self.submit()
        application = self.verify(application)
        services.decide_application(application.reference, user=self.officer, version=application.version,
            decision='approved', notes='Fictional approval', source_expected={})
        self.assertTrue(Member.objects.filter(application=application).exists())
        self.batches(3)

    def test_rejection_preserves_manual_failure(self):
        application = self.verify(self.submit(), verified=False)
        services.decide_application(application.reference, user=self.officer, version=application.version,
            decision='rejected', notes='Fictional rejection', source_expected={})
        self.assertFalse(Member.objects.exists())
        self.batches(3)

    def test_duplicate_submission_is_not_a_source_change(self):
        form = self.form()
        first = self.submit(form)
        self.assertEqual(first.pk, self.submit(form).pk)
        self.batches(1)

    def test_missing_manual_verification_cannot_approve(self):
        application = self.submit()
        with self.assertRaises(ValidationError):
            services.decide_application(application.reference, user=self.officer, version=application.version,
                decision='approved', notes='Fictional premature approval', source_expected={})
        self.batches(1)

    def test_changed_form_snapshot_rejected(self):
        form = self.form()
        self.requirement.instructions = 'Changed fictional instructions'
        self.requirement.save()
        with self.assertRaisesMessage(ValidationError, 'MEMBERSHIP_REQUIREMENTS_CHANGED'):
            self.submit(form)
        self.assertFalse(MembershipApplication.objects.exists())
        self.batches(0)

    def test_missing_or_fabricated_program_scope_rejected(self):
        for expected in (None, self.expected()):
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                services.submit_application(self.form(), user=self.officer, source_expected=expected)
        self.batches(0)

    def test_native_missing_duplicate_and_forged_audits_roll_back(self):
        original = services.record_event
        for mode in ('missing', 'duplicate', 'forged'):
            def corrupt(*args, **kwargs):
                if mode == 'missing':
                    return None
                row = original(*args, **kwargs)
                if mode == 'duplicate':
                    original(*args, **kwargs)
                else:
                    MembershipEvent.objects.filter(pk=row.pk).update(description='Forged fictional description')
                return row
            with self.subTest(mode=mode), patch.object(services, 'record_event', side_effect=corrupt):
                with self.assertRaises(ValidationError):
                    self.submit()
            self.assertFalse(MembershipApplication.objects.exists())
        self.batches(0)

    def test_late_batch_failure_removes_new_file_and_rolls_back(self):
        from django.conf import settings
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional failure')):
            with self.assertRaises(ValidationError):
                self.submit()
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse([p for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()])
        self.batches(0)

    def test_review_failure_preserves_existing_evidence(self):
        application = self.submit()
        document = application.documents.get()
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional failure')):
            with self.assertRaises(ValidationError):
                self.verify(application)
        application.refresh_from_db()
        self.assertIsNone(application.prpwd_verified)
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.batches(1)

    def test_stale_version_and_revoke_restore_are_distinct(self):
        application = self.submit()
        first_version = application.version
        application = self.verify(application)
        with self.assertRaises(ValidationError):
            self.verify(application, version=first_version)
        application = self.verify(application, verified=False)
        self.verify(application, verified=True)
        self.batches(4)

    def test_sql_terms_before_settings_and_intake(self):
        application = self.submit()
        with CaptureQueriesContext(connection) as queries:
            self.verify(application)
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        self.assertIn('programs_programtermslock', locks[0])
        self.assertIn('ewaf_authoritygeneration', locks[1])
        settings_at = next(i for i, q in enumerate(locks) if 'membership_membershipsettings' in q)
        intake_at = next(i for i, q in enumerate(locks) if 'membership_membershipapplication' in q)
        self.assertLess(settings_at, intake_at)

    def test_separate_connection_reviews_wait_then_reject_stale_version(self):
        application = self.submit()
        entered, release = Event(), Event()
        original = services.record_event
        def pause(*args, **kwargs):
            row = original(*args, **kwargs)
            if not entered.is_set():
                entered.set()
                if not release.wait(15):
                    raise RuntimeError('Fictional race timeout')
            return row
        with patch.object(services, 'record_event', side_effect=pause), ThreadPoolExecutor(2) as pool:
            first = pool.submit(worker, lambda: self.verify(application))
            self.assertTrue(entered.wait(10))
            second = pool.submit(worker, lambda: self.verify(application, verified=False))
            try:
                with self.assertRaises(TimeoutError):
                    second.result(timeout=.25)
            finally:
                release.set()
            first_id, first_result = first.result(timeout=20)
            with self.assertRaises(ValidationError):
                second.result(timeout=20)
        self.assertIsInstance(first_result, MembershipApplication)
        self.batches(2)
