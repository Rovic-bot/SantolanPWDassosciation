"""Separate-connection MySQL transactions; synchronization is not mocked locking."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Barrier, Event
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from assistance.services import record_release, void_release
from assistance.tests import release_data
from members.services import change_status
from .durable_testsupport import DurableHelpers
from .durable_models import DurableRun, DurableOutcome
from .durable_services import inspect_development_result
from . import test_evidence_concurrency


def worker(action):
    close_old_connections()
    try:
        try:
            return action()
        except ValidationError as error:
            return error
    finally:
        connections.close_all()


class DurableConcurrencyTests(DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()

    def test_concurrent_same_request_has_one_successful_graph(self):
        request = self.request_run()
        barrier = Barrier(2)
        def process():
            barrier.wait(timeout=15)
            return self.process(request)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, process) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        successful = [result for result in results if not isinstance(result, ValidationError)]
        self.assertTrue(successful)
        self.assertEqual(len({result.pk for result in successful}), 1)
        self.assertEqual(DurableRun.objects.count(), 1)
        self.assertEqual(DurableOutcome.objects.filter(status='COMPLETED').count(), 1)

    def test_concurrent_duplicate_request_creation(self):
        barrier = Barrier(2)
        def create():
            barrier.wait(timeout=15)
            return self.request_run()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=30) for future in [pool.submit(worker, create) for _ in range(2)]]
        self.assertEqual(results[0].pk, results[1].pk)

    def hold_writer_then_process(self, target, action, writer):
        """Writer holds its actual existing source lock before graph capture."""
        request = self.request_run()
        entered, release, capture_started = Event(), Event(), Event()
        def held(*args, **kwargs):
            result = action(*args, **kwargs)
            entered.set()
            if not release.wait(timeout=15):
                raise RuntimeError('Fictional writer coordination timeout')
            return result
        def process():
            capture_started.set()
            return self.process(request)
        with patch(target, side_effect=held), ThreadPoolExecutor(max_workers=2) as pool:
            writing = pool.submit(worker, writer)
            try:
                self.assertTrue(entered.wait(timeout=10))
                processing = pool.submit(worker, process)
                self.assertTrue(capture_started.wait(timeout=10))
                with self.assertRaises(FutureTimeout):
                    processing.result(timeout=.25)
            finally:
                release.set()
            self.assertNotIsInstance(writing.result(timeout=20), ValidationError)
            self.assertIsInstance(processing.result(timeout=20), ValidationError)
        self.assertFalse(DurableRun.objects.exists())
        self.assertEqual(DurableOutcome.objects.get().status, 'FAILED')

    def test_member_writer_blocks_then_invalidates_capture(self):
        from members.services import record_event
        self.hold_writer_then_process('members.services.record_event', record_event,
            lambda: change_status(self.member.pk, user=self.officer, version=self.member.version,
                                  status='inactive', notes='Fictional concurrency correction'))

    def test_document_writer_blocks_then_invalidates_capture(self):
        from members.services import record_event
        self.hold_writer_then_process('members.services.record_event', record_event,
                                      lambda: self.verify(verified=False))

    def test_configuration_writer_blocks_then_invalidates_capture(self):
        from .configuration_services import persist
        self.hold_writer_then_process('ewaf.configuration_services.persist', persist, self.validate)

    def test_eligibility_pool_exit_blocks_then_invalidates_capture(self):
        from programs.services import change_application, record_log
        self.application.refresh_from_db()
        self.hold_writer_then_process('programs.services.record_log', record_log,
            lambda: change_application(self.application.pk, user=self.officer, version=self.application.version,
                                       status='CLOSED', notes='Fictional reasoned pool exit'))

    def test_cross_program_new_receipt_blocks_then_invalidates(self):
        from assistance.services import record_log
        other = test_evidence_concurrency.EvidenceConcurrencyTests.other_selected_application(self)
        self.hold_writer_then_process('assistance.services.record_log', record_log,
            lambda: record_release(other.pk, user=self.officer, data=release_data(other)))

    def test_cross_program_void_blocks_then_invalidates(self):
        from assistance.services import record_log
        other = test_evidence_concurrency.EvidenceConcurrencyTests.other_selected_application(self)
        receipt = record_release(other.pk, user=self.officer, data=release_data(other))
        other.refresh_from_db()
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            self.assess(code)
        self.hold_writer_then_process('assistance.services.record_log', record_log,
            lambda: void_release(other.pk, receipt.pk, user=self.officer,
                data={'version': other.version, 'notes': 'Fictional receipt void', 'confirm': True}))

    def test_capture_locks_block_writer_then_completed_history_becomes_stale(self):
        from .durable_services import _calculate
        request = self.request_run()
        entered, resume, writing_started = Event(), Event(), Event()
        def hold(snapshot):
            entered.set()
            if not resume.wait(timeout=15):
                raise RuntimeError('Fictional capture coordination timeout')
            return _calculate(snapshot)
        def write():
            writing_started.set()
            return change_status(self.member.pk, user=self.officer, version=self.member.version,
                                 status='inactive', notes='Fictional change after calculation')
        with patch('ewaf.durable_services._calculate', side_effect=hold), ThreadPoolExecutor(max_workers=2) as pool:
            processing = pool.submit(worker, lambda: self.process(request))
            try:
                self.assertTrue(entered.wait(timeout=10))
                writing = pool.submit(worker, write)
                self.assertTrue(writing_started.wait(timeout=10))
                with self.assertRaises(FutureTimeout):
                    writing.result(timeout=.25)
            finally:
                resume.set()
            run = processing.result(timeout=20)
            self.assertNotIsInstance(run, ValidationError)
            self.assertNotIsInstance(writing.result(timeout=20), ValidationError)
        self.assertEqual(DurableOutcome.objects.get().status, 'COMPLETED')
        with self.assertRaises(ValidationError):
            inspect_development_result(run.pk, program_id=self.program.pk, user=self.officer)
