from copy import deepcopy
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, Client
from django.urls import reverse
from programs.models import ProgramLog
from programs.tests import create_program
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .scoring_services import validate_run, record_scoring_policy
from .scoring_inputs import VIEW, READINESS_VIEW, validate_readiness_payload
from .scoring_readiness import require_operational_scoring
from .scoring_policy import proposal
from .models import (ScoringPolicyRevision, CalculationDiagnosticRun, CalculationDiagnosticItem, CalculationCriterionTrace,
                     RankingRun, Snapshot)


class ScoringServiceTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_scoring()

    def test_pending_policy_and_exact_references(self):
        self.assertEqual(self.scoring_policy.configuration_id, self.configuration.pk)
        self.assertEqual(self.scoring_policy.validation_digest, self.validation.digest)
        self.assertEqual(self.scoring_policy.proposal['criteria']['SI'], {})
        self.assertFalse(self.diagnostic()['operational_ready'])

    def test_sequential_proposals_preserve_program_version(self):
        version = self.program.version
        row = self.propose()
        self.assertEqual(row.previous_id, self.scoring_policy.pk)
        self.assertEqual(row.revision, 2)
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, version)

    def test_complete_atomic_graph_and_neutral_audits(self):
        run = self.capture_diagnostic()
        validate_run(run)
        self.assertEqual(run.items.count(), 1)
        self.assertEqual(run.items.first().traces.count(), 5)
        self.assertEqual(ProgramLog.objects.filter(action__startswith='g15_').count(), 8)
        for log in ProgramLog.objects.filter(action__startswith='g15_'):
            self.assertEqual(set(log.changes), {'artifact', 'digest'})
        self.assertFalse(RankingRun.objects.exists())
        self.assertFalse(Snapshot.objects.exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')

    def test_no_numeric_applicant_payload_or_columns(self):
        run = self.capture_diagnostic()
        self.assertNotIn('score', run.result)
        self.assertNotIn('weights', run.result)
        for model in (CalculationDiagnosticRun, CalculationDiagnosticItem, CalculationCriterionTrace):
            self.assertFalse({'score', 'normalized', 'contribution', 'weight', 'value'} & {f.name for f in model._meta.fields})
        forged = deepcopy(run.result)
        forged['score_0_1'] = '0.9'
        with self.assertRaises(ValidationError):
            validate_readiness_payload(forged)

    def test_cross_program_references_rejected(self):
        other = create_program(name='Synthetic other program')
        with self.assertRaises(ValidationError):
            self.capture_diagnostic(program_id=other.pk)
        with self.assertRaises(ValidationError):
            self.propose(configuration_id=self.configuration.pk + 10000)
        with self.assertRaises(ValidationError):
            self.propose(validation_id=True)

    def test_stale_policy_context_and_validation(self):
        values = self.proposal_values()
        self.validate()
        with self.assertRaises(ValidationError):
            record_scoring_policy(self.program.pk, **values)
        self.assertIn('SCORING_POLICY_STALE', {r['code'] for r in self.diagnostic()['reasons']})

    def test_stale_member_context_rejected(self):
        token = self.diagnostic()['context_digest']
        self.member.version += 1
        self.member.save(update_fields=['version'])
        with self.assertRaises(ValidationError):
            self.capture_diagnostic(expected_context=token)

    def test_actor_and_client_calculations_not_accepted(self):
        for forged in ({'actor': self.officer}, {'digest': 'f' * 64}, {'weights': {}}, {'score': '0.7'}):
            with self.assertRaises(TypeError):
                self.propose(**forged)

    def test_audit_failure_rolls_back_entire_capture(self):
        from .scoring_services import persist as actual
        counter = 0
        def failing(row):
            nonlocal counter
            counter += 1
            if counter == 5:
                raise ValidationError('Synthetic trace failure')
            return actual(row)
        before = ProgramLog.objects.count()
        with patch('ewaf.scoring_services.persist', side_effect=failing), self.assertRaises(ValidationError):
            self.capture_diagnostic()
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assertFalse(CalculationDiagnosticRun.objects.exists())
        self.assertFalse(CalculationCriterionTrace.objects.exists())
        with patch('ewaf.scoring_services.ProgramLog.objects.create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.propose()
        self.assertEqual(ScoringPolicyRevision.objects.count(), 1)

    def test_wrong_audit_association_detected(self):
        run = self.capture_diagnostic()
        run.audit_entry = self.scoring_policy.audit_entry
        with self.assertRaises(ValidationError):
            run.clean()

    def test_append_only_all_supported_paths(self):
        run = self.capture_diagnostic()
        for row in (self.scoring_policy, run, run.items.first(), run.items.first().traces.first()):
            with self.subTest(model=type(row).__name__):
                for action in (lambda: row.save(), lambda: row.delete(), lambda: type(row).objects.filter(pk=row.pk).update(reason='forged'),
                               lambda: type(row).objects.filter(pk=row.pk).delete(), lambda: type(row).objects.bulk_update([row], ['reason']),
                               lambda: type(row).objects.bulk_create([row])):
                    with self.assertRaises(ValidationError):
                        action()

    def test_permission_checks_before_private_reads(self):
        user = get_user_model().objects.create_user('synthetic_g15_limited', is_staff=True)
        with self.assertRaises(PermissionDenied):
            self.diagnostic(user=user)
        with self.assertRaises(PermissionDenied):
            self.propose(user=user)
        user.user_permissions.set(Permission.objects.filter(codename__in=[p.split('.')[1] for p in (*VIEW, 'accounts.access_dashboard')]))
        user = get_user_model().objects.get(pk=user.pk)
        with self.assertRaises(PermissionDenied):
            self.propose(user=user)
        with self.assertRaises(PermissionDenied):
            self.diagnostic(user=user)
        self.assertFalse(user.groups.exists())

    def test_nonstaff_and_inactive_superuser_rejected(self):
        for field in ('is_active', 'is_staff'):
            setattr(self.officer, field, False)
            with self.assertRaises(PermissionDenied):
                self.diagnostic()
            setattr(self.officer, field, True)

    def test_barriers_unconditional(self):
        for code in ('CRITERION_POLICY_UNAPPROVED', 'CONFIGURATION_AUTHORIZATION_UNAVAILABLE',
                     'OPERATIONAL_SCORING_UNAVAILABLE', 'PROCESSING_GATE_UNAVAILABLE'):
            self.assertIn(code, {r['code'] for r in self.diagnostic()['reasons']})
        with self.assertRaisesMessage(ValidationError, 'OPERATIONAL_SCORING_UNAVAILABLE'):
            require_operational_scoring(self.capture_diagnostic(), confirmed=True)

    def test_unknown_policy_fields_and_numeric_types_rejected(self):
        for field, value in (('approved', 'yes'), ('encoding', {'x': True}), ('bounds', {'method': 'fixed', 'lower': 'NaN'})):
            payload = deepcopy(self.scoring_policy.proposal)
            payload['criteria']['SI'][field] = value
            with self.assertRaises(ValidationError):
                proposal(payload)

    def test_gets_read_only_no_store_and_no_calculator_endpoint(self):
        self.client.force_login(self.officer)
        before = ProgramLog.objects.count()
        for name, kwargs in [('scoring_list', {}), ('scoring_policy', {'pk': self.program.pk}),
                             ('scoring_diagnostics', {'reference': self.application.pk}), ('scoring_history', {'reference': self.application.pk})]:
            response = self.client.get(reverse('ewaf:' + name, kwargs=kwargs))
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertNotContains(response, 'name="weights"')
            self.assertNotContains(response, 'name="score"')
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assertEqual(self.client.post('/ewaf/diagnostics/calculate/', {}).status_code, 404)

    def test_csrf_and_action_permissions(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        url = reverse('ewaf:scoring_diagnostics', kwargs={'reference': self.application.pk})
        self.assertEqual(client.post(url, self.capture_values()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_synthetic_trace_replays_exact_g14_artifacts(self):
        import json
        import os
        from pathlib import Path
        from .scoring_inputs import weight_evidence
        from .weighted_scoring import calculate_synthetic
        from .test_weighted_scoring import synthetic_case
        case = synthetic_case()
        case['judgments']['values']['SI:ES'] = '2'
        self.draft(judgments=case['judgments'])
        self.validate()
        policy = self.propose()
        case['judgments'] = policy.configuration.judgments
        case['validation'] = policy.validation.result
        weights = weight_evidence(policy, user=self.officer)
        result = calculate_synthetic(**case)
        self.assertTrue(result['complete'])
        self.assertEqual([row['weight'] for row in result['traces']], [weights[key] for key in case['criteria']])
        artifact = {'synthetic_only': True, 'application': None, 'fixture': case, 'result': result,
                    'references': {'configuration': policy.configuration_id, 'configuration_digest': policy.configuration_digest,
                                   'validation': policy.validation_id, 'validation_digest': policy.validation_digest,
                                   'policy': policy.pk, 'policy_digest': policy.digest}}
        if os.environ.get('G12_ARTIFACT_DIR'):
            (Path(os.environ['G12_ARTIFACT_DIR']) / 'g15-synthetic-trace.json').write_text(json.dumps(artifact, indent=2), encoding='utf-8')
