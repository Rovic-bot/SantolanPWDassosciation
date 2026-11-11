"""Fictional household data; numerical examples are tests, never policy defaults."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TransactionTestCase
from .household_criteria import CRITERIA, PAIRS, SOURCES
from .household_math import ahp, calculate
from .evidence import reviewed_value, validate_policy
from .weight_input import project, preview, accept, percentages
from .operational_testsupport import OperationalHelpers


class HouseholdMathTests(SimpleTestCase):
    def test_blank_numeric_mapping_and_new_draft_have_no_invented_rules(self):
        from .policy_forms import MappingWidget
        from .operational_forms import WeightConfigurationForm
        self.assertEqual(MappingWidget().value_from_datadict({}, {}, 'HI_encoding'), '')
        data = {'expected': 'fictional-version', 'reason': 'Fictional draft'}
        data.update({'pair_' + pair.replace(':', '_'): '1' for pair in PAIRS})
        form = WeightConfigurationForm(data, program=SimpleNamespace(pk=1))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.proposed()['criteria'], dict.fromkeys(CRITERIA, {}))

    def test_five_equal_comparisons_and_hand_calculated_score(self):
        judgments = dict.fromkeys(PAIRS, '1')
        result = ahp(judgments)
        self.assertEqual(result['RI'], '1.12')
        self.assertEqual(result['CR'], '0')
        self.assertEqual(result['weights'], dict.fromkeys(CRITERIA, '0.2'))
        definitions, inputs = {}, {}
        for code, value, lower, upper, direction, encoding in (
            ('HI', '1000', '0', '2000', 'inverse', None),
            ('SI', 'Yes', '0', '1', 'benefit', {'Yes': '1', 'No': '0'}),
            ('ES', 'unemployed', '0', '1', 'benefit', {'unemployed': '1'}),
            ('PA', 2, '0', '4', 'inverse', None),
            ('HM', 4, '1', '7', 'benefit', None)):
            definitions[code] = {'source_type': SOURCES[code], 'unit': 'test unit', 'encoding': encoding,
                'direction': direction, 'bounds': {'lower': lower, 'upper': upper}}
            inputs[code] = {'source_type': SOURCES[code], 'unit': 'test unit', 'value': value}
        row = calculate(inputs=inputs, definitions=definitions, judgments=judgments, validation=result)
        self.assertEqual(Decimal(row['score_0_100']), Decimal('70'))
        self.assertEqual([entry['criterion'] for entry in row['traces']], list(CRITERIA))
        with self.assertRaises(ValidationError):
            calculate(inputs=inputs | {'HM': inputs['HM'] | {'value': None}},
                definitions=definitions, judgments=judgments, validation=result)

    def test_five_weight_preview_is_bound_and_legacy_replay_is_identical(self):
        proposal = {'order': list(CRITERIA), 'weights': dict(zip(CRITERIA, [3000, 2500, 2000, 1500, 1000]))}
        judgments, weights, _ = project(proposal)
        self.assertEqual(len(judgments), 10)
        self.assertEqual(sum(percentages(weights['weights']).values()), 10000)
        value = preview(proposal, program=1, expected='version')
        self.assertEqual(accept(value['token'], proposal, program=1, expected='version')[0], judgments)
        with self.assertRaises(ValidationError):
            accept(value['token'], proposal, program=2, expected='version')
        from .four_criterion_development import ahp as legacy
        from .operational_policy import ahp as replay
        old = legacy()
        self.assertEqual(replay(old['pairs']), old)
        with self.assertRaises(ValidationError):
            ahp(old['pairs'])

    def test_household_sources_use_registration_and_reject_replacement_values(self):
        member = SimpleNamespace(monthly_income=Decimal('90000'), dependents=8,
            employment_information='', employment_status='unemployed', income_category='',
            household_monthly_income=Decimal('14500.50'), household_members=5,
            registration_profile={'four_ps_member': 'Yes', 'family_members': 6})
        application = SimpleNamespace(member=member)
        for code, expected in (('HI', '14500.50'), ('SI', 'Yes'), ('ES', 'unemployed'), ('HM', 5)):
            rule = {'source_types': [SOURCES[code]], 'categories': {'Yes': 'Yes', 'No': 'No', 'unemployed': 'Unemployed'}}
            self.assertEqual(reviewed_value(application, code, SOURCES[code], None, rule)[0], expected)
            with self.assertRaises(ValidationError):
                reviewed_value(application, code, SOURCES[code], 'invented', rule)
        member.household_members = member.household_monthly_income = None
        for code in ('HI', 'HM'):
            self.assertEqual(reviewed_value(application, code, SOURCES[code], None,
                {'source_types': [SOURCES[code]]})[:2], (None, 'missing'))


class HouseholdOperationalTests(OperationalHelpers, TransactionTestCase):
    def test_new_five_criterion_run_keeps_old_configuration_and_calculation(self):
        self.setup_operational()
        old_config = self.lock_policy()
        old_run = self.calculate()
        retained = deepcopy(old_run.payload())
        self.member.household_monthly_income = Decimal('1000')
        self.member.household_members = 4
        self.member.employment_status = 'unemployed'
        self.member.registration_profile = {'four_ps_member': 'Yes'}
        self.member.version += 1
        self.member.save()
        from documents.services import verify_document
        for code, document in self.criterion_documents.items():
            self.criterion_reviews[code] = verify_document(document.pk, user=self.officer,
                member_version=self.member.version, verified=True, expires_on=None, reason='Fictional current household evidence')
        self.document_review = self.criterion_reviews['ND']
        from programs.testsupport import verified_photo
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        self.application.refresh_from_db()
        verified_photo(self.application)
        review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application,
            **{f'check_{row.pk}': 'pass' for row in self.relevance_requirements}))
        snapshot = deepcopy(self.policy.snapshot)
        snapshot['criteria'].pop('ND')
        for code, base, unit, categories in (('HI', 'SI', 'PHP/month', {}),
            ('SI', 'SI', 'category', {'Yes': '4Ps member', 'No': 'Not a 4Ps member'}),
            ('ES', 'ES', 'category', {'unemployed': 'Unemployed'}), ('HM', 'ND', 'persons', {})):
            snapshot['criteria'][code] = {'definition': 'Fictional ' + code, 'source_types': [SOURCES[code]],
                'unit': unit, 'categories': categories, 'rule_authority': 'Fictional test authority',
                'evidence_mappings': {SOURCES[code]: [self.mapping(base)]}}
        validate_policy(snapshot)
        self.policy = self.policy_record(snapshot)
        from .evidence_services import record_assessment
        for code, base in (('HI', 'SI'), ('SI', 'SI'), ('ES', 'ES'), ('HM', 'ND'), ('PA', 'PA'), ('PR', 'PR')):
            values = self.assessment_values(base)
            if code in ('HI', 'HM'):
                values['expected_revision'] = 0
            values.update(criterion=code, source_type=SOURCES.get(code, 'program_relevance'))
            record_assessment(self.application.pk, **values)
        self.proposal['criteria'].pop('ND')
        for code, lower, upper, direction, encoding, value_type, unit in (
            ('HI', '0', '2000', 'inverse', None, 'decimal', 'PHP/month'),
            ('SI', '0', '1', 'benefit', {'Yes': '1', 'No': '0'}, 'category', 'category'),
            ('ES', '0', '1', 'benefit', {'unemployed': '1'}, 'category', 'category'),
            ('HM', '1', '7', 'benefit', None, 'integer', 'persons')):
            self.proposal['criteria'][code] = {'measure': 'Fictional ' + code, 'source_type': SOURCES[code],
                'unit': unit, 'value_type': value_type, 'encoding': encoding, 'direction': direction,
                'bounds': {'method': 'fixed', 'lower': lower, 'upper': upper},
                'observation_period': 'Fictional current evidence', 'edge_cases': 'block'}
        from . import operational_services as service
        config = service.record_configuration(self.program.pk, user=self.officer,
            expected=service.configuration_token(self.program), proposed=self.proposal,
            judgments=dict.fromkeys(PAIRS, '1'), status='LOCKED', reason='Fictional five-criterion approval', attested=True)
        run = self.calculate()
        self.assertEqual(run.previous_id, old_run.pk)
        self.assertEqual(config.previous_id, old_config.pk)
        self.assertEqual(run.calculations[str(self.application.pk)]['criteria'], list(CRITERIA))
        run.clean()
        old_run.refresh_from_db()
        self.assertEqual(old_run.payload(), retained)
        old_run.clean()
        from django.urls import reverse
        self.client.force_login(self.officer)
        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertContains(page, 'Household monthly income')
        self.assertEqual(page.context['weight_state']['proposal']['order'], list(CRITERIA))
        breakdown = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]))
        self.assertEqual(breakdown.status_code, 200)
        display_traces = breakdown.context['selected']['display_traces']
        self.assertEqual([row['code'] for row in display_traces], ['HI', 'SI', 'ES', 'PA', 'HM'])
        stored = {row['criterion']: row for row in run.calculations[str(self.application.pk)]['traces']}
        for row in display_traces:
            self.assertTrue(row['included'])
            self.assertEqual(row['normalized'], stored[row['code']]['normalized'])
            self.assertEqual(row['contribution'], stored[row['code']]['contribution'])
        self.assertEqual(breakdown.context['selected']['legacy_traces'], [])
        self.assertNotContains(breakdown, 'Not included in this calculation')
        review = self.client.get(reverse('ewaf:evidence_review', args=[self.application.pk, 'HI']))
        self.assertEqual(review.context['form']['value'].value(), '1000.00')
        self.assertTrue(review.context['form'].fields['value'].disabled)
        self.assertEqual(review.context['form'].fields['source_type'].choices[0][0], 'household_monthly_income')
