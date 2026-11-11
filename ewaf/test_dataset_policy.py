"""Isolated synthetic policy adoption and accepted-evidence integration tests."""
from copy import deepcopy
from datetime import timedelta
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TransactionTestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
from documents.services import verify_document
from members.tests import create_member
from membership.tests import pdf, grant
from membership.services import record_event
from programs.tests import program_data, create_program
from programs.testsupport import application_fixture
from programs.services import save_program, change_publication
from programs.models import Program, ProgramLog
from assistance.tests import seed_statuses, review_data, decision_data, release_data
from assistance.services import review_eligibility, decide_assistance, record_release
from scripts.durable_test_runner import require_disposable
from . import vault_services as vault, operational_services as operational
from .vault_policy import source_policy
from .vault_models import VaultRevision
from .household_criteria import PAIRS
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
from .revised import contracts, live_services as service, live_evidence as evidence, live_math
from .revised.live_models import SharedDatasetPolicy as Policy, DatasetInputReview
from .revised.engine import METHOD


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DatasetPolicyTests(TransactionTestCase):
    def setUp(self):
        require_disposable()
        seed_statuses()
        self.user = get_user_model().objects.create_superuser('SYNTHETIC-DATASET-ADMIN', password='synthetic-only')
        self.base = timezone.now() - timedelta(days=10)
        self.doc_type = DocumentType.objects.create(name='SYNTHETIC documented assessment and history coverage')
        self.requirement = MembershipDocumentRequirement.objects.create(document_type=self.doc_type)
        with patch('django.utils.timezone.now', return_value=self.base):
            self.weights = vault.record(user=self.user, expected=vault.token(), proposed=source_policy(),
                judgments=dict.fromkeys(PAIRS, '1'), status='LOCKED', reason='ISOLATED SYNTHETIC equal-weight fixture only', attested=True)
            self.program = save_program(user=self.user, data=program_data(ewaf_applicable=True,
                benefit='Synthetic benefit', slots=1, selection_method='Synthetic EWAF and separate human selection',
                registration_opens_at=self.base + timedelta(hours=1), registration_closes_at=self.base + timedelta(days=1)))
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='authorize_policy', notes='ISOLATED SYNTHETIC program authorization')
        self.program.refresh_from_db()
        from programs.test_approved_terms import TermsHelpers
        terms = TermsHelpers()
        terms.program, terms.officer = self.program, self.user
        terms.reconcile()
        self.cutoff = self.program.registration_closes_at + timedelta(hours=1)
        self.content = contracts.initial_content()
        for key, (_, _, kind) in contracts.SPECS.items():
            if isinstance(kind, dict):
                value = next(iter(kind))
            elif kind == 'documents':
                value = [self.doc_type.pk]
            elif kind == 'integer':
                value = 90 if key == 'evidence_max_age_days' else 12 if key == 'pa_months' else 3
            elif kind == 'datetime':
                value = (self.base - timedelta(days=1) if key == 'effective_from' else timezone.now() + timedelta(days=20)).isoformat()
            else:
                value = 'ISOLATED SYNTHETIC explicit ' + key + '; not an Association operating rule.'
            self.content['choices'][key] = {'value': value, 'specified': True}
        self.client.force_login(self.user)

    def draft(self, content=None):
        return service.save_draft(user=self.user, expected=service.token(), content=content or self.content,
            weight_id=self.weights.pk, reason='ISOLATED SYNTHETIC draft review')

    def approve(self, draft=None):
        row = draft or self.draft()
        return service.approve(row.pk, user=self.user, expected=row.digest, reviewed_groups=['A', 'B', 'C'],
            reason='ISOLATED SYNTHETIC approval in disposable tests only')

    def bind(self, policy=None):
        return service.bind(self.program.pk, user=self.user, expected=operational.configuration_token(self.program),
            policy_id=(policy or self.approve()).pk, cutoff=self.cutoff, reason='ISOLATED SYNTHETIC explicit program binding')

    def publish(self):
        self.configuration = self.bind()
        with patch('django.utils.timezone.now', return_value=self.base):
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='published', notes='ISOLATED SYNTHETIC publication')
        self.program.refresh_from_db()
        return self.configuration

    def applicant(self, code, *, prior=False):
        with patch('django.utils.timezone.now', return_value=self.base + timedelta(hours=2)):
            member = create_member(code)
            intake = member.application
            intake.prpwd_verified_by = intake.decided_by = self.user
            intake.save()
            record_event(intake, 'prpwd_verified', 'Synthetic manual verification', user=self.user)
            record_event(intake, 'approved', 'Synthetic approved intake', user=self.user)
            if prior:
                old = create_program(registration_opens_at=self.base - timedelta(days=2),
                    registration_closes_at=self.base - timedelta(days=1))
                old_app = application_fixture(old, member)
                review_eligibility(old_app.pk, user=self.user, data=review_data(old_app))
                decide_assistance(old_app.pk, user=self.user, data=decision_data(old_app))
                record_release(old_app.pk, user=self.user, data=release_data(old_app))
            application = application_fixture(self.program, member)
            application.source_snapshot = {'member_id': member.pk, 'member_version': member.version,
                'program_version': self.program.version, 'membership_verified_at': timezone.now().isoformat(),
                'policy_authorized_at': self.program.policy_authorized_at.isoformat()}
            application.save(update_fields=['source_snapshot'])
        review_eligibility(application.pk, user=self.user, data=review_data(application))
        application.refresh_from_db()
        document = MembershipApplicationDocument.objects.create(application=intake, requirement=self.requirement,
            label='Synthetic accepted evidence', file=pdf(), content_type='application/pdf', size=50)
        review = verify_document(document.pk, user=self.user, member_version=member.version,
            verified=True, expires_on=None, reason='Synthetic verification of private evidence')
        return application, review

    def accept(self, application, document_review, *, low=False, **changes):
        findings = {**evidence.periods(self.configuration), 'income_monthly': ['5000' if low else '20000'] * 3,
            'si_domains': {'food': 'critical' if low else 'none', 'housing': 'none', 'care': 'none'},
            'employment': 'Unemployed' if low else 'Full-Time Worker', 'household_members': 2 if low else 6,
            'history_complete': True, 'assessment_finding': 'Synthetic accepted findings with verified evidence'}
        findings.update(changes)
        return evidence.record(application.pk, user=self.user, expected=evidence.review_token(application, self.configuration),
            findings=findings, selections={code: [document_review.pk] for code in ('HI', 'SI', 'ES', 'PA', 'HM')},
            state='ACCEPTED', reason='Synthetic reviewed assessment', confirmed=True)

    def pool(self):
        self.publish()
        a, ar = self.applicant('SYNTHETIC-DATASET-A')
        b, br = self.applicant('SYNTHETIC-DATASET-B', prior=True)
        self.accept(a, ar, low=True)
        self.accept(b, br)
        return a, ar, b, br

    def generate(self):
        return operational.generate(self.program.pk, user=self.user,
            expected=operational.context(self.program.pk, user=self.user), request_key=uuid4(), reason='Synthetic complete-pool calculation')

    def choose(self, run, app, outcome='SELECTED', **changes):
        return operational.record_decision(self.program.pk, **dict(user=self.user, run_id=run.pk,
            application_id=app.pk, expected_revision=0, outcome=outcome,
            reason='ISOLATED SYNTHETIC human decision within capacity', **changes))

    def test_draft_storage_explicit_approval_and_immutable_history(self):
        draft = self.draft()
        self.assertEqual(draft.status, 'DRAFT')
        self.assertFalse(Policy.objects.filter(status='APPROVED').exists())
        approved = self.approve(draft)
        approved.clean()
        self.assertEqual(approved.previous_id, draft.pk)
        self.assertEqual(approved.weight_snapshot['weights'], self.weights.validation['weights'])
        retained = approved.payload()
        changed = deepcopy(self.content)
        changed['choices']['income_months']['value'] = 4
        self.draft(changed)
        approved.refresh_from_db()
        self.assertEqual(approved.payload(), retained)
        with self.assertRaises(ValidationError):
            Policy.objects.filter(pk=draft.pk).update(status='APPROVED')
        with self.assertRaises(ValidationError):
            approved.save()

    def test_incomplete_policy_blocks_binding_and_scoring_but_approved_weights_allow_publication(self):
        draft = self.draft(contracts.initial_content())
        with self.assertRaisesMessage(ValidationError, 'unspecified'):
            self.approve(draft)
        with self.assertRaisesMessage(ValidationError, 'explicitly approved'):
            self.bind(draft)
        before = self.program.version
        change_publication(self.program.pk, user=self.user, version=before, action='published', notes='Synthetic approved-weights publication')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'published')
        self.assertEqual(self.program.version, before + 1)
        with self.assertRaises(ValidationError):
            self.generate()

    def test_published_weights_only_intake_gets_first_policy_without_changing_weights_or_schedule(self):
        from .intake_policy import require_configuration
        schedule = self.program.registration_opens_at, self.program.registration_closes_at
        change_publication(self.program.pk, user=self.user, version=self.program.version,
            action='published', notes='Synthetic weights-only intake')
        self.program.refresh_from_db()
        old = require_configuration(self.program)
        app, proof = self.applicant('SYNTHETIC-PREPOLICY-APPLICANT')
        bound = self.bind()
        self.assertEqual(bound.previous_id, old.pk)
        self.assertEqual(bound.dataset_policy.weight_configuration_id, old.vault_revision_id)
        self.program.refresh_from_db()
        self.assertEqual((self.program.registration_opens_at,self.program.registration_closes_at),schedule)
        self.assertEqual(self.program.applications.count(),1)
        self.configuration = bound
        self.accept(app,proof)
        with self.assertRaisesMessage(ValidationError,'Existing scored or historical'):
            self.bind()

    def test_preopening_policy_readiness_does_not_require_dataset_or_change_schedule(self):
        from programs.application_workflow import publication_configuration_problem
        schedule = self.program.registration_opens_at, self.program.registration_closes_at
        configuration = self.bind()
        self.assertEqual(publication_configuration_problem(self.program), '')
        self.assertFalse(self.program.applications.exists())
        with patch('django.utils.timezone.now', return_value=self.base):
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='published', notes='Synthetic preopening publication')
            self.program.refresh_from_db()
            self.assertFalse(self.program.registration_available)
        self.assertEqual((self.program.registration_opens_at, self.program.registration_closes_at), schedule)
        with self.assertRaises(ValidationError):
            self.generate()
        self.assertEqual(configuration.dataset_policy.method, METHOD)

    def test_later_shared_approvals_do_not_rebind_program(self):
        bound = self.bind()
        retained = bound.payload()
        new = deepcopy(self.content)
        new['choices']['pa_months']['value'] = 6
        later = self.approve(self.draft(new))
        current = operational.latest_configuration(self.program)
        self.assertEqual(current.payload(), retained)
        self.assertNotEqual(current.dataset_policy_id, later.pk)

    def test_document_example_from_frozen_pool_without_substituting_live_vector(self):
        from .revised.fixtures import example_pool
        pool = example_pool().data
        config = SimpleNamespace(digest='SYNTHETIC-DOCUMENT-CONFIG', assessment_cutoff=self.cutoff,
            dataset_policy=SimpleNamespace(digest='SYNTHETIC-POLICY'), program=SimpleNamespace(slots=2),
            source={'terms':{'program':{'slots':2}}},
            validation={'weights': dict(zip(('HI','SI','ES','PA','HM'), ('0.3421','0.2360','0.1774','0.1223','0.1222'))), 'weight_digest':'SYNTHETIC-DOCUMENT-VECTOR'})
        result = live_math.calculations({'engine':METHOD, 'configuration_digest':config.digest,
            'eligible':{row['id']:{'inputs':row['inputs']} for row in pool['applicants']}}, config)
        self.assertEqual([Fraction(result[key]['score_exact']) * 100 for key in ('A','B','C')],
                         [Fraction(839,10), Fraction(7537,120), Fraction(611,50)])
        self.assertEqual(self.weights.validation['weights']['HI'], '0.2')

    def test_accepted_evidence_produces_official_run_with_no_automatic_selection(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        run.clean()
        self.assertEqual(run.configuration.dataset_policy_id, self.configuration.dataset_policy_id)
        self.assertTrue(all(row['engine']==METHOD for row in run.calculations.values()))
        self.assertFalse(OperationalDecision.objects.exists())
        self.assertEqual(DatasetInputReview.objects.count(), 2)

    def test_review_note_or_membership_approval_does_not_supply_accepted_inputs(self):
        self.publish()
        app, review = self.applicant('SYNTHETIC-MISSING-ACCEPTANCE')
        with self.assertRaisesMessage(ValidationError, 'Accept all five'):
            self.generate()
        with self.assertRaisesMessage(ValidationError, 'Unlisted employment'):
            self.accept(app, review, employment='Self-employed')
        with self.assertRaisesMessage(ValidationError, 'unknown is not zero'):
            self.accept(app, review, history_complete=False)

    def test_single_applicant_and_constant_columns_stop_under_explicit_test_policy(self):
        self.publish()
        app, review = self.applicant('SYNTHETIC-CONSTANT')
        self.accept(app, review)
        with self.assertRaisesMessage(ValidationError, 'Constant-value'):
            self.generate()
        self.assertFalse(OperationalRun.objects.exists())

    def test_stale_evidence_and_disputed_review_invalidate_current_use_preserving_history(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        retained = run.payload()
        evidence.record(a.pk, user=self.user, expected=evidence.review_token(a,self.configuration), findings={}, selections={},
            state='DISPUTED', reason='Synthetic disputed finding', confirmed=True)
        with self.assertRaises(ValidationError):
            self.generate()
        run.refresh_from_db()
        run.clean()
        self.assertEqual(run.payload(),retained)

    def test_no_weight_reapproval_and_approval_audit_failure_rolls_back(self):
        before = VaultRevision.objects.count()
        draft = self.draft()
        with patch('ewaf.vault_services.approve', side_effect=AssertionError('Never reapprove weights')):
            with patch.object(LogEntry.objects,'create',side_effect=RuntimeError('Synthetic audit failure')):
                with self.assertRaises(RuntimeError):
                    self.approve(draft)
        self.assertEqual(Policy.objects.count(),1)
        self.assertEqual(VaultRevision.objects.count(),before)

    def test_unauthorized_direct_approval_binding_and_http_post_are_denied(self):
        viewer = get_user_model().objects.create_user('SYNTHETIC-POLICY-VIEWER',is_staff=True)
        grant(viewer,'accounts.access_dashboard',*operational.VIEW)
        draft = self.draft()
        with self.assertRaises(PermissionDenied):
            service.approve(draft.pk,user=viewer,expected=draft.digest,reviewed_groups=['A','B','C'],reason='Unauthorized')
        self.client.force_login(viewer)
        response = self.client.post(reverse('ewaf:dataset_policy_review',args=[draft.pk]),
            {'expected':draft.digest,'group_A':'on','group_B':'on','group_C':'on','reason':'Unauthorized'})
        self.assertEqual(response.status_code,403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(reverse('ewaf:dataset_policy_review',args=[draft.pk]),{}).status_code,403)

    def test_disabled_activation_and_stale_draft_requests_fail(self):
        old = service.token()
        self.draft()
        with self.assertRaisesMessage(ValidationError,'changed'):
            service.save_draft(user=self.user,expected=old,content=self.content,weight_id=self.weights.pk,reason='Stale')
        with override_settings(EWAF_DATASET_POLICY_ENABLED=False):
            with self.assertRaisesMessage(ValidationError,'not enabled'):
                self.approve()

    def test_review_interface_lists_exact_choices_provenance_and_blockers(self):
        row=self.draft(contracts.initial_content())
        response=self.client.get(reverse('ewaf:dataset_policy_review',args=[row.pk]))
        self.assertEqual(response.status_code,200)
        for value in ('Group A','Group B','Group C','SI_RUBRIC_AUTHORITY','CONSTANT_COLUMNS','Income inclusions',
                      'Approval blocked','Still unspecified','4Ps','0.2','Full-Time Worker=1'):
            self.assertContains(response,value)
        self.assertFalse(Policy.objects.filter(status='APPROVED').exists())

    def test_selection_capacity_private_publication_projection_and_actual_release(self):
        from assistance.models import AssistanceRelease
        a, ar, b, br = self.pool()
        run = self.generate()
        with self.assertRaises(ValidationError):
            record_release(a.pk, user=self.user, data=release_data(a))
        with self.assertRaisesMessage(ValidationError, 'Finish every'):
            operational.publication_snapshot(self.program)
        self.choose(run, a)
        with self.assertRaisesMessage(ValidationError, 'slots'):
            self.choose(run, b)
        self.choose(run, b, 'NOT_SELECTED')
        payload, stamp = operational.publication_snapshot(self.program)
        self.assertEqual(len(payload['rows']), 1)
        self.assertFalse(any(key in payload['rows'][0] for key in ('score', 'rank', 'inputs', 'traces')))
        self.assertNotEqual(payload['rows'][0]['name'], a.member.full_name)
        record_release(a.pk, user=self.user, data=release_data(a))
        self.assertEqual(AssistanceRelease.objects.successful().filter(application=a).count(), 1)
        run.refresh_from_db()
        run.clean()
        with self.assertRaises(ValidationError):
            record_release(b.pk, user=self.user, data=release_data(b))

    def test_explicit_test_policy_holds_exact_capacity_tie_without_hidden_winner(self):
        self.publish()
        a, ar = self.applicant('SYNTHETIC-TIED-A')
        b, br = self.applicant('SYNTHETIC-TIED-B')
        c, cr = self.applicant('SYNTHETIC-TIED-C', prior=True)
        self.accept(a, ar, low=True)
        self.accept(b, br, low=True)
        self.accept(c, cr)
        run = self.generate()
        self.assertEqual([row['comparison']['business_rank'] for row in operational.ordered(run)], [1, 1, 3])
        self.assertTrue(run.calculations[str(a.pk)]['comparison']['capacity_boundary_tie'])
        with self.assertRaisesMessage(ValidationError, 'holds exact ties'):
            self.choose(run, a, tie_reason='Cannot bypass the explicit test hold rule')
        self.choose(run, a, 'DEFERRED')
        self.assertFalse(OperationalDecision.objects.filter(outcome='SELECTED').exists())

    def test_human_tie_option_requires_reason_when_explicitly_adopted_in_test_policy(self):
        self.content['choices']['tie_rule']['value'] = 'reasoned_human'
        self.publish()
        a, ar = self.applicant('SYNTHETIC-HUMAN-TIE-A')
        b, br = self.applicant('SYNTHETIC-HUMAN-TIE-B')
        c, cr = self.applicant('SYNTHETIC-HUMAN-TIE-C', prior=True)
        for app, proof, low in ((a, ar, True), (b, br, True), (c, cr, False)):
            self.accept(app, proof, low=low)
        run = self.generate()
        with self.assertRaisesMessage(ValidationError, 'tie_reason'):
            self.choose(run, a)
        self.choose(run, a, tie_reason='ISOLATED SYNTHETIC authorized tie-procedure outcome')
        with self.assertRaisesMessage(ValidationError, 'slots'):
            self.choose(run, b, tie_reason='ISOLATED SYNTHETIC cannot exceed capacity')

    def test_evidence_ownership_reverification_and_expiration_are_enforced(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        with self.assertRaises(ValidationError):
            self.accept(a, br, low=True)
        verify_document(ar.document_id, user=self.user, member_version=a.member.version,
            verified=False, expires_on=None, reason='ISOLATED SYNTHETIC evidence rejected')
        with self.assertRaises(ValidationError):
            self.choose(run, a)
        with self.assertRaises(ValidationError):
            self.generate()
        run.refresh_from_db()
        run.clean()
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(days=91)):
            with self.assertRaisesMessage(ValidationError, 'stale'):
                evidence.supporting(b, self.configuration, {code:[br.pk] for code in contracts.CRITERIA})

    def test_acceptance_calculation_and_binding_audit_failures_roll_back(self):
        self.publish()
        a, ar = self.applicant('SYNTHETIC-ROLLBACK-A')
        b, br = self.applicant('SYNTHETIC-ROLLBACK-B', prior=True)
        before = ProgramLog.objects.count()
        with patch.object(ProgramLog.objects, 'create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.accept(a, ar, low=True)
        self.assertFalse(DatasetInputReview.objects.exists())
        self.assertEqual(ProgramLog.objects.count(), before)
        self.accept(a, ar, low=True)
        self.accept(b, br)
        with patch.object(ProgramLog.objects, 'create', side_effect=RuntimeError('Synthetic run audit failure')):
            with self.assertRaises(RuntimeError):
                self.generate()
        self.assertFalse(OperationalRun.objects.exists())

    def test_feature_flags_cutoff_approved_scope_and_unsupported_rules_are_not_bypassed(self):
        bad = deepcopy(self.content)
        bad['choices']['constant_rule']['value'] = 'invent_midpoint'
        with self.assertRaisesMessage(ValidationError, 'unsupported'):
            self.approve(self.draft(bad))
        self.pool()
        with override_settings(EWAF_DATASET_SCORING_ENABLED=False):
            with self.assertRaisesMessage(ValidationError, 'not enabled'):
                self.generate()
        with patch('django.utils.timezone.now', return_value=self.cutoff - timedelta(minutes=1)):
            with self.assertRaisesMessage(ValidationError, 'cutoff'):
                self.generate()

    def test_private_ui_renders_review_binding_inputs_and_results(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        for name, args in [('dataset_policies', []), ('dataset_policy_review', [self.configuration.dataset_policy_id]),
                           ('dataset_binding', [self.program.pk]), ('dataset_inputs', [a.pk]),
                           ('operational_workspace', [self.program.pk]), ('operational_run', [self.program.pk,run.pk])]:
            response = self.client.get(reverse('ewaf:' + name, args=args), follow=True)
            self.assertEqual(response.status_code, 200, name)
            self.assertIn('no-store', response['Cache-Control'])

    def test_draft_concurrency_and_authority_revocation_do_not_create_approval(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        expected, barrier = service.token(), Barrier(2)
        def save():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                service.save_draft(user=self.user, expected=expected, content=self.content,
                    weight_id=self.weights.pk, reason='ISOLATED SYNTHETIC concurrent draft')
                return 'saved'
            except ValidationError:
                return 'stale'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: save(), range(2))), ['saved', 'stale'])
        draft = Policy.objects.first()
        real_store = service._store
        def revoke(row):
            result = real_store(row)
            get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
            return result
        with patch.object(service, '_store', side_effect=revoke):
            with self.assertRaises(PermissionDenied):
                self.approve(draft)
        self.assertEqual(Policy.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_retained_nondefault_weight_precision_and_slider_provenance_are_not_replaced(self):
        # Deliberately synthetic source record produced through the existing slider
        # service. Integration itself neither projects nor reapproves this vector.
        source = vault.approve(user=self.user, expected=vault.token(), proposal={
            'order': list(contracts.CRITERIA), 'weights': dict(zip(contracts.CRITERIA, (3045,2328,1790,1611,1226)))})
        self.weights = source
        original, audit = source.payload(), source.audit_entry_id
        # The unchanged Vault clean() replays its original provenance for integrity;
        # policy integration must not write a replacement or new weight approval.
        with patch('ewaf.vault_services.record', side_effect=AssertionError('Do not reapprove weights')):
            approved = self.approve()
            configuration = self.bind(approved)
        self.assertEqual(configuration.validation['weights'], source.validation['weights'])
        self.assertEqual(configuration.validation['weights']['HI'], '0.30653679653679653679653679653679653679653679653678')
        self.assertEqual(Fraction(approved.weight_snapshot['residue_from_one']), -Fraction(1,10**50))
        self.assertEqual(approved.weight_snapshot['origin']['judgment_origin'], 'generated_from_slider_ratios_not_independently_elicited')
        source.refresh_from_db()
        self.assertEqual((source.payload(),source.audit_entry_id), (original,audit))
        from .test_vault import proposal
        historical = vault.record(user=self.user, expected=vault.token(), proposed=proposal(self.doc_type.pk),
            judgments=dict.fromkeys(PAIRS,'1'), status='LOCKED', reason='ISOLATED SYNTHETIC historical fixed SI encoding', attested=True)
        with self.assertRaises(ValidationError):
            contracts.weight_snapshot(historical)

    def test_reference_definitions_and_frozen_terms_cannot_change_retained_results(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        original = deepcopy(run.calculations)
        # In-memory objects only: historical replay uses bound terms, not current
        # program dates/capacity or whichever shared draft was most recently saved.
        run.configuration.program.slots = 100
        run.configuration.program.registration_closes_at = timezone.now()
        self.assertEqual(live_math.calculations(run.snapshot,run.configuration), original)
        accepted = DatasetInputReview.objects.filter(application=a).first()
        accepted.configuration.program.registration_closes_at = timezone.now()
        accepted.clean()
        DocumentType.objects.filter(pk=self.doc_type.pk).update(description='Synthetic changed evidence definition')
        with self.assertRaisesMessage(ValidationError, 'definitions changed'):
            operational.latest_configuration(self.program)
        run.refresh_from_db()
        run.clean()

    def test_authorization_is_required_for_binding_and_all_three_review_groups(self):
        draft = self.draft()
        with self.assertRaisesMessage(ValidationError,'each of A, B and C'):
            service.approve(draft.pk,user=self.user,expected=draft.digest,reviewed_groups=['A','C'],reason='Synthetic missing SI adoption')
        approved = self.approve(draft)
        viewer = get_user_model().objects.create_user('SYNTHETIC-BINDING-VIEWER',is_staff=True)
        grant(viewer,'accounts.access_dashboard',*operational.VIEW)
        with self.assertRaises(PermissionDenied):
            service.bind(self.program.pk,user=viewer,expected=operational.configuration_token(self.program),
                policy_id=approved.pk,cutoff=self.cutoff,reason='Synthetic unauthorized binding')
        before = OperationalConfiguration.objects.count()
        with patch.object(ProgramLog.objects,'create',side_effect=RuntimeError('Synthetic binding audit failure')):
            with self.assertRaises(RuntimeError):
                self.bind(approved)
        self.assertEqual(OperationalConfiguration.objects.count(),before)

    def test_input_domains_recording_cutoff_and_month_end_rule_are_explicit(self):
        from datetime import date
        for key in ('input_domain', 'pa_knowledge'):
            incomplete = deepcopy(self.content)
            incomplete['choices'][key] = {'value':'', 'specified':False}
            with self.assertRaisesMessage(ValidationError, 'unspecified'):
                self.approve(self.draft(incomplete))
        a, ar, b, br = self.pool()
        accepted = DatasetInputReview.objects.filter(application=b).first()
        self.assertEqual(accepted.inputs['PA']['value'], '1')
        changed = deepcopy(accepted.source)
        changed['pa']['successful'][0]['recorded_at'] = (self.cutoff + timedelta(seconds=1)).isoformat()
        self.assertEqual(evidence.derive_inputs(accepted.findings,self.configuration,changed)['PA']['value'],'0')
        self.assertEqual(evidence.shift_months(date(2024,2,29),12),date(2023,2,28))
        with self.assertRaises(ValidationError):
            self.accept(a,ar,low=True,income_monthly=['-1','0','0'])

    def test_saved_score_breakdown_displays_exact_dataset_traces(self):
        a, ar, b, br = self.pool()
        run = self.generate()
        original = deepcopy(run.payload())
        response = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]),
                                   {'run': run.pk, 'applicant': str(a.pk)})
        self.assertEqual(response.status_code, 200)
        selected = response.context['selected']
        self.assertEqual(selected['score'], run.calculations[str(a.pk)]['score_display'])
        self.assertEqual([row['code'] for row in selected['traces']], ['HI', 'SI', 'ES', 'PA', 'HM'])
        self.assertEqual([row['code'] for row in selected['display_traces']], ['HI', 'SI', 'ES', 'PA', 'HM'])
        self.assertEqual([row['code'] for row in response.context['criteria']], ['HI', 'SI', 'ES', 'PA', 'HM'])
        self.assertTrue(all(row['included'] for row in selected['display_traces']))
        self.assertEqual(selected['legacy_traces'], [])
        self.assertNotContains(response, 'Not included in this calculation')
        self.assertNotContains(response, 'Historical criteria included in this saved score')
        for presented, stored in zip(selected['traces'], run.calculations[str(a.pk)]['traces']):
            self.assertEqual(presented['normalized'], stored['normalized']['exact'])
            self.assertEqual(presented['contribution'], stored['contribution']['exact'])
            self.assertEqual(presented['lower'], stored['minimum']['exact'])
            self.assertEqual(presented['upper'], stored['maximum']['exact'])
        self.assertContains(response, 'How applicants compare')
        run.refresh_from_db()
        self.assertEqual(run.payload(), original)
