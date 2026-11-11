"""Separate MySQL connections demonstrate read-only change detection, not promotion."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connections, connection
from django.test import TransactionTestCase

from members.services import change_status
from members.tests import create_member
from programs.testsupport import application_fixture
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .pool_services import inspect_program_pool, _observe


class PoolConcurrencyTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_scoring()
        self.assertEqual(connection.vendor, 'mysql', 'These tests require real MySQL.')

    def change_between_observations(self, mutation):
        observed, resume = Event(), Event()
        calls = 0

        def held_observation(*args):
            nonlocal calls
            value = _observe(*args)
            calls += 1
            if calls == 1:
                observed.set()
                if not resume.wait(timeout=20):
                    raise RuntimeError('Fictional reader coordination timed out')
            return value

        def reader():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT CONNECTION_ID()')
                    identity = cursor.fetchone()[0]
                return identity, inspect_program_pool(self.program.pk, user=self.officer)
            finally:
                connections.close_all()

        with connection.cursor() as cursor:
            cursor.execute('SELECT CONNECTION_ID()')
            writer_id = cursor.fetchone()[0]
        with patch('ewaf.pool_services._observe', side_effect=held_observation), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reader)
            try:
                self.assertTrue(observed.wait(timeout=15))
                mutation()  # Real committed source writer on the other connection.
            finally:
                resume.set()
            reader_id, result = future.result(timeout=30)
        self.assertNotEqual(reader_id, writer_id)
        self.assertFalse(result['observations_match'])
        self.assertFalse(result['inventory_complete'])
        self.assertFalse(result['calculation_complete'])
        self.assertIsNone(result['context_digest'])
        self.assertEqual(result['manifest'], [])
        self.assertIn('POOL_CONTEXT_CHANGED', result['reasons'])

    def test_member_status_writer_detected(self):
        self.change_between_observations(lambda: change_status(self.member.pk, user=self.officer,
            version=self.member.version, status='inactive', notes='Fictional pool concurrency test'))

    def test_document_revocation_detected(self):
        self.assess('ND')
        self.change_between_observations(lambda: self.verify(verified=False))

    def test_new_assessment_detected(self):
        self.change_between_observations(lambda: self.assess('ND'))

    def test_configuration_validation_revision_detected(self):
        self.change_between_observations(self.validate)

    def test_new_pool_member_detected(self):
        member = create_member('SYN-POOL-CONCURRENCY')
        self.change_between_observations(lambda: application_fixture(self.program, member))

    def other_selected_application(self):
        from .test_evidence_concurrency import EvidenceConcurrencyTests
        return EvidenceConcurrencyTests.other_selected_application(self)

    def test_cross_program_receipt_detected(self):
        from assistance.services import record_release
        from assistance.tests import release_data
        other = self.other_selected_application()
        self.change_between_observations(lambda: record_release(other.pk, user=self.officer, data=release_data(other)))

    def test_cross_program_receipt_void_detected(self):
        from assistance.services import record_release, void_release
        from assistance.tests import release_data
        other = self.other_selected_application()
        receipt = record_release(other.pk, user=self.officer, data=release_data(other))
        other.refresh_from_db()
        self.change_between_observations(lambda: void_release(other.pk, receipt.pk, user=self.officer,
            data={'version': other.version, 'notes': 'Fictional pool receipt void', 'confirm': True}))

    def test_failed_source_audit_rolls_back_and_preserves_context(self):
        before = inspect_program_pool(self.program.pk, user=self.officer)
        with patch('members.services.record_event', side_effect=RuntimeError('Fictional audit outage')):
            with self.assertRaises(RuntimeError):
                change_status(self.member.pk, user=self.officer, version=self.member.version,
                              status='inactive', notes='Fictional rollback test')
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)
        after = inspect_program_pool(self.program.pk, user=self.officer)
        self.assertEqual(before['context_digest'], after['context_digest'])
        self.assertFalse(after['calculation_complete'])
