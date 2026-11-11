"""Private-access native audits participate without narrowing Gate 1 dependencies."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, Client
from django.urls import reverse

from accounts.tests.test_authority_generation import worker
from programs.models import ProgramLog
from . import generation_services as generation, generation_processing as processing
from .test_source_writers import SourceHelpers
from .durable_testsupport import DurableHelpers
from .generation_models import ProgramSourceState, SourceMutationBatch


class AccessWriterTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    def prepare_relevance(self, kind='document'):
        return super().prepare_relevance(kind=kind)

    def setUp(self):
        self.setup_durable()
        self.client.force_login(self.officer)
        self.register()

    def routes(self):
        document = self.application.documents.get()
        return [reverse('programs:photo', args=[self.application.pk, self.application.current_photo_id]),
                reverse('programs:document', args=[self.program.pk, self.application.pk, document.pk]),
                reverse('members:document', args=[self.member.pk, self.document.pk]),
                reverse('membership:document', args=[self.document.pk])]

    def test_all_four_native_access_audits_invalidate(self):
        for index, route in enumerate(self.routes(), 2):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.streaming)
                self.assertIn('no-store', response['Cache-Control'])
                response.close()
                self.assert_transition(index)

    def test_failed_invalidation_rolls_back_native_access_audit(self):
        before = ProgramLog.objects.count()
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional access audit failure')):
            with self.assertRaises(ValidationError):
                self.client.get(self.routes()[0])
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assert_transition(1)
        self.assertTrue(self.application.current_photo.file.storage.exists(self.application.current_photo.file.name))

    def test_duplicate_native_access_audit_rejected(self):
        from programs import photo_views
        original = photo_views.record_log
        def duplicate(*args, **kwargs):
            original(*args, **kwargs)
            return original(*args, **kwargs)
        before = ProgramLog.objects.count()
        with patch.object(photo_views, 'record_log', side_effect=duplicate), self.assertRaises(ValidationError):
            self.client.get(self.routes()[0])
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assert_transition(1)

    def test_unauthorized_and_missing_files_do_not_invalidate(self):
        self.assertEqual(Client().get(self.routes()[0]).status_code, 302)
        self.application.current_photo.file.storage.delete(self.application.current_photo.file.name)
        self.assertEqual(self.client.get(self.routes()[0]).status_code, 404)
        self.assert_transition(1)

    def test_access_after_promotion_clears_pointer_and_keeps_history(self):
        context = processing.inspect_context(self.program.pk, user=self.officer, contract=self.contract)
        request = processing.accept_request(self.program.pk, user=self.officer, contract=self.contract,
            expected=context['expected'], expected_context=context['context_digest'], request_key='fictional-access-race',
            reason='Fictional access audit dependency')
        run = processing.process_request(request.pk, program_id=self.program.pk, user=self.officer)
        response = self.client.get(self.routes()[0])
        response.close()
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        from .durable_services import _assert_history
        _assert_history(run)

    def test_separate_connection_access_waits_for_promotion_commit(self):
        context = processing.inspect_context(self.program.pk, user=self.officer, contract=self.contract)
        request = processing.accept_request(self.program.pk, user=self.officer, contract=self.contract,
            expected=context['expected'], expected_context=context['context_digest'], request_key='fictional-access-lock',
            reason='Fictional private access concurrency')
        entered, release = Event(), Event()
        original = processing._promote
        def pause(*args):
            result = original(*args)
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional race timeout')
            return result
        route = self.routes()[0]
        def access():
            response = self.client.get(route)
            response.close()
            return response.status_code
        with patch.object(processing, '_promote', side_effect=pause), ThreadPoolExecutor(2) as pool:
            first = pool.submit(worker, lambda: processing.process_request(request.pk, program_id=self.program.pk, user=self.officer))
            self.assertTrue(entered.wait(15))
            second = pool.submit(worker, access)
            try:
                with self.assertRaises(TimeoutError):
                    second.result(timeout=.25)
            finally:
                release.set()
            first_id, _ = first.result(timeout=25)
            second_id, status = second.result(timeout=25)
            self.assertNotEqual(first_id, second_id)
            self.assertEqual(status, 200)
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
