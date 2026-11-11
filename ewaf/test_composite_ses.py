"""Exact composite SES fixtures and real, synthetic disposable-MySQL integration."""
from copy import deepcopy
from datetime import timedelta
from fractions import Fraction
from itertools import permutations
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError, PermissionDenied
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import dataset_methods as methods, test_ses_workflow as income_tests
from . import vault_services as vault, operational_services as operational
from .weight_input import project
from .revised import contracts, live_math, live_evidence as evidence, live_services as policies
from .revised.composite_ses import FORMULA, calculate
from .revised.live_models import DatasetInputReview, SharedDatasetPolicy
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision

CODES = methods.SES_CRITERIA


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class CompositeSesFirstSetupTests(TransactionTestCase):
    setUp = income_tests.SesFirstSetupTests.setUp

    def test_new_vault_opens_volume_editor_without_starting_percentage_form(self):
        url = reverse('ewaf:vault')
        retained = deepcopy(self.weights.payload())
        page = self.client.get(url)
        self.assertEqual(page.context['method'], methods.COMPOSITE)
        self.assertFalse(page.context['ses_setup'])
        self.assertIsNone(page.context['weight_state']['proposal'])
        self.assertEqual(page.context['weight_state']['criteria'], list(CODES))
        self.assertIsNone(page.context['weight_state']['approvableProposal'])
        self.assertContains(page, 'id="ewaf-configuration-form"')
        self.assertContains(page, 'js/ewaf-weights.js')
        self.assertNotContains(page, 'type="number"')
        self.assertNotContains(page, 'id="ses-weight-setup"')
        self.assertNotContains(page, 'Adjust with volume sliders')
        self.assertNotContains(page, 'aria-label="EWAF calculation method"')
        from django.contrib.admin.models import LogEntry
        from .vault_models import VaultRevision
        before = VaultRevision.objects.count(), LogEntry.objects.count()
        proposed = {'order': list(CODES), 'weights': dict(zip(CODES, (5000, 2500, 1250, 1250)))}
        submitted = {'calculation_method': methods.COMPOSITE, 'expected': vault.token(),
            'weight_method': 'slider-ratio-projection-v1', 'slider_proposal': json.dumps(proposed), 'reason': ''}
        blank = self.client.post(url, submitted | {'action': 'DRAFT', 'slider_proposal': ''})
        self.assertTrue(blank.context['form'].errors['slider_proposal'])
        self.assertIsNone(blank.context['weight_state']['proposal'])
        preview = self.client.post(url, submitted | {'action': 'PREVIEW_WEIGHTS'})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['method'], methods.COMPOSITE)
        self.assertEqual(len(preview.json()['rows']), 4)
        self.assertEqual(before, (VaultRevision.objects.count(), LogEntry.objects.count()))
        invalid = self.client.post(url, submitted | {'action': 'DRAFT'})
        self.assertTrue(invalid.context['form'].errors['reason'])
        self.assertEqual(invalid.context['weight_state']['proposal'], proposed)
        self.assertContains(invalid, 'id="ewaf-configuration-form"')
        submitted['reason'] = 'SYNTHETIC four weights chosen with sliders'
        self.assertContains(self.client.post(url, submitted | {'action': 'LOCKED'}), 'preview again')
        self.assertIsNone(vault.latest_for(methods.COMPOSITE))
        response = self.client.post(url, submitted | {'action': 'DRAFT'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['ses_setup'])
        state = response.context['weight_state']
        self.assertEqual(state['proposal'], {'order': list(CODES),
            'weights': dict(zip(CODES, (5000, 2500, 1250, 1250)))})
        self.assertEqual(state['approvableProposal'], state['proposal'])
        self.assertContains(response, 'id="ewaf-configuration-form"')
        self.assertContains(response, 'js/ewaf-weights.js')
        self.assertIsNone(vault.active(methods.COMPOSITE))
        self.weights.refresh_from_db()
        self.assertEqual(self.weights.payload(), retained)


    def test_unsaved_slider_setup_rejects_invalid_values_stale_requests_and_unauthorized_staff(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        from .vault_models import VaultRevision
        url = reverse('ewaf:vault')
        data = {'calculation_method': methods.COMPOSITE, 'expected': vault.token(), 'action': 'ADJUST_WEIGHTS',
            **dict(zip(CODES, ('50', '25', '15', '10')))}
        before = VaultRevision.objects.count()
        for change in ({'expected': 'stale'}, {'SES': '45'}, {'PA': ''},
                       dict(zip(CODES, ('80', '10', '5', '5')))):
            with self.subTest(change=change):
                page = self.client.post(url, data | change)
                self.assertEqual(page.status_code, 200)
                self.assertTrue(page.context['ses_setup'])
                self.assertTrue(page.context['form'].errors)
                self.assertIsNone(page.context['weight_state'])
                self.assertEqual(VaultRevision.objects.count(), before)
        viewer = get_user_model().objects.create_user('SYNTHETIC-SLIDER-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operational.VIEW)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(VaultRevision.objects.count(), before)


def proposal(order=CODES):
    return income_tests.proposal(order, (4000, 2000, 2000, 2000))


def fixture(rows, weights=None, policy=None):
    weights = weights or dict(zip(CODES, ('0.4', '0.2', '0.2', '0.2')))
    config = SimpleNamespace(digest='synthetic-composite',
        policy=policy or {'method': methods.COMPOSITE, 'ses_formula': deepcopy(FORMULA)},
        validation={'weights': weights, 'weight_digest': 'synthetic-weights'},
        source={'terms': {'program': {'slots': 1}}}, dataset_policy=SimpleNamespace(digest='synthetic-policy'),
        assessment_cutoff=timezone.now())
    eligible = {}
    for key, (income, p, employment, previous, household) in rows.items():
        eligible[key] = {'inputs': dict(zip(CODES, ({'value': str(income), 'household_four_ps': p},
            {'value': employment}, {'value': str(previous)}, {'value': str(household)})))}
    snapshot = {'engine': methods.COMPOSITE, 'configuration_digest': config.digest, 'eligible': eligible}
    return live_math.calculations(snapshot, config)


def endpoints(p=0):
    return {'minimum': (0, p, 'Unemployed', 0, 6), 'maximum': (100000, p, 'Full-Time Worker', 3, 2)}


def ses_trace(result, key):
    return next(item for item in result[key]['traces'] if item['criterion'] == 'SES')


class CompositeSesArithmeticTests(SimpleTestCase):
    def test_exact_required_income_table_from_pool_bounds_and_four_contributions(self):
        rows = endpoints()
        expected = {0: ('9/10', '1'), 10000: ('81/100', '9/10'),
                    50000: ('9/20', '1/2'), 100000: ('0', '0')}
        for income in expected:
            for p in (0, 1):
                rows[f'{income}-{p}'] = (income, p, 'Seasonal Worker', 1, 4)
        result = fixture(rows)
        for income, values in expected.items():
            for p in (0, 1):
                with self.subTest(income=income, participation=p):
                    trace = ses_trace(result, f'{income}-{p}')
                    value = Fraction(values[p])
                    self.assertEqual(Fraction(trace['normalized']['exact']), value)
                    self.assertEqual(Fraction(trace['minimum']['exact']), 0)
                    self.assertEqual(Fraction(trace['maximum']['exact']), 100000)
                    self.assertEqual(Fraction(trace['income_need']['exact']), Fraction(100000-income, 100000))
                    self.assertEqual(Fraction(trace['multiplier']['exact']), Fraction(9+p, 10))
                    self.assertEqual(Fraction(trace['contribution']['exact']), Fraction(2, 5) * value)
                    self.assertEqual([t['criterion'] for t in result[f'{income}-{p}']['traces']], list(CODES))

    def test_similar_income_order_reversal_and_exact_36_point_contribution(self):
        result = fixture(endpoints() | {
            'higher_yes': (20000, 1, 'Seasonal Worker', 1, 4),
            'lower_no': (15000, 0, 'Seasonal Worker', 1, 4),
            'nine_tenths': (10000, 1, 'Seasonal Worker', 1, 4)})
        yes, no = ses_trace(result, 'higher_yes'), ses_trace(result, 'lower_no')
        self.assertEqual(Fraction(yes['normalized']['exact']), Fraction(4, 5))
        self.assertEqual(Fraction(no['normalized']['exact']), Fraction(153, 200))
        self.assertGreater(Fraction(yes['contribution']['exact']), Fraction(no['contribution']['exact']))
        self.assertEqual(100 * Fraction(ses_trace(result, 'nine_tenths')['contribution']['exact']), 36)

    def test_participation_delta_depends_on_income_need_not_a_flat_bonus(self):
        for income_need in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(1)):
            yes, _ = calculate(income_need, 1)
            no, _ = calculate(income_need, 0)
            self.assertEqual(yes - no, income_need / 10)

    def test_constant_participation_is_valid_and_scores_are_not_stretched_to_100(self):
        for p, best in ((0, 96), (1, 100)):
            result = fixture(endpoints(p))
            self.assertEqual(100 * Fraction(result['minimum']['score_exact']), best)
            self.assertEqual(Fraction(ses_trace(result, 'minimum')['normalized']['exact']), Fraction(9+p, 10))
            self.assertEqual(Fraction(result['maximum']['score_exact']), 0)

    def test_income_bounds_are_derived_again_and_100000_is_not_a_permanent_cutoff(self):
        rows = endpoints(1)
        rows['new_maximum'] = (200000, 1, 'Part-Time Worker', 1, 4)
        result = fixture(rows)
        self.assertEqual(Fraction(ses_trace(result, 'maximum')['income_need']['exact']), Fraction(1, 2))
        self.assertEqual(Fraction(ses_trace(result, 'maximum')['normalized']['exact']), Fraction(1, 2))

    def test_unresolved_invalid_participation_constant_income_and_changed_formula_block(self):
        for p in (None, '', False, True, '0', '1', 2, -1):
            rows = endpoints(); rows['minimum'] = (0, p, 'Unemployed', 0, 6)
            with self.subTest(p=p), self.assertRaises(ValidationError):
                fixture(rows)
        with self.assertRaisesMessage(ValidationError, 'Constant-value'):
            fixture({'a': (100000, 0, 'Unemployed', 0, 6), 'b': (100000, 1, 'Full-Time Worker', 3, 2)})
        for income in ('NaN', '-1', 'Infinity'):
            rows = endpoints(); rows['minimum'] = (income, 0, 'Unemployed', 0, 6)
            with self.assertRaises(ValidationError):
                fixture(rows)
        bad = deepcopy(FORMULA); bad['base'] = '8/10'
        with self.assertRaisesMessage(ValidationError, 'coefficients'):
            fixture(endpoints(), policy={'method': methods.COMPOSITE, 'ses_formula': bad})

    def test_reordered_main_weights_are_applied_by_code_to_composite_ses(self):
        for order in permutations(CODES):
            _, ahp, _ = project(proposal(order))
            result = fixture(endpoints(0), weights=ahp['weights'])
            trace = ses_trace(result, 'minimum')
            self.assertEqual(Fraction(trace['contribution']['exact']), Fraction(ahp['weights']['SES']) * Fraction(9, 10))
            self.assertEqual(trace['ses_formula'], FORMULA)

    def test_exact_and_near_ties_use_complete_scores(self):
        rows = endpoints() | {'a': (15000, 0, 'Seasonal Worker', 1, 4),
                              'b': (15000, 0, 'Seasonal Worker', 1, 4)}
        result = fixture(rows)
        self.assertEqual([result[k]['comparison']['business_rank'] for k in ('minimum', 'a', 'b', 'maximum')], [1, 2, 2, 4])
        rows['b'] = ('15000.000000001', 0, 'Seasonal Worker', 1, 4)
        result = fixture(rows)
        self.assertEqual(result['a']['score_display'], result['b']['score_display'])
        self.assertEqual(result['b']['comparison']['business_rank'], 3)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class CompositeSesWorkflowTests(TransactionTestCase):
    draft = income_tests.SesWorkflowTests.draft
    approve = income_tests.SesWorkflowTests.approve
    bind = income_tests.SesWorkflowTests.bind
    publish = income_tests.SesWorkflowTests.publish
    applicant = income_tests.SesWorkflowTests.applicant
    generate = income_tests.SesWorkflowTests.generate
    choose = income_tests.SesWorkflowTests.choose

    def setUp(self):
        income_tests.SesWorkflowTests.setUp(self)
        self.income_weights, self.income_program = self.weights, self.program
        self.income_content = deepcopy(self.content)
        from programs.tests import program_data
        from programs.services import save_program, change_publication
        from programs.test_approved_terms import TermsHelpers
        with patch('django.utils.timezone.now', return_value=self.base):
            for status in ('DRAFT', 'LOCKED'):
                self.weights = vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=proposal(),
                    reason='SYNTHETIC composite weights; no institutional approval', status=status, method=methods.COMPOSITE)
            self.program = save_program(user=self.user, data=program_data(ewaf_applicable=True,
                name='SYNTHETIC composite SES', benefit='Synthetic benefit', slots=1,
                selection_method='Synthetic composite SES and separate human selection',
                registration_opens_at=self.base+timedelta(hours=1), registration_closes_at=self.base+timedelta(days=1)))
            change_publication(self.program.pk, user=self.user, version=self.program.version,
                action='authorize_policy', notes='SYNTHETIC authority')
        self.program.refresh_from_db()
        helper = TermsHelpers(); helper.program, helper.officer = self.program, self.user; helper.reconcile()
        self.cutoff = self.program.registration_closes_at+timedelta(hours=1)
        self.content = contracts.initial_content(methods.COMPOSITE)
        for key, (_, _, kind) in contracts.specifications(self.content).items():
            if isinstance(kind, dict):
                value = next(iter(kind))
            elif kind == 'documents':
                value = [self.doc_type.pk]
            elif kind == 'integer':
                value = 90 if key == 'evidence_max_age_days' else 12 if key == 'pa_months' else 3
            elif kind == 'datetime':
                value = (self.base-timedelta(days=1) if key == 'effective_from' else timezone.now()+timedelta(days=20)).isoformat()
            else:
                value = 'SYNTHETIC reviewed '+key+'; not an institutional operating rule.'
            self.content['choices'][key] = {'value': value, 'specified': True}

    def accept(self, app, proof, *, low=False, selections=None, **changes):
        findings = {**evidence.periods(self.configuration), 'income_monthly': ['0' if low else '100000']*3,
            'employment': 'Unemployed' if low else 'Full-Time Worker', 'household_members': 6 if low else 2,
            'history_complete': True, 'assessment_finding': 'SYNTHETIC accepted findings',
            'income_consistency': 'consistent', 'income_resolution': '', 'household_four_ps': False,
            'four_ps_household_confirmed': True,
            'four_ps_household_review': 'SYNTHETIC household relationship and participation reviewed using permitted shared assessment.'}
        findings.update(changes)
        return evidence.record(app.pk, user=self.user, expected=evidence.review_token(app,self.configuration),
            findings=findings, selections=selections or {code:[proof.pk] for code in CODES}, state='ACCEPTED',
            reason='SYNTHETIC explicit composite acceptance', confirmed=True)

    def pool(self):
        self.publish()
        a, ar = self.applicant('COMPOSITE-A')
        b, br = self.applicant('COMPOSITE-B', prior=True)
        self.accept(a, ar, low=True)
        self.accept(b, br)
        return a, ar, b, br

    def test_real_stored_policy_binding_ranking_human_decision_and_publication_journey(self):
        from announcements.results import prepare_results, publish_results, results_current
        from assistance.services import record_release
        from assistance.tests import release_data
        a, ar, b, br = self.pool()
        url = reverse('ewaf:operational_workspace',args=[self.program.pk])
        self.assertEqual(self.client.post(url, {'action':'GENERATE',
            'expected':json.dumps(operational.context(self.program.pk,user=self.user)), 'request_key':str(uuid4()),
            'reason':'SYNTHETIC HTTP composite generation'}).status_code,302)
        run=OperationalRun.objects.get(program=self.program); run.clean()
        self.assertEqual(run.snapshot['engine'],methods.COMPOSITE)
        self.assertEqual(run.configuration.policy['ses_formula'],FORMULA)
        trace=ses_trace(run.calculations,str(a.pk))
        self.assertEqual(Fraction(trace['contribution']['exact']),Fraction(9,25))
        self.assertEqual(100*Fraction(run.calculations[str(a.pk)]['score_exact']),96)
        self.assertEqual(run.calculations[str(a.pk)]['comparison']['business_rank'],1)
        self.assertEqual(len(run.calculations[str(a.pk)]['traces']),4)
        self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())
        self.choose(run,a); self.choose(run,b,outcome='NOT_SELECTED')
        item=prepare_results(self.program.pk,user=self.user,version=0,reason='SYNTHETIC permitted public result')
        public=str(item.result_revision.public_payload)
        for value in ('household_four_ps','income_monthly','score_exact','multiplier',a.public_reference):
            self.assertNotIn(value,public)
        item=publish_results(item.pk,user=self.user,version=item.version)
        self.assertTrue(results_current(item))
        a.refresh_from_db(); record_release(a.pk,user=self.user,data=release_data(a))
        run.refresh_from_db(); run.clean()

    def test_accepted_4ps_changes_use_versioned_findings_and_recalculate_complete_pool(self):
        a,ar,b,br=self.pool(); old=self.generate(); retained=deepcopy(old.payload())
        self.accept(a,ar,low=True,household_four_ps=True)
        new=self.generate()
        self.assertEqual(new.previous_id,old.pk)
        self.assertEqual(100*Fraction(new.calculations[str(a.pk)]['score_exact']),100)
        self.assertEqual(100*(Fraction(new.calculations[str(a.pk)]['score_exact'])-Fraction(old.calculations[str(a.pk)]['score_exact'])),4)
        old.refresh_from_db(); old.clean(); self.assertEqual(old.payload(),retained)
        self.assertEqual(new.snapshot['eligible'][str(a.pk)]['inputs']['SES']['household_four_ps'],1)

    def test_missing_unresolved_unconfirmed_disputed_and_stale_4ps_cannot_become_no(self):
        from documents.services import verify_document
        self.publish(); app,proof=self.applicant('COMPOSITE-UNRESOLVED')
        for change in ({'household_four_ps':None},{'household_four_ps':''},{'household_four_ps':'no'},
                       {'four_ps_household_confirmed':False},{'four_ps_household_review':''}):
            with self.subTest(change=change),self.assertRaises(ValidationError): self.accept(app,proof,**change)
        findings={**evidence.periods(self.configuration),'income_monthly':['100000']*3}
        with self.assertRaises(ValidationError):
            evidence.derive_inputs(findings,self.configuration,evidence.context(app))
        with self.assertRaises(ValidationError): self.generate()
        accepted=self.accept(app,proof)
        self.assertEqual(accepted.inputs['SES']['household_four_ps'],0)
        token=evidence.review_token(app,self.configuration)
        evidence.record(app.pk,user=self.user,expected=token,findings={},selections={},state='DISPUTED',
            reason='SYNTHETIC disputed household status',confirmed=True)
        with self.assertRaises(ValidationError): self.generate()
        self.accept(app,proof)
        verify_document(proof.document_id,user=self.user,member_version=app.member.version,
            verified=False,expires_on=None,reason='SYNTHETIC invalidated 4Ps supporting assessment')
        with self.assertRaises(ValidationError): self.generate()

    def test_explicit_policy_approval_controls_internal_coefficients_and_procedures(self):
        for key,value in (('ses_adjustment','80_20'),('four_ps_procedure',''),('four_ps_evidence_procedure','')):
            bad=deepcopy(self.content); bad['choices'][key]['value']=value
            with self.assertRaises(ValidationError): self.approve(self.draft(bad))
        approved=self.approve(); self.assertEqual(approved.method,methods.COMPOSITE)
        with self.assertRaises(ValidationError): approved.save()

    def test_http_policy_draft_approval_and_main_weight_reordering_keep_fixed_formula(self):
        url=reverse('ewaf:dataset_policies')
        data={'calculation_method':methods.COMPOSITE,'expected':policies.token(),'weight':self.weights.pk,
              'reason':'SYNTHETIC HTTP composite policy','shared_cutoff':'application_close'}
        for key,item in self.content['choices'].items():
            data[key],data['specified_'+key]=item['value'],'on'
        page=self.client.get(url)
        self.assertEqual(page.context['method'], methods.COMPOSITE)
        self.assertNotContains(page, 'aria-label="Scoring policy method"')
        self.assertContains(page,'does not guarantee fairness')
        self.assertContains(page,'name="four_ps_evidence_procedure"')
        self.assertNotContains(page,'name="si_rubric"')
        self.assertEqual(self.client.post(url,data).status_code,302)
        draft=SharedDatasetPolicy.objects.first()
        self.assertEqual(self.client.post(reverse('ewaf:dataset_policy_review',args=[draft.pk]),{
            'expected':draft.digest,'group_A':'on','group_B':'on','group_C':'on','reason':'SYNTHETIC HTTP approval'}).status_code,302)
        config=operational.latest_configuration(self.program)
        self.assertEqual(config.dataset_policy_id, SharedDatasetPolicy.objects.first().pk)
        retained=deepcopy(config.payload())
        url=reverse('ewaf:vault')
        page=self.client.get(url)
        self.assertEqual(page.context['method'], methods.COMPOSITE)
        self.assertNotContains(page, 'aria-label="EWAF calculation method"')
        self.assertNotContains(page, 'Calculation rules and member information')
        self.assertNotContains(page, '<strong>Method: ')
        for old_method in (methods.HOUSEHOLD, methods.SES):
            self.assertNotContains(page, '<strong>Method: '+methods.LABELS[old_method]+'</strong>')
        self.assertEqual(page.context['weight_state']['proposal'], proposal())
        self.assertContains(page, 'id="ewaf-configuration-form"')
        self.assertContains(page, 'js/ewaf-weights.js')
        changed=proposal(('HM','SES','ES','PA'))
        data={'calculation_method':methods.COMPOSITE,'weight_method':'slider-ratio-projection-v1',
            'expected':vault.token(),'slider_proposal':json.dumps(changed),'reason':'SYNTHETIC reordered main weights'}
        self.assertEqual(self.client.post(url,data|{'action':'DRAFT'}).status_code,302)
        data['expected']=vault.token()
        preview=self.client.post(url,data|{'action':'PREVIEW_WEIGHTS'}).json()
        self.assertEqual(preview['method'],methods.COMPOSITE)
        self.assertFalse(preview['storage_errors'])
        self.assertEqual(self.client.post(url,data|{'action':'LOCKED', 'weight_review': preview['token']}).status_code,302)
        active=vault.active(methods.COMPOSITE)
        self.assertEqual(active.validation['weights']['HM'],'0.4')
        self.assertEqual(active.validation['weights']['SES'],'0.2')
        self.assertEqual(self.client.get(url).context['weight_state']['proposal'],changed)
        config.refresh_from_db(); config.clean()
        self.assertEqual(config.payload(),retained)
        self.assertEqual(config.policy['ses_formula'],FORMULA)
        self.assertEqual(config.validation['weights']['SES'],'0.4')

    def test_foreign_expired_evidence_and_unresolved_inventory_block_without_mutation(self):
        from documents.services import verify_document
        from members.tests import create_member
        from programs.testsupport import application_fixture
        a,ar,b,br=self.pool();run=self.generate();retained=deepcopy(run.payload())
        with self.assertRaises(ValidationError):
            self.accept(a,ar,low=True,selections={code:[br.pk] for code in CODES})
        with patch('django.utils.timezone.now',return_value=timezone.now()+timedelta(days=91)):
            with self.assertRaisesMessage(ValidationError,'stale'):
                evidence.supporting(a,self.configuration,{code:[ar.pk] for code in CODES})
        with patch('django.utils.timezone.now',return_value=self.base+timedelta(hours=2)):
            application_fixture(self.program,create_member('COMPOSITE-INVENTORY-UNRESOLVED'))
        with self.assertRaises(ValidationError): self.generate()
        run.refresh_from_db();run.clean();self.assertEqual(run.payload(),retained)

    def test_same_main_vector_can_be_explicitly_adopted_without_converting_old_formula(self):
        before=deepcopy(self.income_weights.payload())
        self.weights,self.program=self.income_weights,self.income_program
        self.cutoff=self.program.registration_closes_at+timedelta(hours=1)
        new=self.bind()
        self.assertEqual(new.validation['weights'],self.income_weights.validation['weights'])
        self.assertEqual(new.policy['ses_formula'],FORMULA)
        self.income_weights.refresh_from_db(); self.assertEqual(self.income_weights.payload(),before)
        with self.assertRaises(ValidationError): contracts.weight_snapshot(self.old_weights,methods.COMPOSITE)

    def test_existing_income_only_binding_is_not_rewritten_to_composite(self):
        old=policies.save_draft(user=self.user,expected=policies.token(),content=self.income_content,
            weight_id=self.income_weights.pk,reason='SYNTHETIC retained income-only policy')
        old=policies.approve(old.pk,user=self.user,expected=old.digest,reviewed_groups=['A','B','C'],reason='SYNTHETIC approval')
        old_binding=policies.bind(self.income_program.pk,user=self.user,expected=operational.configuration_token(self.income_program),
            policy_id=old.pk,cutoff=self.income_program.registration_closes_at+timedelta(hours=1),reason='SYNTHETIC retained binding')
        retained=deepcopy(old_binding.payload())
        approved=self.approve()
        with self.assertRaises(ValidationError):
            policies.bind(self.income_program.pk,user=self.user,expected=operational.configuration_token(self.income_program),
                policy_id=approved.pk,cutoff=self.cutoff,reason='SYNTHETIC forbidden formula replacement')
        old_binding.refresh_from_db(); old_binding.clean(); self.assertEqual(old_binding.payload(),retained)

    def test_input_forms_show_reviewed_household_status_without_old_si_or_manual_ses_score(self):
        a,ar,b,br=self.pool(); url=reverse('ewaf:dataset_inputs',args=[a.pk])
        page=self.client.get(url)
        self.assertContains(page,'Income-based SES with a verified 4Ps adjustment')
        self.assertEqual(page.context['form']['household_four_ps'].value(),'no')
        for name in ('si_indigency','si_four_ps','final_ses','ses_score','evidence_SI','evidence_HI'):
            self.assertNotContains(page,'name="'+name+'"')
        data={'expected':evidence.review_token(a,self.configuration),'state':'ACCEPTED','income_0':'50000','income_1':'50000','income_2':'50000',
            'employment':'Unemployed','household_members':6,'history_complete':'on','assessment_finding':'SYNTHETIC form review',
            'income_consistency':'consistent','income_resolution':'','household_four_ps':'yes','four_ps_household_confirmed':'on',
            'four_ps_household_review':'SYNTHETIC permitted household evidence and relationship checked','confirmed':'on','reason':'SYNTHETIC HTTP acceptance',
            **{'evidence_'+code:[ar.pk] for code in CODES}}
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(DatasetInputReview.objects.filter(application=a).first().inputs['SES']['household_four_ps'],1)
        data.pop('household_four_ps');data['expected']=evidence.review_token(a,self.configuration)
        self.assertContains(self.client.post(url,data),'unresolved')

    def test_generating_ranking_exposes_private_scoring_and_calculation_tabs(self):
        from django.contrib.admin.models import LogEntry
        a, _, b, _ = self.pool()
        workspace = reverse('ewaf:operational_workspace', args=[self.program.pk])
        explanation = reverse('ewaf:operational_breakdown', args=[self.program.pk])
        guide_url = reverse('ewaf:operational_calculation_guide', args=[self.program.pk])
        before = self.client.get(workspace)
        self.assertTrue(before.context['ready'])
        self.assertNotContains(before, guide_url)
        self.assertNotContains(before, '>Scoring Explanation</a>')
        form = before.context['form']
        data = {name: form[name].value() for name in form.fields}
        generated = self.client.post(workspace, data | {'action': 'GENERATE',
            'reason': 'SYNTHETIC generated ranking for private explanation tabs'}, follow=True)
        self.assertEqual(generated.status_code, 200)
        run = OperationalRun.objects.filter(program=self.program).first()
        self.assertIsNotNone(run)
        retained = deepcopy(run.payload())
        counts = LogEntry.objects.count(), OperationalRun.objects.count(), OperationalDecision.objects.count()
        self.assertContains(generated, explanation + '?run=' + str(run.pk))
        self.assertContains(generated, guide_url + '?run=' + str(run.pk))
        guide = self.client.get(guide_url, {'run': run.pk, 'applicant': str(b.pk)})
        self.assertContains(guide, 'SES = I × (0.90 + 0.10 × P)')
        self.assertContains(guide, 'Full-Time Worker = 1')
        self.assertContains(guide, 'Unemployed = 4')
        self.assertEqual(guide.context['guide']['count'], 4)
        self.assertTrue(guide.context['guide']['pool_bounds'])
        self.assertTrue(guide.context['guide']['composite'])
        self.assertEqual(guide.context['guide']['formula_version'], FORMULA['version'])
        self.assertIn('no-store', guide['Cache-Control'])
        for code in CODES:
            self.assertContains(guide, 'data-rule-criterion="' + code + '"')
        for code in ('HI', 'SI', 'ND'):
            self.assertNotContains(guide, 'data-rule-criterion="' + code + '"')
        page = self.client.get(explanation, {'run': run.pk, 'applicant': str(b.pk), 'page': 99})
        self.assertEqual(page.context['selected']['rank'], 2)
        self.assertEqual(page.context['selected']['higher'], 1)
        self.assertTrue(all(trace['pool_higher'] == 1 for trace in page.context['selected']['traces']))
        self.assertContains(page, 'Lowest points in this pool')
        page = self.client.get(explanation, {'run': run.pk, 'applicant': str(a.pk)})
        self.assertEqual(page.context['selected']['lower'], 1)
        self.assertTrue(all(trace['pool_lower'] == 1 for trace in page.context['selected']['traces']))
        self.assertEqual(counts, (LogEntry.objects.count(), OperationalRun.objects.count(), OperationalDecision.objects.count()))
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)

    def test_breakdown_private_export_and_vault_distinguish_formula_and_main_weights(self):
        a,ar,b,br=self.pool();run=self.generate()
        page=self.client.get(reverse('ewaf:operational_breakdown',args=[self.program.pk]),{'applicant':str(a.pk),'page':99})
        self.assertContains(page,'Income need I:')
        self.assertContains(page,'Internal multiplier: 9/10')
        self.assertContains(page,'main SES weight is applied separately')
        self.assertEqual(page.context['pool_size'],2)
        data=self.client.get(reverse('ewaf:operational_export',args=[self.program.pk,run.pk])).json()
        self.assertEqual(data['criteria'],list(CODES));self.assertEqual(data['calculations'],run.calculations)
        self.assertEqual(ses_trace(data['calculations'],str(a.pk))['ses_formula'],FORMULA)
        page=self.client.get(reverse('ewaf:vault')+'?method='+methods.COMPOSITE)
        self.assertEqual(set(page.context['weight_state']['proposal']['weights']),set(CODES))
        self.assertNotContains(page,'sliders do not change the internal SES coefficients')
        self.assertContains(page,'name="calculation_method" value="'+methods.COMPOSITE+'"')

    def test_documents_indigency_and_conflicting_high_income_do_not_override_accepted_values(self):
        from documents.models import DocumentType,MembershipDocumentRequirement,MembershipApplicationDocument
        from documents.services import verify_document
        from membership.tests import pdf
        kind=DocumentType.objects.create(name='SYNTHETIC optional indigency attachment')
        requirement=MembershipDocumentRequirement.objects.create(document_type=kind,is_required=False)
        self.content['choices']['evidence_SES']['value'].append(kind.pk)
        self.publish()
        a,ar=self.applicant('COMPOSITE-DOCS-A');b,br=self.applicant('COMPOSITE-DOCS-B');c,cr=self.applicant('COMPOSITE-DOCS-C',prior=True)
        d,dr=self.applicant('COMPOSITE-DOCS-D')
        attachment=MembershipApplicationDocument.objects.create(application=a.member.application,requirement=requirement,
            label='SYNTHETIC optional certificate',file=pdf(),content_type='application/pdf',size=50)
        review=verify_document(attachment.pk,user=self.user,member_version=a.member.version,verified=True,expires_on=None,
            reason='SYNTHETIC optional evidence reviewed')
        args={'income_monthly':['100000']*3,'household_four_ps':True,'employment':'Seasonal Worker','household_members':4}
        with self.assertRaises(ValidationError): self.accept(a,ar,**args,income_consistency='unresolved')
        self.accept(a,ar,**args,income_consistency='resolved',income_resolution='SYNTHETIC dates/circumstances reviewed; PHP 100,000 accepted.',
            selections={code:[ar.pk] for code in CODES}|{'SES':[ar.pk,review.pk]})
        self.accept(b,br,**args);self.accept(c,cr,low=True)
        self.accept(d,dr,income_monthly=['200000']*3)
        run=self.generate()
        self.assertEqual(run.calculations[str(a.pk)]['score_exact'],run.calculations[str(b.pk)]['score_exact'])
        trace=ses_trace(run.calculations,str(a.pk))
        self.assertEqual(Fraction(trace['input']['exact']),100000)
        self.assertEqual(Fraction(trace['normalized']['exact']),Fraction(1,2))
        self.assertEqual(len(run.calculations[str(a.pk)]['traces']),4)

    test_audit_rollback = income_tests.dataset_tests.DatasetPolicyTests.test_acceptance_calculation_and_binding_audit_failures_roll_back
    test_flags_cutoff_and_unsupported_policy = income_tests.dataset_tests.DatasetPolicyTests.test_feature_flags_cutoff_approved_scope_and_unsupported_rules_are_not_bypassed
