"""Real disposable MySQL, fictional fixtures, no operational activation."""
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import connection, transaction, IntegrityError
from django.db.models.deletion import ProtectedError
from django.test import TransactionTestCase
from django.utils import timezone
from members.tests import create_member
from programs.models import ProgramLog
from programs.tests import create_program
from programs.testsupport import application_fixture
from .durable_testsupport import DurableHelpers, fictional_definitions
from .durable_models import DurableRequest, DurableAttempt, DurableRun, DurableResult, DurableTrace, DurableOutcome
from .durable_services import (inspect_development_result, require_operational_result, validate_graph,
    close_interrupted_attempt, _calculate)
from .normalization import CRITERIA


class DurableServiceTests(DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()

    def inspect_run(self, run):
        return inspect_development_result(run.pk, program_id=self.program.pk, user=self.officer)

    def test_default_disabled_without_harness_capability(self):
        with patch('scripts.durable_test_runner._identity', None), self.assertRaises(PermissionDenied):
            self.inspect_pool()
        with self.assertRaises(ValidationError):
            require_operational_result(approved=True, synthetic=True, user=self.officer)

    def test_anonymous_inactive_nonstaff_and_unpermissioned(self):
        for user in (AnonymousUser(), get_user_model().objects.create_user('restricted', is_staff=True)):
            with self.assertRaises(PermissionDenied):
                self.inspect_pool(user=user)
        for field in ('is_active', 'is_staff'):
            setattr(self.officer, field, False)
            with self.assertRaises(PermissionDenied):
                self.inspect_pool()
            setattr(self.officer, field, True)

    def test_database_identity_not_boolean_or_stored_label(self):
        from scripts.durable_test_runner import _identity
        with patch('scripts.durable_test_runner._identity', ('wrong', *_identity[1:])), self.assertRaises(PermissionDenied):
            self.inspect_pool()
        with self.assertRaises(TypeError):
            self.inspect_pool(synthetic=True)

    def test_cross_program_and_other_actor_refused(self):
        request = self.request_run()
        with self.assertRaises(ObjectDoesNotExist):
            self.process(request, program_id=create_program().pk)
        other = get_user_model().objects.create_superuser('other_synthetic_officer')
        with self.assertRaises(PermissionDenied):
            self.process(request, user=other)

    def test_no_subset_pagination_or_slot_limit(self):
        for argument in ({'application_ids': [self.application.pk]}, {'limit': 1}, {'page': 1}):
            with self.assertRaises(TypeError):
                self.inspect_pool(**argument)

    def test_policy_gaps_do_not_default(self):
        self.propose()
        with self.assertRaisesMessage(ValidationError, 'SCORING_POLICY_INCOMPLETE'):
            self.inspect_pool()

    def test_cutoff_and_scope_required(self):
        for contract in ({}, {**self.contract, 'cutoff': ''}, {**self.contract, 'scope': 'first_page'}):
            with self.assertRaises(ValidationError):
                self.inspect_pool(contract=contract)

    def test_unapproved_sources_remain_unapproved_in_history(self):
        run = self.process(self.request_run())
        reasons = run.snapshot['manifest'][0]['readiness_reasons']
        self.assertIn('CRITERION_POLICY_UNAPPROVED', [r['code'] for r in reasons['governance']])
        self.assertFalse(self.inspect_run(run)['operational_ready'])
        self.assertFalse(self.inspect_run(run)['current_promotion'])

    def test_missing_disputed_unverified_and_expired_evidence_blocks_pool(self):
        for changes in ({'state': 'NEEDS_REVIEW'}, {'state': 'DECLARED', 'disputed': True}, {'state': 'DECLARED'}):
            with self.subTest(changes=changes):
                self.assess('ND', **changes)
                with self.assertRaisesMessage(ValidationError, 'ELIGIBLE_POOL_EVIDENCE_INCOMPLETE'):
                    self.inspect_pool()
                self.assess('ND')

    def test_expired_required_document_blocks(self):
        self.document_review = self.verify(expires_on=timezone.localdate())
        for code in CRITERIA:
            self.assess(code)
        with patch('django.utils.timezone.localdate', return_value=timezone.localdate() + timedelta(days=1)):
            with self.assertRaisesMessage(ValidationError, 'ELIGIBLE_POOL_EVIDENCE_INCOMPLETE'):
                self.inspect_pool()

    def test_eligible_without_evidence_never_disappears(self):
        added = application_fixture(self.program, create_member('SYN-DURABLE-MISSING'))
        added.status = 'ELIGIBLE'
        added.submitted_at = self.application.submitted_at
        added.save(update_fields=['status', 'submitted_at'])
        with self.assertRaisesMessage(ValidationError, 'ELIGIBLE_POOL_EVIDENCE_INCOMPLETE'):
            self.inspect_pool()

    def test_out_of_scope_and_ineligible_accounted_separately(self):
        added = application_fixture(self.program, create_member('SYN-DURABLE-LATE'))
        run = self.process(self.request_run())
        self.assertEqual(len(run.snapshot['manifest']), 2)
        self.assertEqual(run.results.count(), 1)
        self.assertFalse(next(r for r in run.snapshot['manifest'] if r['application'] == str(added.pk))['in_scope'])

    def test_unresolved_in_scope_eligibility_blocks(self):
        added = application_fixture(self.program, create_member('SYN-DURABLE-PENDING'))
        added.submitted_at = self.application.submitted_at
        added.save(update_fields=['submitted_at'])
        with self.assertRaisesMessage(ValidationError, 'ELIGIBILITY_UNRESOLVED'):
            self.inspect_pool()

    def test_engine_limit_explicit_no_truncation(self):
        with patch('ewaf.durable_services.MAX_APPLICATIONS', 0), self.assertRaisesMessage(ValidationError, 'WHOLE_POOL_UNSUPPORTED'):
            self.inspect_pool()

    def test_zero_exact_replay_and_reopen_connection(self):
        run = self.process(self.request_run())
        original = run.results.get().calculation
        self.assertEqual(original['score_0_1'], '0.4')
        self.assertEqual(original['score_0_100'], '40')
        self.assertEqual(run.results.get().traces.get(criterion='ND').snapshot['input']['value'], 0)
        connection.close()
        retained = DurableRun.objects.get(pk=run.pk)
        validate_graph(retained)
        self.assertEqual(retained.results.get().calculation, original)
        self.assertEqual(_calculate(retained.snapshot)[str(self.application.pk)], original)

    def test_complete_two_person_pool_preserves_exact_ties(self):
        helper = self.add_ready_applicant()
        run = self.process(self.request_run())
        self.assertEqual(run.results.count(), 2)
        self.assertEqual(set(run.results.values_list('application_id', flat=True)),
                         {self.application.pk, helper.application.pk})
        for result in run.results.all():
            self.assertEqual(result.comparison, {'higher': 0, 'equal': 2, 'business_rank': None})
            self.assertEqual(result.calculation['score_0_1'], '0.4')
            self.assertEqual(result.traces.count(), 5)
        validate_graph(run)

    def test_fifty_digit_fraction_survives_persistence_and_replay(self):
        self.member.dependents = 1
        self.member.save(update_fields=['dependents'])
        for code in CRITERIA:
            self.assess(code)
        definitions = fictional_definitions()
        definitions['criteria']['ND']['bounds']['upper'] = '3'
        self.propose(proposed=definitions)
        run = self.process(self.request_run())
        normalized = run.results.get().traces.get(criterion='ND').snapshot['calculation']['normalized']
        self.assertEqual(normalized, '0.' + '3' * 50)
        connection.close()
        validate_graph(DurableRun.objects.get(pk=run.pk))

    def test_configuration_revision_invalidates_pending_request(self):
        request = self.request_run()
        self.validate()
        with self.assertRaises(ValidationError):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_pool_entry_after_request_refuses_incomplete_success(self):
        request = self.request_run()
        application_fixture(self.program, create_member('SYN-DURABLE-NEW-POOL'))
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_db_uniqueness_for_results_and_traces(self):
        run = self.process(self.request_run())
        # Exercise actual database constraints through SQL, intentionally outside
        # supported immutable paths. This is not a privileged-SQL protection claim.
        for row in (run.results.get(), run.results.get().traces.first()):
            fields = [field for field in row._meta.concrete_fields if not field.primary_key]
            columns = ','.join(connection.ops.quote_name(f.column) for f in fields)
            select = ','.join('%s' if f.name == 'audit_entry' else connection.ops.quote_name(f.column) for f in fields)
            with self.assertRaises(IntegrityError) as caught, transaction.atomic(), connection.cursor() as cursor:
                audit = ProgramLog.objects.create(program=self.program, action='fictional_constraint_probe', notes='Test only')
                cursor.execute(f'INSERT INTO {row._meta.db_table} ({columns}) SELECT {select} FROM {row._meta.db_table} WHERE id=%s', [audit.pk, row.pk])
            constraint = 'ewaf_durable_run_application' if isinstance(row, DurableResult) else 'ewaf_durable_result_criterion'
            self.assertIn(constraint, str(caught.exception))

    def test_unverified_ineligible_status_cannot_hide_an_applicant(self):
        added = application_fixture(self.program, create_member('SYN-DURABLE-INELIGIBLE'))
        added.status, added.submitted_at = 'INELIGIBLE', self.application.submitted_at
        added.save(update_fields=['status', 'submitted_at'])
        with self.assertRaisesMessage(ValidationError, 'INELIGIBLE_OUTCOME_STALE_OR_UNVERIFIED'):
            self.inspect_pool()

    def test_required_result_omission_rolls_back(self):
        from .durable_services import _persist
        request = self.request_run()
        def omit_result(row):
            if isinstance(row, DurableResult):
                raise ValidationError('RESULT_REQUIRED')
            return _persist(row)
        with patch('ewaf.durable_services._persist', side_effect=omit_result), self.assertRaises(ValidationError):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_failed_replacement_never_restores_old_result(self):
        first = self.process(self.request_run())
        request = self.request_run(request_key='replacement', previous_id=first.pk)
        with patch('ewaf.durable_services._calculate', side_effect=RuntimeError('fictional failure')), self.assertRaises(RuntimeError):
            self.process(request)
        with self.assertRaisesMessage(ValidationError, 'RESULT_REPLACEMENT_REQUESTED'):
            self.inspect_run(first)

    def test_failure_audit_failure_leaves_explicit_unfinished_attempt(self):
        request = self.request_run()
        actual = ProgramLog.objects.create
        def failure(**kwargs):
            if kwargs.get('action') in ('durable_durabletrace', 'durable_durableoutcome'):
                raise RuntimeError('fictional audit outage')
            return actual(**kwargs)
        with patch('ewaf.durable_services.ProgramLog.objects.create', side_effect=failure), self.assertRaises(RuntimeError):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())
        self.assertEqual(DurableAttempt.objects.filter(outcome__isnull=True).count(), 1)
        with self.assertRaisesMessage(ValidationError, 'ATTEMPT_IN_PROGRESS_OR_INTERRUPTED'):
            self.process(request)

    def test_immutable_update_delete_bulk_and_audit_protection(self):
        run = self.process(self.request_run())
        for row in (run, run.request, run.attempt, run.completion, run.results.get(), run.results.get().traces.first()):
            for action in (lambda: row.save(), lambda: row.delete(),
                           lambda: type(row).objects.filter(pk=row.pk).update(reason='edited'),
                           lambda: type(row).objects.filter(pk=row.pk).delete(),
                           lambda: type(row).objects.bulk_update([row], ['reason']),
                           lambda: type(row).objects.bulk_create([row])):
                with self.assertRaises(ValidationError):
                    action()
            with self.assertRaises(ProtectedError):
                row.audit_entry.delete()

    def test_duplicate_request_and_conflicting_key(self):
        request = self.request_run()
        self.assertEqual(self.request_run().pk, request.pk)
        with self.assertRaisesMessage(ValidationError, 'REQUEST_CONTENT_CONFLICT'):
            self.request_run(reason='Different content')
        first = self.process(request)
        self.assertEqual(self.process(request).pk, first.pk)
        self.assertEqual(DurableRun.objects.count(), 1)
        self.assertEqual(DurableAttempt.objects.count(), 1)

    def test_deliberate_new_request_is_not_retry(self):
        first = self.process(self.request_run())
        second = self.process(self.request_run(request_key='deliberate-next', previous_id=first.pk))
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(second.previous_id, first.pk)
        self.assertEqual(first.results.get().calculation, second.results.get().calculation)
        with self.assertRaisesMessage(ValidationError, 'RESULT_REPLACEMENT_REQUESTED'):
            self.inspect_run(first)

    def test_new_assessment_correction_preserves_predecessor(self):
        first = self.process(self.request_run())
        before = first.snapshot
        self.assess('ND')
        with self.assertRaisesMessage(ValidationError, 'RESULT_STALE'):
            self.inspect_run(first)
        second = self.process(self.request_run(request_key='correction', previous_id=first.pk))
        first.refresh_from_db()
        self.assertEqual(first.snapshot, before)
        self.assertEqual(second.previous_id, first.pk)
        self.assertNotEqual(first.context_digest, second.context_digest)

    def test_cross_program_predecessor_refused(self):
        first = self.process(self.request_run())
        first.program_id = create_program().pk
        with self.assertRaises(ValidationError):
            first.clean()

    def test_self_predecessor_refused(self):
        run = self.process(self.request_run())
        run.previous = run
        with self.assertRaises(ValidationError):
            run.clean()

    def test_missing_trace_cannot_be_marked_complete(self):
        from .durable_services import _persist
        request = self.request_run()
        def omit_trace(row):
            if isinstance(row, DurableTrace) and row.criterion == 'ND':
                return row
            return _persist(row)
        with patch('ewaf.durable_services._persist', side_effect=omit_trace), self.assertRaisesMessage(
                ValidationError, 'COMPLETE_CRITERION_TRACES_REQUIRED'):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_audit_failure_rolls_back_entire_graph_but_retains_failed_attempt(self):
        request = self.request_run()
        actual = ProgramLog.objects.create
        def fail_success(**kwargs):
            if kwargs.get('action') == 'durable_durabletrace':
                raise RuntimeError('fictional injected audit failure')
            return actual(**kwargs)
        with patch('ewaf.durable_services.ProgramLog.objects.create', side_effect=fail_success), self.assertRaises(RuntimeError):
            self.process(request)
        self.assertEqual(DurableRun.objects.count(), 0)
        self.assertEqual(DurableResult.objects.count(), 0)
        self.assertEqual(DurableTrace.objects.count(), 0)
        self.assertEqual(DurableOutcome.objects.get().status, 'FAILED')
        self.assertFalse(ProgramLog.objects.filter(action='durable_durablerun').exists())
        self.process(request)
        self.assertEqual(list(DurableOutcome.objects.order_by('pk').values_list('status', flat=True)), ['FAILED', 'COMPLETED'])

    def test_interruption_requires_explicit_recovery_then_retry(self):
        request = self.request_run()
        with patch('ewaf.durable_services._calculate', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())
        self.assertFalse(DurableOutcome.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'ATTEMPT_IN_PROGRESS_OR_INTERRUPTED'):
            self.process(request)
        close_interrupted_attempt(request.pk, program_id=self.program.pk, user=self.officer, reason='Fictional crash recovery')
        self.process(request)
        self.assertEqual(DurableAttempt.objects.count(), 2)
        self.assertEqual(DurableRun.objects.count(), 1)

    def test_changed_context_after_request_cannot_commit(self):
        request = self.request_run()
        self.assess('ND')
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process(request)
        self.assertFalse(DurableRun.objects.exists())
        self.assertEqual(DurableOutcome.objects.get().status, 'FAILED')

    def test_changes_during_processing_rollback(self):
        request = self.request_run()
        actual = _calculate
        def mutate(snapshot):
            from programs.models import ProgramApplication
            ProgramApplication.objects.filter(pk=self.application.pk).update(version=999)
            return actual(snapshot)
        with patch('ewaf.durable_services._calculate', side_effect=mutate), self.assertRaises(ValidationError):
            self.process(request)
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.version, 999)
        self.assertFalse(DurableRun.objects.exists())

    def test_outer_transaction_refused(self):
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'top-level'):
            self.inspect_pool()

    def test_general_audits_contain_no_raw_values_or_reason(self):
        run = self.process(self.request_run())
        for log in ProgramLog.objects.filter(action__startswith='durable_'):
            self.assertEqual(set(log.changes), {'digest'})
            self.assertNotIn(self.member.full_name, log.notes)
            self.assertNotIn(run.reason, log.notes)
