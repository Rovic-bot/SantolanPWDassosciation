from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from membership.tests import grant
from programs.models import Program, ProgramLog, ProgramTermsLock
from programs.tests import create_program
from .evidence_testsupport import EvidenceHelpers
from .configuration_testsupport import ConfigurationHelpers, equal_judgments
from .configuration_services import (VIEW, record_configuration, record_validation, record_review,
                                     record_authority_evidence, require_configuration_authorization)
from .configuration_readiness import configuration_diagnostics
from .configuration_records import artifact_digest
from .models import (ConfigurationRevision, ConfigurationValidation, ConfigurationReview,
                     ConfigurationAuthorizationEvidence)


class ConfigurationTests(ConfigurationHelpers, EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_evidence()

    def diagnostic(self):
        return configuration_diagnostics(self.program.pk, user=self.officer)

    def test_complete_workflow_stays_non_effective(self):
        original = Program.objects.values().get(pk=self.program.pk)
        draft = self.draft()
        validation = self.validate()
        review = self.review()
        authority = self.authority()
        result = self.diagnostic()
        self.assertEqual(result['reference_consistency'], 'PASSED')
        self.assertEqual(result['review'], 'REVIEWED')
        self.assertEqual(result['authority_evidence'], 'RECORDED_NON_EFFECTIVE')
        self.client.force_login(self.officer)
        response = self.client.get(reverse('ewaf:configuration_detail', args=[self.program.pk]))
        self.assertEqual([code for code, weight in response.context['derived_weights']], ['SI', 'ES', 'PA', 'ND', 'PR'])
        self.assertFalse(result['effective_authorization'])
        self.assertFalse(result['operational_ready'])
        self.assertEqual(Program.objects.values().get(pk=self.program.pk), original)
        for row in (draft, validation, review, authority):
            self.assertEqual(row.digest, artifact_digest(row.payload()))
            self.assertEqual(row.audit_entry.program, self.program)
            self.assertIsNone(row.audit_entry.application)
        for code in ('PROCESSING_GATE_UNAVAILABLE', 'CONFIGURATION_AUTHORIZATION_UNAVAILABLE', 'CRITERION_POLICY_UNAPPROVED'):
            self.assertIn(code, {row['code'] for row in result['reasons']})

    def test_incomplete_invalid_and_inconsistent_drafts_are_retained(self):
        for values in ({}, {'SI:ES': 'NaN'}, {**equal_judgments()['values'], 'SI:ES': '100'}):
            self.draft(judgments={**equal_judgments(), 'values': values})
            validation = self.validate()
            self.assertNotEqual(validation.result['consistency'], 'PASSED')
            self.assertTrue(validation.result['reasons'])
        self.assertEqual(ConfigurationRevision.objects.count(), 3)
        self.assertEqual(ConfigurationValidation.objects.count(), 3)

    def test_missing_policy_is_explicit_pending_not_inferred(self):
        program = create_program()
        from .configuration_services import configuration_context
        from .evidence import digest
        row = record_configuration(program.pk, user=self.officer, policy_id=None, judgments=equal_judgments(),
            expected_context=digest(configuration_context(program)), reason='Synthetic pending policy', confirmed=True)
        self.assertIsNone(row.policy_id)
        self.assertIsNone(row.terms_revision_id)
        self.assertIn('EVIDENCE_POLICY_MISSING', {r['code'] for r in configuration_diagnostics(program.pk, user=self.officer)['reasons']})

    def test_revision_and_each_history_append_predecessors(self):
        first = self.draft()
        self.validate()
        one_review = self.review()
        two_review = self.review(finding='CORRECTIONS_REQUESTED', correction_requests='Synthetic clarification')
        one_authority = self.authority()
        two_authority = self.authority(authority_reference='Synthetic correction reference')
        second = self.draft()
        self.assertEqual(second.previous, first)
        self.assertEqual(two_review.previous, one_review)
        self.assertEqual(two_authority.previous, one_authority)
        self.assertEqual(self.diagnostic()['review'], 'PENDING')
        self.assertEqual(self.diagnostic()['authority_evidence'], 'MISSING')

    def test_new_validation_requires_review_of_exact_latest_result(self):
        self.draft()
        first = self.validate()
        self.review()
        self.authority()
        self.validate()
        with self.assertRaises(ValidationError):
            self.review(validation_id=first.pk)
        self.assertEqual(self.diagnostic()['review'], 'PENDING')
        self.assertEqual(self.diagnostic()['authority_evidence'], 'MISSING')

    def test_context_replay_fails_after_another_draft(self):
        token = self.context_token()
        self.draft()
        with self.assertRaisesMessage(ValidationError, 'CONFIGURATION_CONTEXT_CHANGED'):
            self.draft(expected_context=token)

    def test_changed_policy_blocks_validation_of_stale_configuration(self):
        self.draft()
        self.policy_record()
        with self.assertRaisesMessage(ValidationError, 'CONFIGURATION_STALE'):
            self.validate()
        self.assertIn('CONFIGURATION_STALE', {r['code'] for r in self.diagnostic()['reasons']})

    def test_terms_control_change_detected_without_program_version_bump(self):
        from programs.binding_services import capture_terms
        from programs.terms import snapshot_terms, terms_digest
        self.draft()
        capture_terms(self.program.pk, user=self.officer, version=0, program_version=self.program.version,
            digest=terms_digest(snapshot_terms(self.program)), reason='Synthetic captured terms', confirmed=True)
        with self.assertRaises(ValidationError):
            self.validate()
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, 0)

    def test_cross_program_policy_configuration_and_validation_rejected(self):
        self.draft()
        self.validate()
        other = create_program()
        from .evidence import digest
        from .configuration_services import configuration_context
        values = {**self.common(), 'expected_context': digest(configuration_context(other))}
        with self.assertRaises(ValidationError):
            record_configuration(other.pk, **values, judgments=equal_judgments(), policy_id=self.policy.pk)
        with self.assertRaises(ValidationError):
            record_validation(other.pk, **values, configuration_id=self.configuration.pk)
        with self.assertRaises(ValidationError):
            self.review(validation_id=999999)
        with self.assertRaises(ValidationError):
            self.authority(configuration_id=999999)

    def test_forged_derived_fields_not_accepted_by_services(self):
        for key in ('weights', 'digest', 'actor', 'recorded_at', 'approved', 'effective_authorization'):
            with self.subTest(key=key), self.assertRaises(TypeError):
                self.draft(**{key: 'forged'})

    def test_all_artifacts_block_supported_mutation_paths(self):
        self.draft()
        self.validate()
        records = [self.configuration, self.validation, self.review(), self.authority()]
        for row in records:
            model = type(row)
            for action in (lambda: row.save(), lambda: row.delete(), lambda: model.objects.all().delete(),
                           lambda: model.objects.all().update(reason='overwritten'),
                           lambda: model.objects.bulk_update([row], ['reason']),
                           lambda: model.objects.bulk_create([row]),
                           lambda: model.objects.bulk_create([row], update_conflicts=True, update_fields=['reason']),
                           lambda: model.objects.create(**{f.attname: getattr(row, f.attname) for f in row._meta.fields})):
                with self.subTest(model=model.__name__), self.assertRaises(ValidationError):
                    action()

    def test_wrong_audit_and_forged_calculation_fail_integrity(self):
        self.draft()
        validation = self.validate()
        validation.audit_entry = self.configuration.audit_entry
        with self.assertRaises(ValidationError):
            validation.clean()
        validation.refresh_from_db()
        validation.result['calculation']['weights']['SI'] = '1'
        with self.assertRaises(ValidationError):
            validation.clean()

    def test_tampered_audit_cannot_make_current_review(self):
        self.draft()
        self.validate()
        review = self.review()
        ProgramLog.objects.filter(pk=review.audit_entry_id).update(actor=None)
        result = self.diagnostic()
        self.assertEqual(result['review'], 'PENDING')
        self.assertIn('ARTIFACT_INTEGRITY_FAILED', {row['code'] for row in result['reasons']})

    def test_audit_failure_rolls_back_every_write_type(self):
        for name, operation, model in [('draft', self.draft, ConfigurationRevision),
                ('validation', self.validate, ConfigurationValidation), ('review', self.review, ConfigurationReview),
                ('authority', self.authority, ConfigurationAuthorizationEvidence)]:
            before = model.objects.count()
            with patch('ewaf.configuration_services.ProgramLog.objects.create', side_effect=RuntimeError('Synthetic audit failure')):
                with self.assertRaises(RuntimeError):
                    operation()
            self.assertEqual(model.objects.count(), before)
            if name in ('draft', 'validation'):
                operation()

    def test_artifact_failure_rolls_back_mandatory_audit(self):
        before = ProgramLog.objects.count()
        with patch('ewaf.models.ConfigurationRevision.save', side_effect=RuntimeError('Synthetic record failure')):
            with self.assertRaises(RuntimeError):
                self.draft()
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_confirmation_scope_and_correction_explanation_required(self):
        with self.assertRaises(ValidationError):
            self.draft(confirmed=False)
        self.draft()
        self.validate()
        for changes in ({'attested': False}, {'attested': 1}, {'authority_reference': ''}, {'stated_scope': ''},
                        {'authority_reference': None}, {'stated_scope': None}):
            with self.assertRaises(ValidationError):
                self.authority(**changes)
        with self.assertRaises(ValidationError):
            self.review(finding='CORRECTIONS_REQUESTED')
        with self.assertRaises(ValidationError):
            self.review(correction_requests=None)

    def test_private_explanations_not_copied_to_general_audit(self):
        row = self.draft(reason='Synthetic confidential methodological explanation')
        self.assertNotIn('confidential', row.audit_entry.notes)
        self.assertNotIn('confidential', str(row.audit_entry.changes))

    def test_explicit_permissions_and_no_automatic_staff_grants(self):
        viewer = get_user_model().objects.create_user('g14_viewer', is_staff=True)
        self.assertFalse(viewer.has_perm('ewaf.record_configurationrevision'))
        for user in (viewer, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                self.draft(user=user)
        grant(viewer, 'accounts.access_dashboard', *VIEW)
        viewer = get_user_model().objects.get(pk=viewer.pk)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('ewaf:configuration_detail', args=[self.program.pk])).status_code, 200)
        for action in ('draft', 'validate', 'review', 'authority'):
            self.assertEqual(self.client.get(reverse('ewaf:configuration_action', args=[self.program.pk, action])).status_code, 403)

    def test_view_permission_does_not_grant_other_service_actions(self):
        self.draft()
        self.validate()
        user = get_user_model().objects.create_user('g14_drafter', is_staff=True)
        grant(user, 'accounts.access_dashboard', *VIEW, 'ewaf.record_configurationrevision')
        for action in (self.validate, self.review, self.authority):
            with self.assertRaises(PermissionDenied):
                action(user=user)

    def test_inactive_or_nonstaff_users_cannot_record(self):
        for active, staff in ((False, True), (True, False)):
            self.officer.is_active, self.officer.is_staff = active, staff
            with self.assertRaises(PermissionDenied):
                self.draft()

    def test_gets_are_read_only_and_never_create_mutex(self):
        self.draft()
        self.validate()
        ProgramTermsLock.objects.all().delete()
        self.client.force_login(self.officer)
        before = ProgramLog.objects.count()
        urls = [reverse('ewaf:configuration_list'), reverse('ewaf:configuration_detail', args=[self.program.pk]),
                reverse('ewaf:configuration_history', args=[self.program.pk])]
        urls += [reverse('ewaf:configuration_action', args=[self.program.pk, action]) for action in ('draft', 'validate', 'review', 'authority')]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assertFalse(ProgramTermsLock.objects.exists())

    def test_csrf_anonymous_and_method_restrictions(self):
        route = reverse('ewaf:configuration_action', args=[self.program.pk, 'draft'])
        self.assertEqual(self.client.get(route).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        self.assertEqual(client.post(route, {}).status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.put(route, {}).status_code, 405)
        history = reverse('ewaf:configuration_history', args=[self.program.pk])
        self.assertEqual(self.client.get(history, {'revision': 'forged'}).status_code, 404)

    def test_retired_workflows_and_processing_barrier_remain_disabled(self):
        from .services import save_configuration, save_input, generate_ranking, current_ranking, require_ranked
        from .readiness import require_operational_evidence
        from assistance.services import decide_assistance, record_release
        from assistance.tests import decision_data, release_data
        self.draft()
        self.validate()
        self.review()
        self.authority()
        for action in (lambda: save_configuration(user=self.officer, data={}),
                lambda: save_input(self.application.pk, user=self.officer, data={}),
                lambda: generate_ranking(self.program.pk, user=self.officer, configuration=None, version=0),
                lambda: current_ranking(self.program), lambda: require_ranked(self.application, self.program),
                require_configuration_authorization, require_operational_evidence,
                lambda: decide_assistance(self.application.pk, user=self.officer, data=decision_data(self.application)),
                lambda: record_release(self.application.pk, user=self.officer, data=release_data(self.application))):
            with self.assertRaises(ValidationError):
                action()
