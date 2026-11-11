"""SES revision: independent arithmetic and real services, synthetic MySQL only."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from itertools import permutations
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import dataset_methods as methods, vault_services as vault, operational_services as operational
from .weight_input import project, percentages
from .dataset_methods import SES_CRITERIA as CODES
from .revised import contracts, live_services as policies, live_evidence as evidence, live_math
from .revised.live_models import SharedDatasetPolicy, DatasetInputReview
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
from .vault_models import VaultRevision
from . import test_dataset_policy as dataset_tests


def proposal(order=CODES, units=(4478, 2322, 1601, 1599)):
    return {'order': list(order), 'weights': dict(zip(order, units))}


def calculate_fixture(weights, rows=None, slots=2):
    rows = rows or {'A': ('5000', 'Seasonal Worker', '1', '4'),
                    'B': ('12500', 'Unemployed', '0', '2'), 'C': ('20000', 'Full-Time Worker', '3', '6')}
    config = SimpleNamespace(digest='synthetic-config', policy={'method': methods.SES},
        validation={'weights': dict(zip(CODES, map(str, weights))), 'weight_digest': 'synthetic-weights'},
        source={'terms': {'program': {'slots': slots}}}, dataset_policy=SimpleNamespace(digest='synthetic-policy'),
        assessment_cutoff=timezone.now())
    snapshot = {'engine': methods.SES, 'configuration_digest': config.digest, 'eligible': {
        key: {'inputs': {code: {'value': value} for code, value in zip(CODES, values)}} for key, values in rows.items()}}
    return live_math.calculations(snapshot, config)


class SesArithmeticTests(SimpleTestCase):
    def test_schema_graph_has_no_unreviewed_model_changes(self):
        from django.apps import apps
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.autodetector import MigrationAutodetector
        from django.db.migrations.state import ProjectState
        loader = MigrationLoader(None)
        self.assertEqual(loader.graph.leaf_nodes('ewaf'), [('ewaf', '0012_dataset_policy_integration')])
        changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
        self.assertEqual(changes, {})

    def test_requested_fractional_teaching_fixture_separate_from_operational_projection(self):
        q = [Fraction(n, 7640) for n in (3421, 1774, 1223, 1222)]
        matrix = [[a / b for b in q] for a in q]
        totals = [sum(row[j] for row in matrix) for j in range(4)]
        weights = [sum(row[j] / totals[j] for j in range(4)) / 4 for row in matrix]
        cv = [sum(row[j] * weights[j] for j in range(4)) / weights[i] for i, row in enumerate(matrix)]
        self.assertEqual(weights, q)
        self.assertEqual(cv, [4] * 4)
        self.assertEqual(((sum(cv) / 4 - 4) / 3) / Fraction('0.90'), 0)
        result = calculate_fixture(q)
        self.assertEqual([100 * Fraction(result[k]['score_exact']) for k in 'ABC'],
                         [Fraction(15075, 191), Fraction(47075, 764), Fraction(3055, 191)])
        self.assertEqual([result[k]['score_display'] for k in 'ABC'], ['78.93', '61.62', '15.99'])

    def test_actual_word_file_equal_placeholder_fixture_is_disclosed_separately(self):
        result = calculate_fixture([Fraction(1, 4)] * 4)
        self.assertEqual([100 * Fraction(result[k]['score_exact']) for k in 'ABC'],
                         [Fraction(425, 6), Fraction(125, 2), Fraction(25)])

    def test_actual_projection_matches_independent_matrix_weights_and_cr(self):
        judgments, result, origin = project(proposal())
        self.assertEqual(judgments, {'SES:ES': '2', 'SES:PA': '3', 'SES:HM': '3',
                                    'ES:PA': '2', 'ES:HM': '2', 'PA:HM': '1'})
        matrix = [[Fraction(v) for v in row] for row in (
            ('1', '2', '3', '3'), ('1/2', '1', '2', '2'),
            ('1/3', '1/2', '1', '1'), ('1/3', '1/2', '1', '1'))]
        expected = [Fraction(331, 728), Fraction(383, 1456), Fraction(411, 2912), Fraction(411, 2912)]
        actual = [Fraction(result['weights'][code]) for code in CODES]
        tolerance = Fraction(1, 10**47)  # 50-digit Decimal divisions; not a consistency tolerance.
        for value, reference in zip(actual, expected):
            self.assertLess(abs(value - reference), tolerance)
        cv = [sum(row[j] * expected[j] for j in range(4)) / expected[i] for i, row in enumerate(matrix)]
        exact_cr = (sum(cv) / 4 - 4) / 3 / Fraction('0.90')
        self.assertLess(abs(Fraction(result['CR']) - exact_cr), tolerance)
        self.assertEqual(result['RI'], '0.90')
        self.assertEqual(result['reference_consistency'], 'PASSED')
        self.assertNotEqual(Fraction(result['CR']), 0)
        self.assertEqual(origin['judgment_origin'], 'generated_from_slider_ratios_not_independently_elicited')
        scores = calculate_fixture(actual)
        self.assertEqual([scores[k]['score_display'] for k in 'ABC'], ['79.47', '63.15', '14.11'])
        self.assertEqual([scores[k]['comparison']['business_rank'] for k in 'ABC'], [1, 2, 3])
        self.assertTrue(all([t['criterion'] for t in row['traces']] == list(CODES) for row in scores.values()))
        self.assertEqual(sum(percentages(result['weights']).values()), 10000)

    def test_other_vectors_and_all_priority_orders_keep_codes_and_four_criteria(self):
        for order in permutations(CODES):
            for vector in ((4000, 3000, 2000, 1000), (3500, 2500, 2500, 1500),
                           (5000, 2500, 1250, 1250), (4000, 2000, 2000, 2000)):
                _, result, _ = project(proposal(order, vector))
                self.assertEqual(set(result['weights']), set(CODES))
                self.assertEqual(result['criteria'], list(CODES))
                weights = [Decimal(result['weights'][code]) for code in order]
                self.assertEqual(weights, sorted(weights, reverse=True))
                self.assertEqual(len(result['pairs']), 6)
                if vector in ((5000, 2500, 1250, 1250), (4000, 2000, 2000, 2000)):
                    self.assertEqual(contracts.validate_weight_total(result['weights']), 1)

    def test_existing_precision_contract_is_reused_without_rescaling_overruns(self):
        _, result, _ = project(proposal(units=(4000, 3000, 2000, 1000)))
        self.assertEqual(sum(map(Fraction, result['weights'].values())) - 1, Fraction(15, 10**51))
        with self.assertRaises(ValidationError):
            contracts.validate_weight_total(result['weights'])
        for weights in (dict.fromkeys(CODES, '0.19'), dict.fromkeys(CODES, '0.26')):
            with self.assertRaises(ValidationError):
                contracts.validate_weight_total(weights)

    def test_exact_and_near_ties_use_full_scores_and_capacity_boundary(self):
        rows = {'A': ('5000', 'Seasonal Worker', '1', '4'), 'B': ('5000', 'Seasonal Worker', '1', '4'),
                'C': ('20000', 'Full-Time Worker', '3', '2')}
        result = calculate_fixture([Fraction(1, 4)] * 4, rows, slots=1)
        self.assertEqual([result[k]['comparison']['business_rank'] for k in 'ABC'], [1, 1, 3])
        self.assertTrue(result['A']['comparison']['capacity_boundary_tie'])
        rows['B'] = ('5000.00000001', 'Seasonal Worker', '1', '4')
        result = calculate_fixture([Fraction(1, 4)] * 4, rows, slots=1)
        self.assertEqual(result['A']['score_display'], result['B']['score_display'])
        self.assertEqual([result[k]['comparison']['business_rank'] for k in 'ABC'], [1, 2, 3])

    def test_invalid_weights_and_constant_columns_do_not_get_defaults(self):
        for vector in ((10000, 0, 0, 0), (7000, 1500, 1000, 500), (4000, 3000, 2000, 999), (3000, 4000, 2000, 1000)):
            with self.assertRaises(ValidationError):
                project(proposal(units=vector))
        with self.assertRaisesMessage(ValidationError, 'Constant-value'):
            calculate_fixture([Fraction(1, 4)] * 4, {'A': ('5000', 'Unemployed', '0', '4')})

    def test_historical_si_and_four_and_five_matrices_still_reproduce(self):
        from .revised.si import score
        from .household_math import ahp as five
        from .household_criteria import PAIRS
        from .four_criterion_development import ahp as old_four
        from .operational_policy import ahp as dispatch
        self.assertEqual([score({'four_ps': a, 'indigency': b}) for a, b in
            ((True, True), (True, False), (False, True), (False, False))], ['5', '2.5', '2.5', '0'])
        old = old_four()
        self.assertEqual(dispatch(old['pairs']), old)
        result = five(dict.fromkeys(PAIRS, '1'))
        self.assertEqual(result['RI'], '1.12')
        self.assertEqual(result['weights'], dict.fromkeys(('HI', 'SI', 'ES', 'PA', 'HM'), '0.2'))


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class SesWorkflowTests(TransactionTestCase):
    draft = dataset_tests.DatasetPolicyTests.draft
    approve = dataset_tests.DatasetPolicyTests.approve
    bind = dataset_tests.DatasetPolicyTests.bind
    publish = dataset_tests.DatasetPolicyTests.publish
    applicant = dataset_tests.DatasetPolicyTests.applicant
    generate = dataset_tests.DatasetPolicyTests.generate
    choose = dataset_tests.DatasetPolicyTests.choose
    test_ses_acceptance_and_calculation_audit_rollback = dataset_tests.DatasetPolicyTests.test_acceptance_calculation_and_binding_audit_failures_roll_back
    test_ses_flags_cutoff_and_unsupported_policy_guards = dataset_tests.DatasetPolicyTests.test_feature_flags_cutoff_approved_scope_and_unsupported_rules_are_not_bypassed
    test_ses_binding_and_all_three_approval_groups_require_authority = dataset_tests.DatasetPolicyTests.test_authorization_is_required_for_binding_and_all_three_review_groups

    def setUp(self):
        dataset_tests.DatasetPolicyTests.setUp(self)
        self.old_weights, self.old_program = self.weights, self.program
        self.old_content = deepcopy(self.content)
        self.old_payload = self.weights.payload()
        from programs.tests import program_data
        from programs.services import save_program, change_publication
        from programs.test_approved_terms import TermsHelpers
        with patch('django.utils.timezone.now', return_value=self.base):
            for status in ('DRAFT', 'LOCKED'):
                self.weights = vault.record_ses_weights(user=self.user, expected=vault.token(),
                    proposal=proposal(), reason='SYNTHETIC SES weights; no institutional authority', status=status)
            self.program = save_program(user=self.user, data=program_data(ewaf_applicable=True,
                name='SYNTHETIC SES program', benefit='Synthetic benefit', slots=1,
                selection_method='Synthetic SES ranking and separate human decisions',
                registration_opens_at=self.base + timedelta(hours=1), registration_closes_at=self.base + timedelta(days=1)))
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='authorize_policy', notes='SYNTHETIC program authority')
        self.program.refresh_from_db()
        helper = TermsHelpers()
        helper.program, helper.officer = self.program, self.user
        helper.reconcile()
        self.cutoff = self.program.registration_closes_at + timedelta(hours=1)
        self.content = contracts.initial_content(methods.SES)
        for key, (_, _, kind) in contracts.specifications(self.content).items():
            if isinstance(kind, dict):
                value = next(iter(kind))
            elif kind == 'documents':
                value = [self.doc_type.pk]
            elif kind == 'integer':
                value = 90 if key == 'evidence_max_age_days' else 12 if key == 'pa_months' else 3
            elif kind == 'datetime':
                value = (self.base - timedelta(days=1) if key == 'effective_from' else timezone.now() + timedelta(days=20)).isoformat()
            else:
                value = 'SYNTHETIC reviewed ' + key + '; not an institutional operating rule.'
            self.content['choices'][key] = {'value': value, 'specified': True}

    def accept(self, app, proof, *, low=False, selections=None, **changes):
        findings = {**evidence.periods(self.configuration), 'income_monthly': ['5000' if low else '20000'] * 3,
            'employment': 'Unemployed' if low else 'Full-Time Worker', 'household_members': 6 if low else 2,
            'history_complete': True, 'assessment_finding': 'SYNTHETIC verified source findings',
            'income_consistency': 'consistent', 'income_resolution': ''}
        findings.update(changes)
        return evidence.record(app.pk, user=self.user, expected=evidence.review_token(app, self.configuration),
            findings=findings, selections=selections or {code: [proof.pk] for code in CODES},
            state='ACCEPTED', reason='SYNTHETIC SES evidence acceptance', confirmed=True)

    def pool(self):
        self.publish()
        a, ar = self.applicant('SES-A')
        b, br = self.applicant('SES-B', prior=True)
        self.accept(a, ar, low=True)
        self.accept(b, br)
        return a, ar, b, br

    def test_full_policy_acceptance_ranking_selection_publication_and_release_journey(self):
        from announcements.results import prepare_results, publish_results, results_current
        from assistance.services import record_release
        from assistance.tests import release_data
        a, ar, b, br = self.pool()
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        response = self.client.post(url, {'action': 'GENERATE',
            'expected': json.dumps(operational.context(self.program.pk, user=self.user)),
            'request_key': str(uuid4()), 'reason': 'SYNTHETIC HTTP generation'})
        self.assertEqual(response.status_code, 302)
        run = OperationalRun.objects.get(program=self.program)
        run.clean()
        self.assertEqual(run.snapshot['engine'], methods.SES)
        self.assertFalse(OperationalDecision.objects.exists())
        for row in run.calculations.values():
            self.assertEqual([t['criterion'] for t in row['traces']], list(CODES))
            self.assertNotIn('classification', row)
        self.choose(run, a)
        self.choose(run, b, outcome='NOT_SELECTED')
        item = prepare_results(self.program.pk, user=self.user, version=0, reason='SYNTHETIC permitted result preparation')
        public = str(item.result_revision.public_payload)
        for private in (a.member.full_name, a.public_reference, 'score_0_100', 'income_monthly', 'score_exact', 'supporting'):
            self.assertNotIn(private, public)
        item = publish_results(item.pk, user=self.user, version=item.version)
        self.assertTrue(results_current(item))
        a.refresh_from_db()
        release = record_release(a.pk, user=self.user, data=release_data(a))
        self.assertIsNotNone(release)
        retained = deepcopy(run.payload())
        run.refresh_from_db()
        run.clean()
        self.assertEqual(run.payload(), retained)
        self.old_weights.refresh_from_db()
        self.old_weights.clean()
        self.assertEqual(self.old_weights.payload(), self.old_payload)

    def test_slider_fixture_b_from_stored_weights_accepted_findings_and_actual_ledger(self):
        from programs.tests import create_program
        from programs.testsupport import application_fixture
        from assistance.services import review_eligibility, decide_assistance, record_release
        from assistance.tests import review_data, decision_data, release_data
        self.publish()
        a, ar = self.applicant('SES-FIXTURE-A', prior=True)
        b, br = self.applicant('SES-FIXTURE-B')
        c, cr = self.applicant('SES-FIXTURE-C', prior=True)
        with patch('django.utils.timezone.now', return_value=self.base + timedelta(hours=2)):
            for _ in range(2):
                old = create_program(registration_opens_at=self.base - timedelta(days=2),
                    registration_closes_at=self.base - timedelta(days=1))
                app = application_fixture(old, c.member)
                review_eligibility(app.pk, user=self.user, data=review_data(app))
                decide_assistance(app.pk, user=self.user, data=decision_data(app))
                record_release(app.pk, user=self.user, data=release_data(app))
        self.accept(a, ar, income_monthly=['5000'] * 3, employment='Seasonal Worker', household_members=4)
        self.accept(b, br, income_monthly=['12500'] * 3, employment='Unemployed', household_members=2)
        self.accept(c, cr, income_monthly=['20000'] * 3, employment='Full-Time Worker', household_members=6)
        run = self.generate()
        run.clean()
        self.assertEqual(run.configuration.validation['weights'], project(proposal())[1]['weights'])
        self.assertEqual([run.snapshot['eligible'][str(app.pk)]['inputs']['PA']['value'] for app in (a, b, c)], ['1', '0', '3'])
        self.assertEqual([run.calculations[str(app.pk)]['score_display'] for app in (a, b, c)], ['79.47', '63.15', '14.11'])
        self.assertEqual([run.calculations[str(app.pk)]['comparison']['business_rank'] for app in (a, b, c)], [1, 2, 3])

    def test_real_binding_and_input_forms_accept_exactly_four_findings(self):
        from programs.services import change_publication
        approved = self.approve()
        response = self.client.post(reverse('ewaf:dataset_binding', args=[self.program.pk]), {
            'expected': operational.configuration_token(self.program), 'policy': approved.pk,
            'cutoff': self.cutoff.isoformat(), 'reason': 'SYNTHETIC HTTP immutable binding'})
        self.assertEqual(response.status_code, 302)
        self.configuration = OperationalConfiguration.objects.filter(program=self.program).first()
        with patch('django.utils.timezone.now', return_value=self.base):
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='published', notes='SYNTHETIC HTTP-bound program')
        self.program.refresh_from_db()
        app, proof = self.applicant('SES-HTTP-ACCEPT')
        response = self.client.post(reverse('ewaf:dataset_inputs', args=[app.pk]), {
            'expected': evidence.review_token(app, self.configuration), 'state': 'ACCEPTED',
            'income_0': '90000', 'income_1': '100000', 'income_2': '110000',
            'employment': 'Part-Time Worker', 'household_members': 4, 'history_complete': 'on',
            'assessment_finding': 'SYNTHETIC complete income and history review',
            'income_consistency': 'consistent', 'income_resolution': '', 'confirmed': 'on',
            'reason': 'SYNTHETIC explicit new-method acceptance', **{'evidence_' + code: [proof.pk] for code in CODES}})
        self.assertEqual(response.status_code, 302)
        saved = DatasetInputReview.objects.filter(application=app).first()
        self.assertEqual(set(saved.inputs), set(CODES))
        self.assertEqual(saved.inputs['SES']['value'], '100000')
        self.assertNotIn('si_documents', saved.findings)

    def test_unresolved_application_is_not_silently_omitted_and_foreign_evidence_is_rejected(self):
        from members.tests import create_member
        from programs.testsupport import application_fixture
        a, ar, b, br = self.pool()
        with self.assertRaises(ValidationError):
            self.accept(a, ar, selections={code: [br.pk] for code in CODES})
        with patch('django.utils.timezone.now', return_value=self.base + timedelta(hours=2)):
            unresolved = application_fixture(self.program, create_member('SES-UNRESOLVED'))
        with self.assertRaises(ValidationError):
            self.generate()
        self.assertTrue(self.program.applications.filter(pk=unresolved.pk).exists())
        self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())

    def test_vault_setup_has_no_defaults_and_retains_saved_four_criterion_drafts(self):
        from .vault_forms import SesSetupForm, ses_state
        form = SesSetupForm(initial={'expected': vault.token()})
        self.assertTrue(all(form[code].value() is None for code in CODES))
        self.assertIsNone(ses_state(self.old_weights))
        url = reverse('ewaf:vault') + '?method=' + methods.SES
        page = self.client.get(url)
        self.assertEqual(page.context['weight_state']['proposal'], proposal())
        changed = proposal(order=('HM', 'SES', 'ES', 'PA'), units=(5000, 2500, 1250, 1250))
        data = {'calculation_method': methods.SES, 'weight_method': 'slider-ratio-projection-v1',
            'expected': vault.token(), 'slider_proposal': json.dumps(changed), 'reason': 'SYNTHETIC changed priorities'}
        before = VaultRevision.objects.count()
        self.assertContains(self.client.post(url, data | {'action': 'LOCKED'}), 'unapproved weight draft')
        self.assertEqual(VaultRevision.objects.count(), before)
        self.assertEqual(self.client.post(url, data | {'action': 'DRAFT'}).status_code, 302)
        preview = self.client.post(url, data | {'action': 'PREVIEW_WEIGHTS', 'expected': vault.token()}).json()
        self.assertEqual(preview['consistency']['criteria_count'], 4)
        self.assertEqual(preview['consistency']['RI'], '0.90')
        self.assertEqual(self.client.post(url, data | {'action': 'LOCKED', 'expected': vault.token()}).status_code, 302)
        self.assertEqual(vault.active(methods.SES).validation, project(changed)[1])
        self.assertEqual(self.client.get(url).context['weight_state']['proposal'], changed)

    def test_storage_incompatible_projection_remains_an_unapproved_draft(self):
        changed = proposal(units=(4000, 3000, 2000, 1000))
        draft = vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=changed,
            reason='SYNTHETIC rounding-residue draft', status='DRAFT')
        url = reverse('ewaf:vault') + '?method=' + methods.SES
        preview = self.client.post(url, {'action': 'PREVIEW_WEIGHTS', 'calculation_method': methods.SES,
            'expected': vault.token(), 'slider_proposal': json.dumps(changed)}).json()
        self.assertEqual(preview['consistency']['result'], 'PASSED')
        self.assertTrue(preview['storage_errors'])
        with self.assertRaisesMessage(ValidationError, 'precision'):
            vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=changed,
                reason='SYNTHETIC incompatible precision approval attempt', status='LOCKED')
        self.assertEqual(vault.latest_for(methods.SES), draft)
        with self.assertRaisesMessage(ValidationError, 'provenance'):
            vault.record(user=self.user, expected=vault.token(), proposed=vault.vault_policy.source_policy(methods.SES),
                judgments=project(proposal())[0], status='LOCKED', attested=True,
                reason='SYNTHETIC missing slider provenance')

    def test_compatible_weights_policy_approval_and_intake_remain_separate(self):
        from programs.application_workflow import publication_configuration_problem
        from programs.services import change_publication
        self.assertEqual(publication_configuration_problem(self.program), '')
        self.assertFalse(SharedDatasetPolicy.objects.filter(method=methods.SES, status='APPROVED').exists())
        with patch('django.utils.timezone.now', return_value=self.base):
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='published', notes='SYNTHETIC weights-only intake')
        self.program.refresh_from_db()
        app, proof = self.applicant('SES-INTAKE')
        with self.assertRaises(ValidationError):
            self.generate()
        self.configuration = self.bind()
        self.assertEqual(self.configuration.dataset_policy.method, methods.SES)
        self.accept(app, proof)
        self.assertEqual(DatasetInputReview.objects.get(application=app).inputs['SES']['value'], '20000')

    def test_old_signature_cannot_be_used_as_ses_weights_or_rebound_program(self):
        with self.assertRaises(ValidationError):
            contracts.weight_snapshot(self.old_weights, methods.SES)
        with self.assertRaises(ValidationError):
            policies.save_draft(user=self.user, expected=policies.token(), content=self.content,
                weight_id=self.old_weights.pk, reason='SYNTHETIC incompatible weight attempt')
        with self.assertRaises(ValidationError):
            vault.record_ses_weights(user=self.user, expected=vault.token(), status='DRAFT',
                proposal=proposal(('SI', 'ES', 'PA', 'ND')), reason='SYNTHETIC wrong four-criterion signature')
        approved = self.approve()
        with self.assertRaisesMessage(ValidationError, 'signature'):
            policies.bind(self.old_program.pk, user=self.user,
                expected=operational.configuration_token(self.old_program), policy_id=approved.pk,
                cutoff=self.old_program.registration_closes_at + timedelta(hours=1), reason='SYNTHETIC incompatible binding')
        old_draft = policies.save_draft(user=self.user, expected=policies.token(), content=self.old_content,
            weight_id=self.old_weights.pk, reason='SYNTHETIC retained five-criterion policy draft')
        old_policy = policies.approve(old_draft.pk, user=self.user, expected=old_draft.digest,
            reviewed_groups=['A', 'B', 'C'], reason='SYNTHETIC retained five-criterion policy approval')
        policies.bind(self.old_program.pk, user=self.user, expected=operational.configuration_token(self.old_program),
            policy_id=old_policy.pk, cutoff=self.old_program.registration_closes_at + timedelta(hours=1),
            reason='SYNTHETIC old-method binding')
        with self.assertRaisesMessage(ValidationError, 'signature'):
            policies.bind(self.old_program.pk, user=self.user,
                expected=operational.configuration_token(self.old_program), policy_id=approved.pk,
                cutoff=self.old_program.registration_closes_at + timedelta(hours=1), reason='SYNTHETIC old-policy conversion attempt')

    def test_documents_and_four_ps_are_evidence_without_a_bonus_or_fifth_term(self):
        from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
        from documents.services import verify_document
        from membership.tests import pdf
        optional_type = DocumentType.objects.create(name='SYNTHETIC optional indigency evidence')
        optional_requirement = MembershipDocumentRequirement.objects.create(document_type=optional_type, is_required=False)
        self.content['choices']['evidence_SES']['value'].append(optional_type.pk)
        self.publish()
        a, ar = self.applicant('SES-INVARIANT-A')
        b, br = self.applicant('SES-INVARIANT-B')
        c, cr = self.applicant('SES-INVARIANT-C', prior=True)
        a.member.registration_profile = {'four_ps_member': 'Yes'}
        a.member.save(update_fields=['registration_profile'])
        extra = MembershipApplicationDocument.objects.create(application=a.member.application, requirement=optional_requirement,
            label='SYNTHETIC optional indigency evidence', file=pdf(), content_type='application/pdf', size=50)
        extra_review = verify_document(extra.pk, user=self.user, member_version=a.member.version,
            verified=True, expires_on=None, reason='SYNTHETIC optional evidence review')
        args = {'income_monthly': ['100000'] * 3, 'employment': 'Seasonal Worker', 'household_members': 4}
        accepted = self.accept(a, ar, selections={code: [ar.pk] for code in CODES} |
            {'SES': [ar.pk, extra_review.pk]}, **args)
        self.accept(b, br, **args)
        self.accept(c, cr, low=True)
        self.assertEqual(accepted.inputs['SES']['value'], '100000')
        self.assertEqual(set(accepted.inputs), set(CODES))
        run = self.generate()
        left, right = run.calculations[str(a.pk)], run.calculations[str(b.pk)]
        self.assertEqual(left['score_exact'], right['score_exact'])
        self.assertEqual(left['comparison'], right['comparison'])
        self.assertEqual(len(left['traces']), 4)
        page = self.client.get(reverse('ewaf:dataset_inputs', args=[a.pk]))
        for name in ('si_four_ps', 'si_indigency', 'si_food', 'evidence_SI', 'evidence_HI'):
            self.assertNotContains(page, 'name="' + name + '"')
        self.assertContains(page, 'name="evidence_SES"')

    def test_material_income_conflict_requires_resolution_without_income_substitution(self):
        self.publish()
        app, proof = self.applicant('SES-CONFLICT')
        with self.assertRaisesMessage(ValidationError, 'discrepancies'):
            self.accept(app, proof, income_monthly=['100000'] * 3, income_consistency='unresolved')
        with self.assertRaisesMessage(ValidationError, 'resolved'):
            self.accept(app, proof, income_monthly=['100000'] * 3, income_consistency='resolved')
        accepted = self.accept(app, proof, income_monthly=['100000'] * 3, income_consistency='resolved',
            income_resolution='SYNTHETIC dates and circumstances reviewed; current accepted income is PHP 100,000.')
        self.assertEqual(accepted.inputs['SES']['value'], '100000')

    def test_missing_invalid_evidence_and_input_domains_remain_blockers(self):
        self.publish()
        app, proof = self.applicant('SES-BLOCKERS')
        with self.assertRaisesMessage(ValidationError, 'all four'):
            self.generate()
        for changed in ({'income_monthly': ['', '', '']}, {'income_monthly': ['-1', '0', '0']},
                        {'income_monthly': ['NaN', '0', '0']}, {'history_complete': False},
                        {'household_members': 0}, {'household_members': 2.5}, {'employment': 'Unlisted'}):
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                self.accept(app, proof, **changed)
        with self.assertRaises(ValidationError):
            self.accept(app, proof, selections={code: [] for code in CODES})
        self.accept(app, proof)
        with self.assertRaisesMessage(ValidationError, 'Constant-value'):
            self.generate()
        self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())

    def test_stale_inputs_full_pool_recalculation_and_immutable_versions(self):
        a, ar, b, br = self.pool()
        old = self.generate()
        retained = deepcopy(old.payload())
        token = evidence.review_token(a, self.configuration)
        self.accept(a, ar, low=True, income_monthly=['6000'] * 3)
        with self.assertRaises(ValidationError):
            evidence.record(a.pk, user=self.user, expected=token, findings={}, selections={},
                state='NEEDS_REVIEW', reason='SYNTHETIC stale submission', confirmed=True)
        new = self.generate()
        self.assertEqual(new.previous_id, old.pk)
        old.refresh_from_db()
        old.clean()
        self.assertEqual(old.payload(), retained)
        evidence.record(a.pk, user=self.user, expected=evidence.review_token(a, self.configuration),
            findings={}, selections={}, state='DISPUTED', reason='SYNTHETIC evidence dispute', confirmed=True)
        with self.assertRaises(ValidationError):
            self.generate()

    def test_capacity_ties_hold_or_require_the_approved_human_explanation(self):
        self.content['choices']['tie_rule']['value'] = 'reasoned_human'
        self.publish()
        a, ar = self.applicant('SES-TIE-A')
        b, br = self.applicant('SES-TIE-B')
        c, cr = self.applicant('SES-TIE-C', prior=True)
        self.accept(a, ar, low=True)
        self.accept(b, br, low=True)
        self.accept(c, cr)
        run = self.generate()
        self.assertTrue(run.calculations[str(a.pk)]['comparison']['capacity_boundary_tie'])
        with self.assertRaisesMessage(ValidationError, 'tie_reason'):
            self.choose(run, a)
        self.choose(run, a, tie_reason='SYNTHETIC reviewed capacity-boundary decision under the assigned procedure')
        with self.assertRaisesMessage(ValidationError, 'slots'):
            self.choose(run, b, tie_reason='SYNTHETIC attempted excess selection')

    def test_unresolved_inventory_changed_evidence_and_cutoff_coverage_block_current_use(self):
        from documents.services import verify_document
        a, ar, b, br = self.pool()
        run = self.generate()
        source = deepcopy(DatasetInputReview.objects.filter(application=b).first().source)
        findings = DatasetInputReview.objects.filter(application=b).first().findings
        source['pa']['successful'][0]['recorded_at'] = (self.cutoff + timedelta(seconds=1)).isoformat()
        self.assertEqual(evidence.derive_inputs(findings, self.configuration, source)['PA']['value'], '0')
        verify_document(ar.document_id, user=self.user, member_version=a.member.version,
            verified=False, expires_on=None, reason='SYNTHETIC changed evidence review')
        with self.assertRaises(ValidationError):
            self.generate()
        run.refresh_from_db()
        run.clean()

    def test_concurrent_weight_drafts_share_the_existing_stale_edit_fence(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections, connections
        expected = vault.token()
        user_id = self.user.pk
        def save(index):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=user_id)
                try:
                    vault.record_ses_weights(user=user, expected=expected, proposal=proposal(), status='DRAFT',
                        reason=f'SYNTHETIC concurrent draft {index}')
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(save, (1, 2)))
        self.assertCountEqual(outcomes, ['saved', 'stale'])

    def test_private_breakdown_exports_and_filters_keep_all_four_pool_bounds(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        page = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]),
            {'run': run.pk, 'applicant': str(a.pk), 'page': 99, 'q': 'not-a-pool-filter'})
        self.assertEqual(page.status_code, 200)
        self.assertEqual([row['code'] for row in page.context['criteria']], list(CODES))
        self.assertEqual(page.context['selected']['legacy_traces'], [])
        self.assertEqual(page.context['pool_size'], 2)
        url = reverse('ewaf:operational_export', args=[self.program.pk, run.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['criteria'], list(CODES))
        self.assertEqual(response.json()['method'], methods.SES)
        self.assertEqual(response.json()['calculations'], run.calculations)
        self.assertIn('no-store', response['Cache-Control'])
        from membership.tests import grant
        limited = get_user_model().objects.create_user('SES-PRIVATE-EXPORT-DENIED', is_staff=True)
        grant(limited, 'accounts.access_dashboard')
        self.client.force_login(limited)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_policy_http_draft_approval_and_ses_fields(self):
        url = reverse('ewaf:dataset_policies') + '?method=' + methods.SES
        data = {'calculation_method': methods.SES, 'expected': policies.token(),
                'weight': self.weights.pk, 'reason': 'SYNTHETIC HTTP policy draft',
                'shared_cutoff': 'application_close'}
        for key, item in self.content['choices'].items():
            data[key], data['specified_' + key] = item['value'], 'on'
        page = self.client.get(url)
        self.assertContains(page, 'income-based proxy')
        self.assertNotContains(page, 'name="si_rubric"')
        self.assertNotContains(page, 'name="evidence_HI"')
        self.assertEqual(self.client.post(url, data).status_code, 302)
        draft = SharedDatasetPolicy.objects.first()
        review_url = reverse('ewaf:dataset_policy_review', args=[draft.pk])
        self.assertEqual(self.client.post(review_url, {'expected': draft.digest, 'group_A': 'on', 'group_B': 'on',
            'group_C': 'on', 'reason': 'SYNTHETIC HTTP policy approval'}).status_code, 302)
        self.assertEqual(SharedDatasetPolicy.objects.first().method, methods.SES)

    def test_unauthorized_audit_failure_and_stale_weight_approval_are_controlled(self):
        from membership.tests import grant
        viewer = get_user_model().objects.create_user('SES-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operational.VIEW)
        args = {'expected': vault.token(), 'proposal': proposal(), 'reason': 'SYNTHETIC authority test', 'status': 'DRAFT'}
        with self.assertRaises(PermissionDenied):
            vault.record_ses_weights(user=viewer, **args)
        count, audits = VaultRevision.objects.count(), LogEntry.objects.count()
        with patch.object(LogEntry.objects, 'create', side_effect=ValidationError('SYNTHETIC audit failure')):
            with self.assertRaises(ValidationError):
                vault.record_ses_weights(user=self.user, **args)
        self.assertEqual((VaultRevision.objects.count(), LogEntry.objects.count()), (count, audits))
        vault.record_ses_weights(user=self.user, **args)
        with self.assertRaisesMessage(ValidationError, 'changed'):
            vault.record_ses_weights(user=self.user, **args)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class SesFirstSetupTests(TransactionTestCase):
    setUp = dataset_tests.DatasetPolicyTests.setUp

    def test_initial_http_setup_is_blank_and_cannot_approve_without_a_saved_ses_draft(self):
        url = reverse('ewaf:vault') + '?method=' + methods.SES
        page = self.client.get(url)
        self.assertTrue(page.context['ses_setup'])
        self.assertIsNone(page.context['weight_state'])
        self.assertContains(page, 'no supplied defaults')
        data = {'calculation_method': methods.SES, 'expected': vault.token(),
            'reason': 'SYNTHETIC explicitly chosen starting weights', **dict(zip(CODES, ('40', '30', '20', '10')))}
        self.assertContains(self.client.post(url, data | {'action': 'LOCKED'}), 'unapproved weight draft')
        self.assertIsNone(vault.latest_for(methods.SES))
        self.assertEqual(self.client.post(url, data | {'action': 'DRAFT'}).status_code, 302)
        draft = vault.latest_for(methods.SES)
        self.assertEqual(draft.status, 'DRAFT')
        self.assertIsNone(vault.active(methods.SES))
        self.assertEqual(self.client.get(url).context['weight_state']['proposal'], proposal(units=(4000, 3000, 2000, 1000)))
