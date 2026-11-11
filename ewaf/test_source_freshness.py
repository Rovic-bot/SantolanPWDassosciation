"""Gate 1 fictional fixtures; actual MySQL transactions, no application DB."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase
from django.utils import timezone
from documents.models import MembershipDocumentRequirement, DocumentType
from members.services import change_status
from programs.models import ProgramLog
from . import durable_services as services
from .durable_models import DurableRun, DurableResult, DurableTrace, DurableOutcome
from .durable_testsupport import DurableHelpers
from .evidence import digest
from .source_freshness import ENGINE, VERSION
from .test_durable_concurrency import worker


class SourceFreshnessTests(DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()

    def history(self, run):
        return services.inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)

    def current(self, run):
        return services.inspect_development_result(run.pk, program_id=self.program.pk, user=self.officer)

    def change_requirement(self):
        MembershipDocumentRequirement.objects.filter(pk=self.document.requirement_id).update(
            instructions='Fictional changed instructions')

    def assert_failed_graph(self):
        self.assertFalse(DurableRun.objects.exists())
        self.assertFalse(DurableResult.objects.exists())
        self.assertFalse(DurableTrace.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='durable_durablerun').exists())
        self.assertEqual(DurableOutcome.objects.get().status, 'FAILED')

    def test_versioned_observations_leave_legacy_source_digest_unchanged(self):
        source = self.context()
        run = self.process(self.request_run())
        self.assertEqual(run.snapshot['engine'], ENGINE)
        self.assertEqual(run.snapshot['freshness']['version'], VERSION)
        self.assertEqual(run.snapshot['eligible'][str(self.application.pk)]['source'], source)
        self.assertEqual(run.snapshot['manifest'][0]['source_digest'], digest(source))
        self.assertFalse(self.current(run)['atomic_freshness'])
        self.assertFalse(self.current(run)['current_promotion'])

    def test_changed_requirement_metadata_invalidates_pending_request(self):
        request = self.request_run()
        self.change_requirement()
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assert_failed_graph()

    def test_added_requirement_without_document_invalidates_inventory(self):
        request = self.request_run()
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(name='Fictional added requirement'))
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assert_failed_graph()

    def test_document_type_metadata_change_detected(self):
        request = self.request_run()
        kind = self.document.requirement.document_type
        kind.description = 'Fictional changed evidence meaning'
        kind.save()
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)

    def test_linked_event_publication_observation_changes_without_program_version(self):
        from events.tests import create_event
        from events.services import change_publication
        from .source_freshness import observe
        event = create_event(application_program=self.program)
        before = observe(self.program, [self.application], self.officer)
        change_publication(event.pk, user=self.officer, version=event.version,
            action='cancelled', notes='Fictional event cancellation')
        after = observe(self.program, [self.application], self.officer)
        self.assertNotEqual(before['linked_event_digest'], after['linked_event_digest'])

    def test_intake_snapshot_version_change_invalidates_context(self):
        request = self.request_run()
        # Unsupported correction is a boundary probe, not a new intake workflow.
        intake = self.member.application
        intake.version += 1
        intake.save(update_fields=['version'])
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)

    def test_cross_program_release_then_void_does_not_restore_context(self):
        from assistance.services import record_release, void_release
        from assistance.tests import release_data
        from .test_evidence_concurrency import EvidenceConcurrencyTests
        other = EvidenceConcurrencyTests.other_selected_application(self)
        before = self.context()['pa']['count']
        request = self.request_run()
        receipt = record_release(other.pk, user=self.officer, data=release_data(other))
        other.refresh_from_db()
        void_release(other.pk, receipt.pk, user=self.officer,
            data={'version': other.version, 'notes': 'Fictional receipt void', 'confirm': True})
        self.assertEqual(self.context()['pa']['count'], before)
        with self.assertRaises(ValidationError):
            self.process(request)
        self.assert_failed_graph()

    def test_duplicate_request_revalidates_instead_of_returning_stale_identity(self):
        request = self.request_run()
        self.change_requirement()
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.request_run(expected_context=request.expected_context)
        self.assertEqual(request.attempts.count(), 0)

    def test_only_one_replacement_request_for_a_predecessor(self):
        run = self.process(self.request_run())
        self.request_run(request_key='replacement-a', previous_id=run.pk)
        with self.assertRaisesMessage(ValidationError, 'PREDECESSOR_ALREADY_REPLACEMENT_REQUESTED'):
            self.request_run(request_key='replacement-b', previous_id=run.pk)

    def test_stale_history_remains_replayable_without_current_claim(self):
        run = self.process(self.request_run())
        original = (run.digest, run.context_digest, deepcopy(run.snapshot), run.results.get().calculation)
        self.change_requirement()
        with self.assertRaisesMessage(ValidationError, 'RESULT_STALE'):
            self.current(run)
        self.assertIsNone(self.history(run)['sources_match_now'])
        self.assertFalse(self.history(run)['operational_ready'])
        run.refresh_from_db()
        self.assertEqual(original, (run.digest, run.context_digest, run.snapshot, run.results.get().calculation))

    def test_legacy_run_replays_without_rewriting_or_claiming_new_freshness(self):
        with patch('ewaf.durable_services._capture', services._capture_legacy):
            run = self.process(self.request_run())
        original = deepcopy(run.snapshot)
        self.assertNotIn('freshness', original)
        self.assertTrue(self.history(run)['historically_complete'])
        with self.assertRaisesMessage(ValidationError, 'FRESHNESS_REVALIDATION_REQUIRED'):
            self.current(run)
        run.refresh_from_db()
        self.assertEqual(run.snapshot, original)

    def test_legacy_pending_request_requires_new_context(self):
        with patch('ewaf.durable_services._capture', services._capture_legacy):
            request = self.request_run()
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assert_failed_graph()

    def test_changed_then_restored_member_status_is_not_fresh(self):
        request = self.request_run()
        change_status(self.member.pk, user=self.officer, version=self.member.version,
            status='inactive', notes='Fictional temporary change')
        self.member.refresh_from_db()
        change_status(self.member.pk, user=self.officer, version=self.member.version,
            status='active', notes='Fictional restoration')
        with self.assertRaises(ValidationError):
            self.process(request)
        self.assert_failed_graph()

    def test_changed_then_restored_review_requires_new_assessments(self):
        request = self.request_run()
        self.verify(verified=False)
        self.verify(verified=True)
        with self.assertRaises(ValidationError):
            self.process(request)
        self.assert_failed_graph()

    def test_unversioned_metadata_aba_is_explicitly_not_guaranteed(self):
        before = self.inspect_pool()['context_digest']
        old = self.document.requirement.instructions
        self.change_requirement()
        MembershipDocumentRequirement.objects.filter(pk=self.document.requirement_id).update(instructions=old)
        self.assertEqual(self.inspect_pool()['context_digest'], before)
        run = self.process(self.request_run())
        self.assertFalse(self.current(run)['atomic_freshness'])
        self.assertFalse(self.current(run)['operational_ready'])

    def test_direct_permission_topology_change_detected_even_for_superuser(self):
        request = self.request_run()
        self.officer.user_permissions.add(Permission.objects.get(codename='process_durablerequest'))
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assert_failed_graph()

    def test_group_permission_topology_change_detected(self):
        group = Group.objects.create(name='Fictional source observers')
        self.officer.groups.add(group)
        request = self.request_run()
        group.permissions.add(Permission.objects.get(codename='process_durablerequest'))
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)

    def test_admin_audit_detects_restored_actor_permission_state(self):
        request = self.request_run()
        # Mirrors the admin's retained audit after a change and restoration.
        LogEntry.objects.create(user=self.officer, content_type=ContentType.objects.get_for_model(self.officer),
            object_id=str(self.officer.pk), object_repr='Fictional actor', action_flag=CHANGE,
            change_message='Fictional permission change and restoration')
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)

    def test_permission_revocation_ignores_cached_actor_permissions(self):
        request = self.request_run()
        self.officer.get_all_permissions()
        get_user_model().objects.filter(pk=self.officer.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_expiry_after_request_blocks_and_preserves_history(self):
        self.document_review = self.verify(expires_on=timezone.localdate())
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            self.assess(code)
        run = self.process(self.request_run())
        with patch('django.utils.timezone.localdate', return_value=timezone.localdate() + timedelta(days=1)):
            with self.assertRaises(ValidationError):
                self.current(run)
            self.assertTrue(self.history(run)['historically_complete'])

    def test_missing_private_bytes_fail_closed(self):
        request = self.request_run()
        self.document.file.storage.delete(self.document.file.name)
        with self.assertRaises(ValidationError):
            self.process(request)
        self.assert_failed_graph()

    def test_inconsistent_snapshot_versions_and_trace_inputs_rejected(self):
        run = self.process(self.request_run())
        for mutate, error in (
            (lambda s: s.update(engine='unknown'), 'UNSUPPORTED_RUN_VERSION'),
            (lambda s: s['freshness'].update(version='unknown'), 'UNSUPPORTED_FRESHNESS_VERSION'),
            (lambda s: s['freshness'].update(inventory=[]), 'COMPLETE_POOL_MANIFEST_REQUIRED'),
            (lambda s: s['eligible'].clear(), 'COMPLETE_POOL_RESULTS_REQUIRED'),
            (lambda s: s['eligible'][str(self.application.pk)]['inputs'].pop('PR'), 'COMPLETE_CRITERION_TRACES_REQUIRED'),
        ):
            with self.subTest(error=error):
                snapshot = deepcopy(run.snapshot)
                mutate(snapshot)
                with self.assertRaisesMessage(ValidationError, error):
                    services.validate_snapshot(snapshot)

    def test_partial_calculation_map_rolls_back_entire_graph(self):
        self.add_ready_applicant()
        request = self.request_run()
        calculate = services._calculate
        def partial(snapshot):
            result = calculate(snapshot)
            result.pop(next(iter(result)))
            return result
        with patch('ewaf.durable_services._calculate', side_effect=partial), self.assertRaises(ValidationError):
            self.process(request)
        self.assert_failed_graph()

    def test_unlocked_source_writer_during_calculation_detected_on_separate_connection(self):
        request = self.request_run()
        calculate = services._calculate
        def interleave(snapshot):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(worker, self.change_requirement).result(timeout=15)
            return calculate(snapshot)
        with patch('ewaf.durable_services._calculate', side_effect=interleave), self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assert_failed_graph()
        self.assertEqual(MembershipDocumentRequirement.objects.get(pk=self.document.requirement_id).instructions,
                         'Fictional changed instructions')

    def test_unlocked_source_writer_during_persistence_rolls_back_complete_graph(self):
        request = self.request_run()
        persist = services._persist
        def interleave(row):
            result = persist(row)
            if isinstance(row, DurableTrace) and row.criterion == 'PR':
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(worker, self.change_requirement).result(timeout=15)
            return result
        with patch('ewaf.durable_services._persist', side_effect=interleave), self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assert_failed_graph()

    def test_permission_revoked_during_persistence_cannot_complete(self):
        self.officer.is_superuser = False
        self.officer.save(update_fields=['is_superuser'])
        self.officer.user_permissions.add(*Permission.objects.all())
        revoked = Permission.objects.get(codename='process_durablerequest')
        request = self.request_run()
        persist = services._persist
        def interleave(row):
            result = persist(row)
            if isinstance(row, DurableTrace) and row.criterion == 'PR':
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(worker, lambda: get_user_model().objects.get(pk=self.officer.pk)
                                .user_permissions.remove(revoked)).result(timeout=15)
            return result
        with patch('ewaf.durable_services._persist', side_effect=interleave), self.assertRaises((PermissionDenied, ValidationError)):
            self.process(request)
        self.assert_failed_graph()
