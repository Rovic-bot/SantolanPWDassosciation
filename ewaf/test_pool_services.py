"""Fictional MySQL records only; no numerical applicant processing or new schema."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from members.tests import create_member
from programs.models import ProgramApplication, ProgramLog
from programs.tests import create_program
from programs.testsupport import application_fixture
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .scoring_inputs import READINESS_VIEW
from .pool_contracts import BARRIERS, scoring_findings, require_context_digest
from .pool_services import (inspect_program_pool, recheck_program_pool,
                            request_recalculation, process_recalculation, current_pool_result)


class PoolContractTests(SimpleTestCase):
    def test_missing_policy_stays_missing(self):
        self.assertEqual(scoring_findings(None), [{'code': 'SCORING_POLICY_MISSING', 'source': None}])

    def test_unknown_policy_approval_boolean_rejected(self):
        self.assertEqual(scoring_findings({'approved': True})[0]['code'], 'SCORING_POLICY_INVALID')

    def test_empty_criteria_keep_individual_policy_gaps(self):
        result = scoring_findings({'criteria': {key: {} for key in ('SI', 'ES', 'PA', 'ND', 'PR')}})
        self.assertEqual({row['source'] for row in result}, {'SI', 'ES', 'PA', 'ND', 'PR'})
        self.assertTrue({'SCORING_POLICY_INCOMPLETE', 'NORMALIZATION_DIRECTION_PENDING', 'BOUNDS_PENDING'}
                        <= {row['code'] for row in result})

    def test_digest_cannot_be_missing_or_arbitrary_object(self):
        for value in (None, {}, True, 'abc', 'G' * 64):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                require_context_digest(value)
        require_context_digest('a' * 64)


class PoolServiceTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_scoring()

    def inspect(self, **kwargs):
        return inspect_program_pool(self.program.pk, **{'user': self.officer, **kwargs})

    def add_application(self, status='ELIGIBLE', program=None):
        member = create_member('SYN-POOL-' + str(ProgramApplication.objects.count()))
        application = application_fixture(program or self.program, member)
        application.status = status
        application.save(update_fields=['status'])
        return application

    def assert_blocked(self, result):
        for key in ('operational_ready', 'calculation_complete', 'effective_authorization', 'persisted'):
            self.assertIs(result[key], False)
        self.assertTrue(set(BARRIERS) <= set(result['reasons']))

    def test_anonymous_denied_before_reads(self):
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            self.inspect(user=AnonymousUser())

    def test_staff_without_private_permissions_denied(self):
        officer = get_user_model().objects.create_user('pool_restricted', is_staff=True)
        with self.assertRaises(PermissionDenied):
            self.inspect(user=officer)

    def test_scoped_read_permissions_suffice_only_for_readiness(self):
        officer = get_user_model().objects.create_user('pool_reader', is_staff=True)
        officer.user_permissions.set(Permission.objects.filter(codename__in=[
            key.split('.')[1] for key in (*READINESS_VIEW, 'accounts.access_dashboard')]))
        self.assert_blocked(self.inspect(user=officer))
        # Cached permissions must not survive a database-side revocation.
        officer.user_permissions.remove(Permission.objects.get(content_type__app_label='ewaf',
                                                               codename='view_criterionassessment'))
        with self.assertRaises(PermissionDenied):
            self.inspect(user=officer)

    def test_inactive_or_nonstaff_even_superuser_denied(self):
        for field in ('is_active', 'is_staff'):
            setattr(self.officer, field, False)
            with self.assertRaises(PermissionDenied):
                self.inspect()
            setattr(self.officer, field, True)

    def test_complete_inventory_keeps_all_statuses_and_missing_candidates(self):
        missing = self.add_application()
        pending = self.add_application('NEEDS_INFORMATION')
        ineligible = self.add_application('INELIGIBLE')
        result = self.inspect()
        self.assertTrue(result['inventory_complete'])
        self.assertEqual(result['retained_application_count'], 4)
        self.assertEqual(set(result['eligible_status_ids']), {str(self.application.pk), str(missing.pk)})
        self.assertEqual({row['application_id'] for row in result['manifest']},
                         {str(row.pk) for row in (self.application, missing, pending, ineligible)})
        self.assertIn('ELIGIBLE_POOL_EVIDENCE_INCOMPLETE', result['reasons'])
        self.assertIn('NONCANDIDATE_ADMISSION_POLICY_PENDING', result['reasons'])
        self.assert_blocked(result)

    def test_no_caller_subset_cutoff_or_synthetic_switch(self):
        for extra in ({'application_ids': [str(self.application.pk)]}, {'limit': 1},
                      {'cutoff': timezone.now()}, {'synthetic': True}):
            with self.subTest(extra=extra), self.assertRaises(TypeError):
                self.inspect(**extra)

    def test_resource_limit_blocks_whole_inventory_not_a_page(self):
        self.add_application()
        with patch('ewaf.pool_services.MAX_APPLICATIONS', 1):
            result = self.inspect()
        self.assertEqual(result['retained_application_count'], 2)
        self.assertFalse(result['inventory_complete'])
        self.assertEqual(result['manifest'], [])
        self.assertEqual(result['items'], [])
        self.assertIsNone(result['context_digest'])
        self.assertIn('POOL_RESOURCE_LIMIT', result['reasons'])

    def test_other_program_records_never_in_manifest(self):
        other = create_program()
        foreign = self.add_application(program=other)
        result = self.inspect()
        self.assertNotIn(str(foreign.pk), {row['application_id'] for row in result['manifest']})
        with self.assertRaises(ValidationError):
            recheck_program_pool(other.pk, user=self.officer, expected_context_digest=result['context_digest'])

    def test_slot_count_does_not_limit_inventory(self):
        self.add_application()
        result = self.inspect()
        self.assertEqual(len(result['manifest']), 2)
        self.assertEqual(len(result['eligible_status_ids']), 2)

    def test_no_cutoff_derived_from_program_schedule(self):
        result = self.inspect()
        self.assertIsNone(result['evaluation_scope'])
        self.assertIsNone(result['evaluation_cutoff'])
        self.assertEqual(result['inspection_scope'], 'ALL_RETAINED_APPLICATIONS')

    def test_verified_zero_distinct_from_missing(self):
        before = self.inspect()['items'][0]['readiness']['criteria'][3]
        self.assertEqual(before['state'], 'MISSING')
        row = self.assess('ND')
        self.assertEqual(row.value, 0)
        after = self.inspect()['items'][0]['readiness']['criteria'][3]
        self.assertTrue(after['current'])
        self.assertEqual(after['assessment'], row.pk)
        self.assertNotIn('value', after)

    def test_rejected_disputed_latest_evidence_never_disappears(self):
        self.assess('ND')
        rejected = self.assess('ND', state='REJECTED', disputed=True)
        result = self.inspect()
        self.assertEqual(result['eligible_status_ids'], [str(self.application.pk)])
        readiness = result['items'][0]['readiness']
        self.assertEqual(readiness['criteria'][3]['assessment'], rejected.pk)
        self.assertTrue({'CRITERION_REJECTED', 'EVIDENCE_DISPUTED'} <= {r['code'] for r in readiness['reasons']})
        self.assertIn('ELIGIBLE_POOL_EVIDENCE_INCOMPLETE', result['reasons'])

    def test_expired_evidence_blocks_candidate(self):
        today = timezone.localdate()
        self.document_review = self.verify(expires_on=today)
        self.assess('ND')
        with patch('django.utils.timezone.localdate', return_value=today + timedelta(days=1)):
            result = self.inspect()
        self.assertIn('EVIDENCE_EXPIRED', {r['code'] for r in result['items'][0]['readiness']['reasons']})
        self.assertIn(str(self.application.pk), result['eligible_status_ids'])

    def test_membership_provenance_failure_is_not_ready(self):
        self.member.application.events.filter(action='prpwd_verified').delete()
        result = self.inspect()
        self.assertEqual(result['eligible_status_ids'], [str(self.application.pk)])
        self.assertEqual(result['eligibility_ready_ids'], [])

    def test_all_reviewed_still_no_numerical_processing(self):
        self.prepare_relevance()
        self.draft()
        self.validate()
        self.propose()
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            self.assess(code)
        result = self.inspect()
        self.assertEqual(result['eligibility_ready_ids'], result['eligible_status_ids'])
        self.assertEqual(result['evidence_ready_ids'], result['eligible_status_ids'])
        self.assertEqual(result['weight_evidence_ready_ids'], result['eligible_status_ids'])
        self.assert_blocked(result)

    def test_recheck_reuses_current_sources_not_old_diagnostic(self):
        captured = self.capture_diagnostic()
        before = self.inspect()
        self.assess('ND')
        with self.assertRaises(ValidationError) as raised:
            recheck_program_pool(self.program.pk, user=self.officer, expected_context_digest=before['context_digest'])
        self.assertEqual(raised.exception.code, 'POOL_CONTEXT_CHANGED')
        captured.refresh_from_db()
        self.assertEqual(captured.result['mode'], 'READINESS_ONLY')

    def test_same_sources_repeat_same_digest_without_writes(self):
        result = self.inspect()
        self.assertEqual(result['context_digest'], self.inspect()['context_digest'])
        current = recheck_program_pool(self.program.pk, user=self.officer,
                                      expected_context_digest=result['context_digest'])
        self.assertEqual(current, result)

    def test_source_and_configuration_corrections_change_context(self):
        before = self.inspect()['context_digest']
        self.verify(verified=False)
        after = self.inspect()['context_digest']
        self.assertNotEqual(after, before)
        self.validate()
        self.assertNotEqual(after, self.inspect()['context_digest'])

    def test_new_or_reclassified_application_changes_context(self):
        before = self.inspect()['context_digest']
        new = self.add_application('NEEDS_INFORMATION')
        after = self.inspect()['context_digest']
        self.assertNotEqual(before, after)
        new.status = 'ELIGIBLE'
        new.save(update_fields=['status'])
        self.assertNotEqual(after, self.inspect()['context_digest'])

    def test_change_between_observations_returns_no_usable_capture(self):
        from .pool_services import _observe
        calls = 0

        def change(*args):
            nonlocal calls
            result = _observe(*args)
            calls += 1
            if calls == 1:
                self.assess('ND')
            return result
        with patch('ewaf.pool_services._observe', side_effect=change):
            result = self.inspect()
        self.assertFalse(result['observations_match'])
        self.assertFalse(result['inventory_complete'])
        self.assertIsNone(result['context_digest'])
        self.assertEqual(result['manifest'], [])
        self.assertEqual(result['evidence_ready_ids'], [])

    def test_mid_read_account_revocation_denies_response(self):
        from .pool_services import _observe

        def revoke(*args):
            result = _observe(*args)
            get_user_model().objects.filter(pk=self.officer.pk).update(is_active=False)
            return result
        with patch('ewaf.pool_services._observe', side_effect=revoke), self.assertRaises(PermissionDenied):
            self.inspect()

    def test_outer_transaction_refused(self):
        with transaction.atomic(), self.assertRaises(ValidationError) as raised:
            self.inspect()
        self.assertEqual(raised.exception.code, 'POOL_OBSERVATION_REQUIRES_AUTOCOMMIT')

    def test_private_values_and_error_details_not_in_payload(self):
        result = self.inspect()
        text = json.dumps(result)
        for key in ('monthly_income', 'employment_information', 'score_0_1', 'score_0_100', 'contribution'):
            self.assertNotIn('"' + key + '"', text)
        self.assertNotIn(self.member.full_name, text)
        with patch('ewaf.pool_services.evaluate_application', side_effect=ValidationError('PRIVATE RAW SECRET')):
            blocked = self.inspect()
        self.assertNotIn('PRIVATE RAW SECRET', json.dumps(blocked))
        self.assertIn('SOURCE_REVIEW_UNAVAILABLE', blocked['reasons'])
        self.assertIn(str(self.application.pk), blocked['eligible_status_ids'])

    def test_forged_numerical_readiness_rejected(self):
        from .scoring_inputs import evaluate_application
        forged = evaluate_application(self.application, user=self.officer)
        forged['score_0_1'] = '1'
        with patch('ewaf.pool_services.evaluate_application', return_value=forged):
            result = self.inspect()
        self.assertIsNone(result['items'][0]['readiness'])
        self.assert_blocked(result)

    def test_disabled_write_contracts_even_with_flag_and_staff(self):
        calls = (lambda: request_recalculation(self.program.pk, user=self.officer, reason='Synthetic',
                    expected_context_digest='a' * 64, request_key='retry-1'),
                 lambda: process_recalculation(1, user=self.officer),
                 lambda: current_pool_result(self.program.pk, user=self.officer))
        with override_settings(EWAF_OPERATIONAL_BACKEND_ENABLED=True):
            for call in calls:
                for _ in range(2):
                    with self.assertNumQueries(0), self.assertRaises(ValidationError) as raised:
                        call()
                    self.assertEqual(raised.exception.code, 'DURABLE_POOL_STORAGE_UNAVAILABLE')

    def test_disabled_contract_denies_anonymous_first(self):
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            process_recalculation(1, user=AnonymousUser())

    def test_all_business_rows_and_audits_preserved_even_if_audit_unavailable(self):
        def rows():
            return {m._meta.label_lower: list(m.objects.order_by('pk').values()) for m in apps.get_models()}
        before = rows()

        def read_only(execute, sql, params, many, context):
            self.assertTrue(sql.lstrip().upper().startswith('SELECT'), sql[:80])
            return execute(sql, params, many, context)
        with connection.execute_wrapper(read_only), patch.object(ProgramLog.objects, 'create', side_effect=RuntimeError('audit down')):
            result = self.inspect()
            self.assert_blocked(result)
            with self.assertRaises(ValidationError):
                process_recalculation(1, user=self.officer)
        self.assertEqual(before, rows())

    def test_interrupted_observation_leaves_no_partial_records(self):
        before = ProgramLog.objects.count()
        with patch('ewaf.pool_services._observe', side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):
                self.inspect()
        self.assertEqual(before, ProgramLog.objects.count())

    def test_schema_unchanged(self):
        self.assertEqual(MigrationLoader(connection).graph.leaf_nodes('ewaf'), [('ewaf', '0008_operational_four')])

    def test_empty_program_is_not_a_complete_calculation(self):
        program = create_program(ewaf_applicable=True)
        result = inspect_program_pool(program.pk, user=self.officer)
        self.assertTrue(result['inventory_complete'])
        self.assertIn('EMPTY_POOL', result['reasons'])
        self.assertIn('SCORING_POLICY_MISSING', result['reasons'])
        self.assert_blocked(result)
