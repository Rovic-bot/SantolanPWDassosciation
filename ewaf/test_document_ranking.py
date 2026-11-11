"""Document weights and owner-confirmed SI, using disposable synthetic records."""
from copy import deepcopy
from fractions import Fraction
import json
from unittest.mock import patch
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from .vault_forms import PercentageWeightsForm, SaatyWeightsForm, saaty_state
from .vault_models import VaultRevision
from .dataset_methods import HOUSEHOLD
from . import vault_services as vault, vault_weights, operational_services as operational
from .operational_models import OperationalRun, OperationalDecision
from .revised import contracts, live_evidence as evidence, si
from .revised.live_forms import InputReviewForm
from .revised.math import CRITERIA, DEFAULTS
from . import test_dataset_policy as dataset_tests


class DocumentArithmeticTests(SimpleTestCase):
    def test_saaty_sliders_start_from_unequal_document_proposal(self):
        state = saaty_state()
        self.assertEqual(state['proposal']['weights'],
            dict(zip(CRITERIA, (3421, 2360, 1774, 1223, 1222))))
        form = SaatyWeightsForm({'expected': 'synthetic', 'weight_method': 'slider-ratio-projection-v1',
            'slider_proposal': json.dumps(state['proposal']), 'reason': 'Synthetic scale review'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.validation['reference_consistency'], 'PASSED')

    def test_all_four_si_combinations_and_unknown_are_distinct(self):
        for four_ps, indigency, expected in [(True, True, '5'), (True, False, '2.5'),
                                             (False, True, '2.5'), (False, False, '0')]:
            self.assertEqual(si.score({'four_ps': four_ps, 'indigency': indigency}), expected)
        for value in [None, '', 0, 1, 'no', 'yes']:
            with self.assertRaises(ValidationError):
                si.score({'four_ps': value, 'indigency': False})
        with self.assertRaises(ValidationError):
            si.score({'four_ps': False})

    def test_exact_percentages_and_remainder_without_ahp_projection(self):
        validation, origin = vault_weights.compile_weights(dict(zip(CRITERIA, DEFAULTS)))
        self.assertEqual(validation['weights'], dict(zip(CRITERIA, ('0.3421', '0.2360', '0.1774', '0.1223', '0.1222'))))
        self.assertEqual(vault_weights.replay(origin, {}), validation)
        with self.assertRaises(ValidationError):
            vault_weights.replay(origin, {'HI:SI': '1'})
        invalid = deepcopy(origin)
        invalid['proposal']['weights']['HM'] += 1
        with self.assertRaises(ValidationError):
            vault_weights.replay(invalid, {})

    def test_invalid_weight_totals_precision_and_zero_remainder(self):
        invalid = {'HI': '62.55', 'SI': '19.48', 'ES': '14.07', 'PA': '12.23'}
        with self.assertRaisesMessage(ValidationError, 'HM would be'):
            vault_weights.compile_weights(invalid)
        invalid['HI'] = '54.22'
        validation, _ = vault_weights.compile_weights(invalid)
        self.assertEqual(validation['weights']['HM'], '0.0000')
        invalid['HI'] = '54.221'
        with self.assertRaises(ValidationError):
            vault_weights.compile_weights(invalid)
        for raw in ['NaN', 'Infinity', '-1', '1e2']:
            with self.assertRaises(ValidationError):
                vault_weights.compile_weights(invalid | {'HI': raw})

    def test_new_draft_uses_confirmed_si_without_changing_retained_proposals(self):
        old = contracts.initial_content()
        draft = contracts.document_content(old)
        self.assertEqual(old['choices']['si_rubric']['value'], '')
        self.assertEqual(draft['choices']['si_rubric'], {'value': si.METHOD, 'specified': True})
        self.assertEqual(old['si_proposal'], draft['si_proposal'])
        self.assertFalse(contracts.applicable(draft, 'si_critical'))
        contracts.structural(draft)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DocumentRankingTests(TransactionTestCase):
    # Reuse fixture builders, without rerunning the inherited legacy test methods.
    draft = dataset_tests.DatasetPolicyTests.draft
    approve = dataset_tests.DatasetPolicyTests.approve
    bind = dataset_tests.DatasetPolicyTests.bind
    publish = dataset_tests.DatasetPolicyTests.publish
    applicant = dataset_tests.DatasetPolicyTests.applicant
    generate = dataset_tests.DatasetPolicyTests.generate

    def setUp(self):
        dataset_tests.DatasetPolicyTests.setUp(self)
        self.old_weights = self.weights
        self.old_payload = self.weights.payload()
        self.weights = vault.approve_percentages(user=self.user, expected=vault.token(),
            values=dict(zip(CRITERIA, DEFAULTS)), reason='SYNTHETIC approval of document percentages')
        self.content = contracts.document_content(self.content)

    def accept(self, app, proof, *, low=False, **changes):
        findings = {**evidence.periods(self.configuration), 'income_monthly': ['5000' if low else '20000'] * 3,
            'si_documents': {'four_ps': low, 'indigency': low},
            'employment': 'Unemployed' if low else 'Full-Time Worker', 'household_members': 6 if low else 2,
            'history_complete': True, 'assessment_finding': 'Synthetic reviewed sources for every criterion'}
        findings.update(changes)
        return evidence.record(app.pk, user=self.user, expected=evidence.review_token(app, self.configuration),
            findings=findings, selections={code: [proof.pk] for code in CRITERIA},
            state='ACCEPTED', reason='Synthetic verified findings', confirmed=True)

    def test_exact_vault_approval_replays_and_keeps_old_versions(self):
        self.weights.clean()
        self.assertEqual(self.weights.judgments, {})
        self.assertEqual(contracts.weight_snapshot(self.weights)['weights']['HI'], '0.3421')
        self.old_weights.refresh_from_db()
        self.old_weights.clean()
        self.assertEqual(self.old_weights.payload(), self.old_payload)
        with self.assertRaises(ValidationError):
            self.weights.save()

    def test_open_exact_percentage_editor_keeps_its_method_and_rejects_stale_posts(self):
        url = reverse('ewaf:vault')
        page = self.client.get(url + '?method=' + HOUSEHOLD)
        self.assertContains(page, 'name="slider_proposal"')
        self.assertContains(page, 'name="weight_method"')
        self.assertNotContains(page, 'Calculation rules and member information')
        self.assertNotContains(page, 'id="scoring-policy"')
        self.assertNotContains(page, 'Revised calculation preview')
        data = {'expected': vault.token(), 'action': 'LOCKED', 'HI': '40.00', 'SI': '23.60',
                'ES': '17.74', 'PA': '12.23', 'reason': 'Synthetic changed percentages'}
        self.assertRedirects(self.client.post(url, data), url)
        current = vault.active()
        self.assertEqual(current.validation['weights']['HI'], '0.4000')
        self.assertEqual(current.validation['weights']['HM'], '0.0643')
        count = VaultRevision.objects.count()
        self.assertContains(self.client.post(url, data), 'The vault changed')
        self.assertEqual(VaultRevision.objects.count(), count)
        self.assertContains(self.client.get(url), '6.43%')

    def test_saaty_approval_matches_displayed_calculation_and_retains_exact_versions(self):
        from .weight_input import project, METHOD
        url = reverse('ewaf:vault')
        form = self.client.get(url + '?method=' + HOUSEHOLD).context['form']
        self.assertIsInstance(form, SaatyWeightsForm)
        data = {name: form[name].value() for name in form.fields}
        data.update(action='LOCKED', reason='Synthetic approval of calculated Saaty weights')
        proposal = json.loads(data['slider_proposal'])
        judgments, validation, origin = project(proposal)
        retained = self.weights.payload()
        before = VaultRevision.objects.count(), LogEntry.objects.count()
        result = self.client.post(url, data | {'action': 'PREVIEW_WEIGHTS'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(before, (VaultRevision.objects.count(), LogEntry.objects.count()))
        self.assertRedirects(self.client.post(url, data), url)
        approved = vault.active()
        self.assertEqual(approved.policy['weight_input'], origin)
        self.assertEqual(approved.policy['weight_input']['method'], METHOD)
        self.assertEqual(approved.judgments, judgments)
        self.assertEqual(approved.validation, validation)
        from .weight_input import percentages
        displayed = percentages(validation['weights'], proposal['order'])
        for row in result.json()['rows']:
            self.assertEqual(row['actual'], f"{displayed[row['code']] / 100:.2f}")
        self.assertEqual(approved.reason, data['reason'])
        approved.clean()
        self.assertEqual(contracts.weight_snapshot(approved)['weights'], validation['weights'])
        reopened = self.client.get(url + '?method=' + HOUSEHOLD).context['weight_state']['proposal']
        self.assertEqual(reopened, proposal)
        self.assertEqual(project(reopened)[1], validation)
        self.weights.refresh_from_db()
        self.weights.clean()
        self.assertEqual(self.weights.payload(), retained)
        count = VaultRevision.objects.count()
        self.assertContains(self.client.post(url, data), 'The vault changed')
        self.assertEqual(VaultRevision.objects.count(), count)

    def test_saaty_priority_can_put_hm_first_and_rejects_invalid_approval(self):
        from .weight_input import METHOD, project
        url = reverse('ewaf:vault')
        order = ['HM', 'SI', 'ES', 'PA', 'HI']
        proposal = {'order': order, 'weights': dict(zip(order, [4000, 2500, 1500, 1000, 1000]))}
        data = {'expected': vault.token(), 'action': 'LOCKED', 'weight_method': METHOD,
                'slider_proposal': json.dumps(proposal), 'reason': 'Synthetic household priority'}
        before = VaultRevision.objects.count(), LogEntry.objects.count()
        for change in ({'reason': ''}, {'slider_proposal': json.dumps({'order': order,
                'weights': dict(zip(order, [10000, 0, 0, 0, 0]))})}, {'weight_method': 'unrecognized'}):
            self.assertEqual(self.client.post(url, data | change).status_code, 200)
            self.assertEqual(before, (VaultRevision.objects.count(), LogEntry.objects.count()))
        with patch('django.contrib.admin.models.LogEntry.objects.create', side_effect=ValidationError('audit failed')):
            self.assertContains(self.client.post(url, data), 'audit failed')
        self.assertEqual(before, (VaultRevision.objects.count(), LogEntry.objects.count()))
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(vault.active().validation, project(proposal)[1])
        self.assertEqual(self.client.get(url + '?method=' + HOUSEHOLD).context['weight_state']['proposal']['order'], order)

    def test_saaty_preview_and_approval_permissions(self):
        from membership.tests import grant
        from .weight_input import METHOD
        url = reverse('ewaf:vault')
        data = {'expected': vault.token(), 'weight_method': METHOD,
            'slider_proposal': json.dumps(saaty_state()['proposal']), 'reason': 'Synthetic permissions review'}
        reviewer = get_user_model().objects.create_user('synthetic-weight-configurator', is_staff=True)
        grant(reviewer, 'accounts.access_dashboard', *operational.VIEW, 'ewaf.configure_operational')
        self.client.force_login(reviewer)
        self.assertEqual(self.client.post(url, data | {'action': 'PREVIEW_WEIGHTS'}).status_code, 200)
        self.assertEqual(self.client.post(url, data | {'action': 'LOCKED'}).status_code, 403)
        outsider = get_user_model().objects.create_user('synthetic-weight-outsider', is_staff=True)
        grant(outsider, 'accounts.access_dashboard', *operational.VIEW)
        self.client.force_login(outsider)
        self.assertEqual(self.client.post(url, data | {'action': 'PREVIEW_WEIGHTS'}).status_code, 403)

    def test_invalid_or_unexplained_percentages_do_not_create_a_revision(self):
        before = VaultRevision.objects.count(), LogEntry.objects.count()
        data = {'expected': vault.token(), 'action': 'LOCKED', 'HI': '62.55', 'SI': '19.48',
                'ES': '14.07', 'PA': '12.23', 'reason': 'Synthetic invalid weights'}
        response = self.client.post(reverse('ewaf:vault'), data)
        self.assertContains(response, 'HM would be')
        self.assertEqual(before, (VaultRevision.objects.count(), LogEntry.objects.count()))
        form = PercentageWeightsForm(data | {'HI': '34.21', 'reason': ''})
        self.assertFalse(form.is_valid())

    def test_weight_authority_and_audit_failure_roll_back(self):
        before = VaultRevision.objects.count(), LogEntry.objects.count()
        args = {'expected': vault.token(), 'values': dict(zip(CRITERIA, DEFAULTS)), 'reason': 'Synthetic approval'}
        outsider = get_user_model().objects.create_user('synthetic-unprivileged-weights', is_staff=True)
        with self.assertRaises(PermissionDenied):
            vault.approve_percentages(user=outsider, **args)
        with patch('django.contrib.admin.models.LogEntry.objects.create', side_effect=ValidationError('audit failed')):
            with self.assertRaisesMessage(ValidationError, 'audit failed'):
                vault.approve_percentages(user=self.user, **args)
        self.assertEqual(before, (VaultRevision.objects.count(), LogEntry.objects.count()))

    def test_complete_pool_generates_document_ranking_and_no_selection(self):
        self.publish()
        a, ar = self.applicant('DOC-RANK-A')
        b, br = self.applicant('DOC-RANK-B', prior=True)
        c, cr = self.applicant('DOC-RANK-C')
        self.accept(a, ar, low=True)
        self.accept(b, br)
        with self.assertRaisesMessage(ValidationError, 'Accept all five'):
            self.generate()
        self.assertFalse(OperationalRun.objects.exists())
        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertEqual(page.context['ready_count'], 2)
        self.assertEqual(page.context['pending_count'], 1)
        accepted = self.accept(c, cr, income_monthly=['12500'] * 3, household_members=4,
            employment='Part-Time Worker', si_documents={'four_ps': False, 'indigency': True})
        self.assertEqual(accepted.inputs['SI']['value'], '2.5')
        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertTrue(page.context['ready'])
        self.assertEqual(page.context['ready_count'], 3)
        data = page.context['form'].initial | {'action': 'GENERATE', 'reason': 'Synthetic HTTP full-pool generation'}
        import json
        data['expected'] = json.dumps(data['expected'])
        self.assertEqual(self.client.post(reverse('ewaf:operational_workspace', args=[self.program.pk]), data).status_code, 302)
        run = OperationalRun.objects.get()
        run.clean()
        self.assertNotIn('accepted_values', run.snapshot['manifest'][0])
        self.assertEqual([Fraction(run.calculations[str(app.pk)]['score_exact']) * 100 for app in (a, b, c)],
                         [Fraction(100), Fraction(0), Fraction(6379, 120)])
        self.assertEqual([run.calculations[str(app.pk)]['comparison']['business_rank'] for app in (a, b, c)], [1, 3, 2])
        self.assertFalse(OperationalDecision.objects.exists())
        response = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]))
        self.assertContains(response, '100.00')
        self.assertNotContains(response, 'calculation preview')

    def test_si_unanswered_is_blocked_and_accepted_findings_are_prefilled(self):
        self.publish()
        app, review = self.applicant('DOC-SI-REVIEW')
        with self.assertRaisesMessage(ValidationError, 'Review both'):
            self.accept(app, review, si_documents={'four_ps': None, 'indigency': False})
        accepted = self.accept(app, review, si_documents={'four_ps': True, 'indigency': False})
        accepted.clean()
        self.assertEqual(accepted.inputs['SI']['value'], '2.5')
        response = self.client.get(reverse('ewaf:dataset_inputs', args=[app.pk]))
        self.assertEqual(response.context['form']['si_four_ps'].value(), 'yes')
        self.assertEqual(response.context['form']['si_indigency'].value(), 'no')
        self.assertNotContains(response, 'name="si_food"')
        self.assertContains(response, 'Certificate of Indigency')

    def test_zero_hm_weight_is_retained_exactly_without_reweighting(self):
        weight = vault.approve_percentages(user=self.user, expected=vault.token(),
            values={'HI': '54.22', 'SI': '19.48', 'ES': '14.07', 'PA': '12.23'}, reason='Synthetic zero remainder')
        snapshot = contracts.weight_snapshot(weight)
        self.assertEqual(snapshot['weights']['HM'], '0.0000')
        self.assertEqual(snapshot['exact_total'], '1')

    def test_policy_editor_retains_confirmed_si_and_rejects_legacy_choice_in_new_drafts(self):
        from .revised import live_services
        from .revised.live_models import SharedDatasetPolicy
        data = {'expected': live_services.token(), 'weight': self.weights.pk, 'reason': 'Synthetic reviewed configuration',
                'shared_cutoff': 'application_close'}
        for key, entry in self.content['choices'].items():
            if contracts.applicable(self.content, key):
                data[key] = entry['value']
                data['specified_' + key] = 'on'
        url = reverse('ewaf:dataset_policies')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        draft = SharedDatasetPolicy.objects.get()
        self.assertEqual(draft.content['choices']['si_rubric']['value'], si.METHOD)
        self.assertEqual(contracts.findings(draft.content, draft.weight_snapshot), [])
        rejected = self.client.post(url, data | {'expected': live_services.token(), 'si_rubric': 'barriers_v1'})
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.context['form'].errors['si_rubric'])
        self.assertEqual(SharedDatasetPolicy.objects.count(), 1)

    def test_input_form_requires_both_findings_and_accepts_either_document(self):
        from .revised.live_models import DatasetInputReview
        self.publish()
        app, proof = self.applicant('DOC-SI-FORM')
        data = {'expected': evidence.review_token(app, self.configuration), 'state': 'ACCEPTED',
            'employment': 'Unemployed', 'household_members': 4, 'history_complete': 'on',
            'assessment_finding': 'Synthetic evidence review', 'reason': 'Synthetic reviewed findings',
            'confirmed': 'on', 'income_0': '5000', 'income_1': '5000', 'income_2': '5000',
            'si_four_ps': '', 'si_indigency': 'yes', **{'evidence_' + code: [proof.pk] for code in CRITERIA}}
        url = reverse('ewaf:dataset_inputs', args=[app.pk])
        response = self.client.post(url, data)
        self.assertContains(response, 'Review both 4Ps')
        self.assertFalse(DatasetInputReview.objects.filter(application=app).exists())
        response = self.client.post(url, data | {'si_four_ps': 'no'})
        self.assertEqual(response.status_code, 302)
        saved = DatasetInputReview.objects.get(application=app)
        self.assertEqual(saved.inputs['SI']['value'], '2.5')
        self.assertEqual(saved.findings['si_documents'], {'four_ps': False, 'indigency': True})

    def test_retired_preview_redirects_without_writes_and_cannot_calculate(self):
        before = VaultRevision.objects.count(), OperationalRun.objects.count(), LogEntry.objects.count()
        url = reverse('ewaf:revised_preview')
        self.assertRedirects(self.client.get(url), reverse('ewaf:operational_programs'))
        self.assertEqual(self.client.post(url, {'action': 'RETAIN'}).status_code, 405)
        self.assertEqual(before, (VaultRevision.objects.count(), OperationalRun.objects.count(), LogEntry.objects.count()))
