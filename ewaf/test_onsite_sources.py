"""Fictional mappings exercise the unchanged engine; never seed approved policy."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TransactionTestCase
from documents.services import verify_document
from members.profile import INCOME
from members.services import update_member
from membership.forms import PROFILE_FIELDS
from assistance.services import review_eligibility
from assistance.tests import review_data
from programs.testsupport import verified_photo
from .evidence import reviewed_value, validate_policy
from .operational_policy import findings
from .operational_testsupport import OperationalHelpers
from .operational_models import OperationalRun, OperationalDecision
from .four_criterion_development import ahp


class CategorySourceTests(SimpleTestCase):
    def test_categories_require_exact_recorded_identifier_and_explicit_definition(self):
        member = SimpleNamespace(income_category='income_5000_10000', employment_status='retired',
            monthly_income=None, employment_information='Legacy description', dependents=3)
        application = SimpleNamespace(member=member)
        for code, source, value in (('SI', 'income_category', member.income_category),
                                     ('ES', 'employment_status', member.employment_status)):
            rule = {'source_types': [source], 'categories': {value: 'Fictional explicitly reviewed category'}}
            self.assertEqual(reviewed_value(application, code, source, None, rule), (value, 'category', value))
            with self.assertRaises(ValidationError):
                reviewed_value(application, code, source, 'fabricated', rule)
            with self.assertRaises(ValidationError):
                reviewed_value(application, code, source, None, {'source_types': [source], 'categories': {}})
        with self.assertRaises(ValidationError):
            reviewed_value(application, 'ES', 'employment_text', None, {'source_types': ['employment_text']})
        self.assertEqual(reviewed_value(application, 'SI', 'monthly_income', None,
            {'source_types': ['monthly_income']}), (None, 'missing', None))
        self.assertEqual(reviewed_value(application, 'ND', 'dependent_count', None,
            {'source_types': ['dependent_count']}), (3, 'integer', 3))


class OnsiteOperationalSourcesTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()

    def update_profile(self):
        self.member.refresh_from_db()
        data = {name: getattr(self.member, name) for name in PROFILE_FIELDS}
        data.update(disability_type=self.member.disability_type_id, income_category='income_5000_10000',
                    employment_status='retired', dependents='3')
        self.member = update_member(self.member.pk, user=self.officer, version=self.member.version,
            data=data, notes='Fictional onsite source correction with separate evidence review required')

    def categorical_policy(self):
        snapshot = deepcopy(self.policy.snapshot)
        for code, source, category in (('SI', 'income_category', 'income_5000_10000'), ('ES', 'employment_status', 'retired')):
            snapshot['criteria'][code].update(source_types=[source], unit='category',
                categories={category: 'Fictional membership category explicitly defined for this test'},
                evidence_mappings={source: [self.mapping(code)]},
                rule_authority='Fictional category authority; not an Association policy')
        return snapshot

    def test_explicit_verified_category_mapping_recalculates_and_keeps_history(self):
        self.lock_policy()
        original = self.calculate()
        decision = self.choose(original)
        retained = deepcopy(original.payload())
        old_decision = deepcopy(decision.payload())
        self.update_profile()
        self.assertEqual(self.member.income_category_label, dict(INCOME)['income_5000_10000'])
        with self.assertRaises(ValidationError):
            self.choose(original, expected_revision=1)
        with self.assertRaises(ValidationError):
            self.calculate()
        self.policy = self.policy_record(self.categorical_policy())
        # A new label alone cannot verify the source; all stale documents and
        # program-specific eligibility/identity decisions must be reviewed again.
        with self.assertRaises(ValidationError):
            self.assess('ES', source_type='employment_status')
        for code, document in self.criterion_documents.items():
            self.criterion_reviews[code] = verify_document(document.pk, user=self.officer,
                member_version=self.member.version, verified=True, expires_on=None, reason='Fictional current onsite evidence review')
        self.document_review = self.criterion_reviews['ND']
        self.application.refresh_from_db()
        verified_photo(self.application)
        review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application,
            **{f'check_{row.pk}': 'pass' for row in self.relevance_requirements}))
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            self.assess(code, **({'source_type': 'income_category'} if code == 'SI' else
                                {'source_type': 'employment_status'} if code == 'ES' else {}))
        for code, source, category, number in (('SI', 'income_category', 'income_5000_10000', '0.6'),
                                               ('ES', 'employment_status', 'retired', '0.4')):
            self.proposal['criteria'][code].update(source_type=source, value_type='category', unit='category',
                encoding={category: number}, bounds={'method': 'fixed', 'lower': '0', 'upper': '1'})
        self.lock_policy()
        replacement = self.calculate()
        calculation = replacement.calculations[str(self.application.pk)]
        traces = {row['criterion']: row for row in calculation['traces']}
        self.assertEqual(set(traces), {'SI', 'ES', 'PA', 'ND'})
        self.assertEqual(Decimal(traces['SI']['normalized']), Decimal('.6'))
        self.assertEqual(Decimal(traces['ES']['normalized']), Decimal('.4'))
        self.assertEqual(Decimal(traces['ND']['normalized']), Decimal('.3'))
        self.assertEqual(Decimal(traces['PA']['normalized']), Decimal('0'))
        self.assertEqual(OperationalDecision.objects.count(), 1)
        self.assertEqual(OperationalRun.objects.count(), 2)
        original.refresh_from_db()
        decision.refresh_from_db()
        self.assertEqual(original.payload(), retained)
        self.assertEqual(decision.payload(), old_decision)
        original.clean()
        replacement.clean()

    def test_unknown_encodings_and_legacy_policy_equivalence_are_rejected(self):
        snapshot = self.categorical_policy()
        snapshot['criteria']['ES']['categories'] = {'old_unemployed': 'Not an authorized membership identifier'}
        with self.assertRaises(ValidationError):
            validate_policy(snapshot)
        proposed = deepcopy(self.proposal)
        proposed['criteria']['ES'].update(source_type='employment_status', value_type='category',
            encoding={'old_unemployed': '1'})
        self.assertTrue(any('ES.encoding' in item for item in findings(proposed, ahp()['pairs'])))
        proposed['criteria']['ES']['encoding'] = None
        self.assertTrue(any('ES.encoding' in item for item in findings(proposed, ahp()['pairs'])))
