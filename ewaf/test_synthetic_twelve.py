"""Owner-requested T01-T12 fixture. No operational policy or real data is changed.

Run only through scripts/g12_test_runner.py and SyntheticTwelveRunner. Each
scenario recreates the same twelve-person pool and 27-release ledger in the
disposable database. All approval/verification statements are synthetic.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from assistance.models import AssistanceRelease
from assistance.services import review_eligibility, decide_assistance, record_release, void_release
from assistance.tests import seed_statuses, review_data, decision_data, release_data
from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
from documents.services import verify_document
from members.models import Member, DisabilityType
from membership import registration_services as registration, services as membership_services
from membership.models import MembershipSettings
from membership.test_pdf_registration import association_data, pdf_policy
from membership.test_registration_handoff import HandoffHelpers, acceptance_policy
from membership.tests import grant as grant_permissions, pdf
from programs.services import save_program, change_publication, submit_application
from programs.application_workflow import verify
from programs.tests import program_data
from programs.test_approved_terms import TermsHelpers
from programs.workflow import review_photo
from announcements.tests import image_upload
from scripts.durable_test_runner import require_disposable, identity

from . import dataset_methods as methods, vault_services as vault, operational_services as operational
from .operational_models import OperationalRun, OperationalDecision
from .revised import contracts, live_services as policies, live_evidence as evidence, live_math
from .revised.composite_ses import FORMULA
from .revised.live_models import DatasetInputReview
from .weight_input import project


CODES = ('SES', 'ES', 'PA', 'HM')
BASE = datetime(2026, 10, 10, tzinfo=dt_timezone.utc)
NOW = datetime(2026, 10, 27, 4, tzinfo=dt_timezone.utc)
ROWS = (
    ('T01', 'Ana', 'Testalpha', 10000, 1, 'employed', 3, 2),
    ('T02', 'Ben', 'Testbravo', 64000, 0, 'unemployed', 3, 2),
    ('T03', 'Cora', 'Testcharlie', 40000, 0, 'employed', 0, 2),
    ('T04', 'Dan', 'Testdelta', 82000, 0, 'employed', 4, 10),
    ('T05', 'Ella', 'Testecho', 28000, 1, 'employed', 2, 4),
    ('T06', 'Finn', 'Testfoxtrot', 28000, 0, 'employed', 2, 4),
    ('T07', 'Gia', 'Testgolf', 41500, 1, 'employed', 1, 6),
    ('T08', 'Hugo', 'Testhotel', 100000, 1, 'employed', 4, 1),
    ('T09', 'Iris', 'Testindia', 37000, 0, 'employed', 2, 5),
    ('T10', 'Jiro', 'Testjuliet', 37000, 0, 'employed', 2, 5),
    ('T11', 'Kara', 'Testkilo', 51000, 0, 'employed', 1, 7),
    ('T12', 'Luis', 'Testlima', 23500, 0, 'employed', 3, 8),
)
SCENARIOS = {
    'balanced': (2500, 2500, 2500, 2500),
    'ses': (6250, 1250, 1250, 1250),
    'es': (1250, 6250, 1250, 1250),
    'pa': (1250, 1250, 6250, 1250),
    'hm': (1250, 1250, 1250, 6250),
}
EXPECTED_RANKS = (
    (10, 1, 10, 10, 11), (4, 10, 1, 9, 9), (5, 6, 5, 1, 10),
    (11, 11, 11, 11, 1), (6, 3, 6, 4, 7), (9, 5, 9, 7, 8),
    (1, 4, 2, 2, 4), (12, 12, 12, 12, 12), (7, 7, 7, 5, 5),
    (7, 7, 7, 5, 5), (2, 9, 3, 3, 3), (3, 2, 4, 8, 2),
)
# Explicit fixture-only encoding authorized in the request; never production mapping.
TEST_EMPLOYMENT = {'employed': ('Full-Time Worker', 1), 'unemployed': ('Unemployed', 4)}


def proposal(scenario):
    weights = dict(zip(CODES, SCENARIOS[scenario]))
    return {'order': sorted(CODES, key=lambda code: -weights[code]), 'weights': weights}


def oracle(weights):
    """Independent rational formula, with the user's fixed fixture bounds."""
    result = {}
    for label, first, last, income, p, employment, pa, hm in ROWS:
        need = Fraction(100000 - income, 90000)
        normalized = dict(zip(CODES, (need * Fraction(9 + p, 10),
            Fraction(TEST_EMPLOYMENT[employment][1] - 1, 3), Fraction(4 - pa, 4), Fraction(hm - 1, 9))))
        contributions = {code: Fraction(weights[code]) * normalized[code] for code in CODES}
        result[label] = {'normalized': normalized, 'contributions': contributions,
                         'score': 100 * sum(contributions.values()), 'income_need': need}
    for row in result.values():
        row['rank'] = 1 + sum(other['score'] > row['score'] for other in result.values())
    return result


def independent_ahp(judgments):
    matrix = [[Fraction(1) for _ in CODES] for _ in CODES]
    for pair, value in judgments.items():
        a, b = (CODES.index(code) for code in pair.split(':'))
        matrix[a][b], matrix[b][a] = Fraction(value), 1 / Fraction(value)
    totals = [sum(row[j] for row in matrix) for j in range(4)]
    return {code: sum(matrix[i][j] / totals[j] for j in range(4)) / 4 for i, code in enumerate(CODES)}


def math_fixture(scenario, changes=None):
    weights = {code: str(Fraction(value, 10000)) for code, value in zip(CODES, SCENARIOS[scenario])}
    configuration = SimpleNamespace(digest='SYNTHETIC-TWELVE-ONLY',
        policy={'method': methods.COMPOSITE, 'ses_formula': deepcopy(FORMULA)},
        validation={'weights': weights, 'weight_digest': 'SYNTHETIC-TWELVE-WEIGHTS'},
        source={'terms': {'program': {'slots': 12}}},
        dataset_policy=SimpleNamespace(digest='SYNTHETIC-TWELVE-POLICY'), assessment_cutoff=BASE + timedelta(days=1, hours=1))
    eligible = {row[0]: {'inputs': {
        'SES': {'value': str(row[3]), 'household_four_ps': row[4]},
        'ES': {'value': TEST_EMPLOYMENT[row[5]][0]}, 'PA': {'value': str(row[6])},
        'HM': {'value': str(row[7])}}} for row in ROWS}
    if changes:
        changes(eligible)
    return live_math.calculations({'engine': methods.COMPOSITE,
        'configuration_digest': configuration.digest, 'eligible': eligible}, configuration)


class SyntheticTwelveArithmeticTests(SimpleTestCase):
    def test_five_fixed_weight_oracles_against_real_composite_engine(self):
        for index, scenario in enumerate(SCENARIOS):
            expected = oracle({code: Fraction(value, 10000) for code, value in zip(CODES, SCENARIOS[scenario])})
            actual = math_fixture(scenario)
            for i, row in enumerate(ROWS):
                label = row[0]
                with self.subTest(scenario=scenario, member=label):
                    self.assertEqual(expected[label]['rank'], EXPECTED_RANKS[i][index])
                    self.assertEqual(Fraction(actual[label]['score_exact']) * 100, expected[label]['score'])
                    self.assertEqual(actual[label]['comparison']['business_rank'], expected[label]['rank'])
                    for trace in actual[label]['traces']:
                        code = trace['criterion']
                        self.assertEqual(Fraction(trace['normalized']['exact']), expected[label]['normalized'][code])
                        self.assertEqual(Fraction(trace['contribution']['exact']), expected[label]['contributions'][code])
            self.assertEqual(actual['T09']['score_exact'], actual['T10']['score_exact'])
        self.assertEqual(oracle(dict(zip(CODES, [Fraction(1, 4)] * 4)))['T05']['score'] -
                         oracle(dict(zip(CODES, [Fraction(1, 4)] * 4)))['T06']['score'], 2)
        focused = oracle(dict(zip(CODES, (Fraction(5, 8), Fraction(1, 8), Fraction(1, 8), Fraction(1, 8)))))
        self.assertEqual(focused['T05']['score'] - focused['T06']['score'], 5)

    def test_all_five_slider_projections_independently_reproduce_exact_targets(self):
        for scenario, units in SCENARIOS.items():
            judgments, actual, _ = project(proposal(scenario))
            expected = independent_ahp(judgments)
            self.assertEqual(expected, dict(zip(CODES, (Fraction(value, 10000) for value in units))))
            self.assertEqual({code: Fraction(value) for code, value in actual['weights'].items()}, expected)
            self.assertEqual(Fraction(actual['CR']), 0)

    def test_each_constant_numeric_column_blocks_without_redistributing_weights(self):
        for code in CODES:
            def constant(rows):
                for row in rows.values():
                    row['inputs'][code]['value'] = 'Full-Time Worker' if code == 'ES' else '2'
            with self.subTest(code=code), self.assertRaisesMessage(ValidationError, 'Constant-value'):
                math_fixture('balanced', constant)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ExistingRegressionDiagnosisTests(TransactionTestCase):
    """Explain two unchanged legacy-test failures without changing their behavior."""

    def test_historical_policy_needs_explicit_shared_cutoff_to_be_ready(self):
        from .test_document_ranking import DocumentRankingTests
        from .revised.live_models import SharedDatasetPolicy
        DocumentRankingTests.setUp(self)
        data = {'expected': policies.token(), 'weight': self.weights.pk,
                'reason': 'SYNTHETIC investigation of existing regression expectation'}
        for key, entry in self.content['choices'].items():
            if contracts.applicable(self.content, key):
                data[key], data['specified_' + key] = entry['value'], 'on'
        url = reverse('ewaf:dataset_policies')
        self.assertEqual(self.client.post(url, data).status_code, 302)
        draft = SharedDatasetPolicy.objects.first()
        self.assertEqual(contracts.findings(draft.content, draft.weight_snapshot),
            ['C: choose the shared assessment cutoff rule once in the Configuration Vault.'])
        self.assertEqual(self.client.post(url, data | {'expected': policies.token(),
            'shared_cutoff': 'application_close'}).status_code, 302)
        revised = SharedDatasetPolicy.objects.first()
        self.assertEqual(contracts.findings(revised.content, revised.weight_snapshot), [])
        self.assertNotEqual(revised.pk, draft.pk)

    def test_approved_handoff_is_visible_in_detail_and_absent_from_pending_inbox(self):
        require_disposable()
        helper = HandoffHelpers()
        helper.addCleanup, helper.assertTrue = self.addCleanup, self.assertTrue
        helper.setup_handoff()
        intake = helper.make()
        helper.approve(helper.verify(helper.prepare(intake)))
        self.client.force_login(helper.actor)
        self.assertNotContains(self.client.get(reverse('membership:registration_inbox')), 'Membership: Approved')
        page = self.client.get(reverse('membership:registration_detail', args=[intake.reference]))
        self.assertContains(page, 'Open member record')
        completed = self.client.get(reverse('membership:registration_inbox'), {'tab': 'completed'})
        self.assertEqual(completed.context['page_obj'].paginator.count, 1)
        self.assertEqual(Member.objects.count(), 1)


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
    PDAO_ENFORCEMENT_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SyntheticTwelveIntegrationTests(StaticLiveServerTestCase):
    handoff_form = HandoffHelpers.form

    def setUp(self):
        require_disposable()
        self.clock = patch('django.utils.timezone.now', return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        seed_statuses()
        self.actor = self.user = get_user_model().objects.create_superuser('SYNTHETIC-TWELVE-ADMIN', password='synthetic-only')
        self.client.force_login(self.user)
        self.doc_type = DocumentType.objects.create(name='SYNTHETIC reviewed income, household, employment and ledger coverage')
        self.requirement = MembershipDocumentRequirement.objects.create(document_type=self.doc_type)
        DisabilityType.objects.get_or_create(name='Visual Disability')
        MembershipSettings.objects.create(pk=1, prpwd_url='https://registry.example.test/manual')
        self.policy = acceptance_policy() | pdf_policy() | {'onsite_enabled': True, 'handoff_enabled': True}
        self.policy['applicant_profile'] = pdf_policy()['applicant_profile']
        self.options = override_settings(ASSOCIATION_REGISTRATION_POLICY=self.policy)
        self.options.enable()
        self.addCleanup(self.options.disable)
        self.output = Path(os.environ['G12_ARTIFACT_DIR']) / 'synthetic-twelve'
        self.output.mkdir(exist_ok=True)
        self.members, self.apps, self.proofs, self.releases = {}, {}, {}, []

    def observe(self, intake):
        from membership.registration_forms import OnsiteForm
        intake.refresh_from_db()
        form = OnsiteForm(policy=self.policy)
        data = {'version': intake.version, 'reason': 'SYNTHETIC current onsite checklist observations',
                'civil_alternative': 'birth'}
        for key in form.keys:
            data['finding_' + key] = 'sighted'
            data['method_' + key] = self.policy['onsite_methods'][0]
        registration.record_onsite(intake.reference, user=self.user, data=data)

    def register_members(self):
        for i, row in enumerate(ROWS, 1):
            label, first, last, income, p, employment, count, household = row
            data = association_data() | {'first_name': first, 'last_name': last,
                'pwd_number': f'00-0000-000-{i:07d}', 'house_street': f'{i} Fictional Fixture Lane',
                'contact_number': f'0900000{i:04d}', 'email': f'{label.lower()}@example.test',
                'household_monthly_income': str(income), 'four_ps_member': 'Yes' if p else 'No',
                'employment_status': employment, 'household_members': str(household),
                'family_members': str(household)}
            binding = registration.binding_for('SYNTHETIC-ONSITE-' + label)
            context = registration.issue_context(binding, channel='walk_in', user=self.user)
            intake = registration.submit_registration(context.pk, binding, data, channel='walk_in', user=self.user)
            registration.review_registration(intake.reference, user=self.user, version=intake.version,
                action='begin_review', reason='SYNTHETIC onsite five-item intake review')
            self.observe(intake)
            form = self.handoff_form(intake, control_number=f'SYNTH-EWAF-20261027-{i:03d}')
            application = registration.handoff_registration(intake.reference, user=self.user, form=form)
            application = membership_services.record_verification(application.reference, user=self.user,
                version=application.version, verified=True,
                notes='SYNTHETIC simulated manual PRPWD outcome; no government record or external access.')
            membership_services.decide_application(application.reference, user=self.user, version=application.version,
                decision='approved', notes='SYNTHETIC completed onsite requirements and manual review only.')
            member = Member.objects.get(application=application)
            self.assertNotEqual(member.control_number, label)
            self.assertEqual(member.full_name, first + ' ' + last)
            self.assertEqual(member.household_monthly_income, income)
            self.assertEqual(member.household_members, household)
            self.assertEqual(member.employment_status, employment)
            self.assertEqual(member.registration_profile['four_ps_member'], 'Yes' if p else 'No')
            document = application.documents.get(requirement=self.requirement)
            proof = verify_document(document.pk, user=self.user, member_version=member.version,
                verified=True, expires_on=None, reason='SYNTHETIC evidence and complete history coverage review')
            self.members[label], self.proofs[label] = member, proof
        self.assertEqual(Member.objects.count(), 12)
        # Unequal optional document counts must not break the T09/T10 score tie.
        kind = DocumentType.objects.create(name='SYNTHETIC optional indigency evidence')
        optional = MembershipDocumentRequirement.objects.create(document_type=kind, is_required=False)
        document = MembershipApplicationDocument.objects.create(application=self.members['T09'].application,
            requirement=optional, label='SYNTHETIC optional document, never a scoring bonus',
            file=pdf(), content_type='application/pdf', size=50)
        verify_document(document.pk, user=self.user, member_version=self.members['T09'].version,
            verified=True, expires_on=None, reason='SYNTHETIC optional evidence review')
        self.assertEqual(self.members['T09'].application.documents.count(), 2)
        self.assertEqual(self.members['T10'].application.documents.count(), 1)

    def program(self, name, *, ewaf, opens, closes):
        program = save_program(user=self.user, data=program_data(name=name, benefit='SYNTHETIC delivered support',
            slots=12, ewaf_applicable=ewaf, registration_opens_at=opens, registration_closes_at=closes,
            selection_method='SYNTHETIC reviewed ' + ('EWAF with separate human selection' if ewaf else 'committee selection')))
        change_publication(program.pk, user=self.user, version=program.version,
            action='authorize_policy', notes='SYNTHETIC program authorization only')
        program.refresh_from_db()
        terms = TermsHelpers()
        terms.program, terms.officer = program, self.user
        terms.reconcile()
        return program

    def publish(self, program):
        change_publication(program.pk, user=self.user, version=program.version,
            action='published', notes='SYNTHETIC isolated intake; no public deployment or results')
        program.refresh_from_db()

    def apply(self, program, member):
        grant, outcome, _ = verify(program.pk, version=program.version, control_number=member.control_number,
            full_name=member.full_name, birthdate=member.birthdate, contact_number=member.contact_number)
        self.assertEqual(outcome, 'passed')
        app = submit_application(program.pk, grant=grant,
            data={'version': program.version, 'applicant_name': member.full_name,
                'applicant_contact': member.contact_number, 'applicant_email': member.email,
                'pwd_id_number': member.registration_profile['pwd_number'], 'current_information': 'unchanged',
                'change_details': '', 'confirm_information': True},
            files=MultiValueDict({'calendar_photo': [image_upload()]}))
        review_photo(app.pk, user=self.user, data={'version': app.version, 'photo_id': app.current_photo_id,
            'outcome': 'VERIFIED', 'reason': 'SYNTHETIC accepted identity evidence', 'confirm': True})
        review_eligibility(app.pk, user=self.user, data=review_data(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'ELIGIBLE')
        return app

    def history(self):
        for batch in range(4):
            day = BASE - timedelta(days=12 - batch * 2)
            with patch('django.utils.timezone.now', return_value=day):
                program = self.program(f'SYNTHETIC prior delivery batch {batch + 1}', ewaf=False,
                    opens=day + timedelta(hours=1), closes=day + timedelta(hours=3))
                self.publish(program)
            apps = []
            with patch('django.utils.timezone.now', return_value=day + timedelta(hours=2)):
                for row in ROWS:
                    if row[6] > batch:
                        apps.append(self.apply(program, self.members[row[0]]))
            with patch('django.utils.timezone.now', return_value=day + timedelta(hours=4)):
                for app in apps:
                    decide_assistance(app.pk, user=self.user, data=decision_data(app))
                    self.releases.append(record_release(app.pk, user=self.user, data=release_data(app,
                        reference=f'SYNTHETIC-RELEASE-{batch + 1}-{app.member_id}',
                        notes='SYNTHETIC confirmed delivery, not an application or selection count')))
        self.assertEqual(AssistanceRelease.objects.filter(voided_at__isnull=True).count(), 27)
        for release in self.releases:
            self.assertIsNone(release.voided_at)
            self.assertLess(release.recorded_at, BASE)
            self.assertLess(release.released_on, BASE.date())
            self.assertEqual(release.application.status, 'COMPLETED')

    def save_weights(self, scenario):
        retained = []
        # Save all five independent versions; leave the tested vector active last.
        for name in [key for key in SCENARIOS if key != scenario] + [scenario]:
            for status in ('DRAFT', 'LOCKED'):
                self.weights = vault.record_ses_weights(user=self.user, expected=vault.token(),
                    proposal=proposal(name), reason='SYNTHETIC twelve-member ' + name,
                    status=status, method=methods.COMPOSITE)
            retained.append((self.weights.pk, deepcopy(self.weights.payload())))
        self.retained_weights = retained

    def bind(self):
        content = contracts.initial_content(methods.COMPOSITE)
        for key, (_, _, kind) in contracts.specifications(content).items():
            if isinstance(kind, dict):
                value = next(iter(kind))
            elif kind == 'documents':
                value = [self.doc_type.pk]
            elif kind == 'integer':
                value = {'evidence_max_age_days': 90, 'pa_months': 12}.get(key, 3)
            elif kind == 'datetime':
                value = (BASE - timedelta(days=30) if key == 'effective_from' else NOW + timedelta(days=60)).isoformat()
            else:
                value = 'SYNTHETIC authorized test procedure for ' + key + '; not institutional policy.'
            content['choices'][key] = {'value': value, 'specified': True}
        draft = policies.save_draft(user=self.user, expected=policies.token(), content=content,
            weight_id=self.weights.pk, reason='SYNTHETIC fixture-only policy')
        policy = policies.approve(draft.pk, user=self.user, expected=draft.digest,
            reviewed_groups=['A', 'B', 'C'], reason='SYNTHETIC fixture approval, never operational authorization')
        self.configuration = policies.bind(self.target.pk, user=self.user,
            expected=operational.configuration_token(self.target), policy_id=policy.pk,
            cutoff=BASE + timedelta(days=1, hours=1), reason='SYNTHETIC immutable scenario binding')

    def findings(self, label):
        member = self.members[label]
        return {**evidence.periods(self.configuration),
            'income_monthly': [str(member.household_monthly_income)] * 3,
            'employment': TEST_EMPLOYMENT[member.employment_status][0],
            'household_members': member.household_members, 'history_complete': True,
            'assessment_finding': 'SYNTHETIC reviewed registered inputs; complete 12-month ledger coverage. '
                'Test-only accepted ES: Employed=1, Unemployed=4. No production mapping.',
            'income_consistency': 'consistent', 'income_resolution': '',
            'household_four_ps': member.registration_profile['four_ps_member'] == 'Yes',
            'four_ps_household_confirmed': True,
            'four_ps_household_review': 'SYNTHETIC accepted household relationship and Yes/No finding; no genuine 4Ps verification.'}

    def accept(self, label, **changes):
        app = self.apps[label]
        return evidence.record(app.pk, user=self.user, expected=evidence.review_token(app, self.configuration),
            findings=self.findings(label) | changes,
            selections={code: [self.proofs[label].pk] for code in CODES}, state='ACCEPTED',
            reason='SYNTHETIC explicit accepted numerical assessment', confirmed=True)

    def generate(self):
        return operational.generate(self.target.pk, user=self.user,
            expected=operational.context(self.target.pk, user=self.user), request_key=uuid4(),
            reason='SYNTHETIC complete frozen T01-T12 pool')

    def build(self, scenario):
        with patch('django.utils.timezone.now', return_value=BASE - timedelta(days=20)):
            self.register_members()
        self.history()
        with patch('django.utils.timezone.now', return_value=BASE):
            self.save_weights(scenario)
            self.target = self.program('SYNTHETIC T01-T12 ' + scenario, ewaf=True,
                opens=BASE + timedelta(hours=1), closes=BASE + timedelta(days=1))
            self.bind()
            self.publish(self.target)
        with patch('django.utils.timezone.now', return_value=BASE + timedelta(hours=2)):
            for label in self.members:
                self.apps[label] = self.apply(self.target, self.members[label])
        for row in ROWS:
            accepted = self.accept(row[0])
            self.assertEqual(int(accepted.inputs['PA']['value']), row[6])
            self.assertEqual(len(accepted.inputs['PA']['release_ids']), row[6])
        self.assertEqual(self.target.applications.count(), 12)

    def check_scenario(self, scenario):
        self.build(scenario)
        expected = oracle(independent_ahp(self.weights.judgments))
        # The Admin POST is the actual generation route, not a separate calculator.
        response = self.client.post(reverse('ewaf:operational_workspace', args=[self.target.pk]), {
            'action': 'GENERATE', 'expected': json.dumps(operational.context(self.target.pk, user=self.user)),
            'request_key': str(uuid4()), 'reason': 'SYNTHETIC Admin ranking test'})
        self.assertEqual(response.status_code, 302)
        run = OperationalRun.objects.get(program=self.target)
        run.clean()
        self.assertEqual(run.snapshot['engine'], methods.COMPOSITE)
        self.assertEqual(len(run.snapshot['eligible']), 12)
        actual = {}
        for row in ROWS:
            label = row[0]
            key = str(self.apps[label].pk)
            result = run.calculations[key]
            self.assertEqual(Fraction(result['score_exact']) * 100, expected[label]['score'])
            self.assertEqual(result['comparison']['business_rank'], expected[label]['rank'])
            self.assertEqual(expected[label]['rank'], EXPECTED_RANKS[int(label[1:]) - 1][list(SCENARIOS).index(scenario)])
            for trace in result['traces']:
                self.assertEqual(Fraction(trace['normalized']['exact']), expected[label]['normalized'][trace['criterion']])
                self.assertEqual(Fraction(trace['contribution']['exact']), expected[label]['contributions'][trace['criterion']])
            actual[label] = {'name': row[1] + ' ' + row[2], 'member_id': self.members[label].pk,
                'control_number': self.members[label].control_number, 'application_id': key,
                'registered': self.members[label].registration_profile,
                'document_count': self.members[label].application.documents.count(),
                'accepted': run.snapshot['eligible'][key], 'calculation': result,
                'expected_score_100_exact': str(expected[label]['score']), 'expected_rank': expected[label]['rank']}
        self.assertEqual(actual['T09']['calculation']['score_exact'], actual['T10']['calculation']['score_exact'])
        self.assertEqual(expected['T08']['income_need'], 0)
        self.assertEqual(expected['T08']['normalized']['SES'], 0)
        self.assertFalse(OperationalDecision.objects.filter(program=self.target).exists())
        from .vault_models import VaultRevision
        for pk, payload in self.retained_weights:
            retained = VaultRevision.objects.get(pk=pk)
            retained.clean()
            self.assertEqual(retained.payload(), payload)
        export = self.client.get(reverse('ewaf:operational_export', args=[self.target.pk, run.pk]))
        self.assertEqual(export.status_code, 200)
        self.assertIn('no-store', export['Cache-Control'])
        result = {'scenario': scenario, 'database': identity(), 'program_id': str(self.target.pk),
            'cutoff': self.configuration.assessment_cutoff.isoformat(), 'periods': evidence.periods(self.configuration),
            'proposal': proposal(scenario), 'calculated_weights': self.weights.validation['weights'],
            'judgments': self.weights.judgments, 'consistency': self.weights.validation,
            'vault_version_ids': [pk for pk, _ in self.retained_weights],
            'configuration_id': self.configuration.pk, 'run_id': run.pk, 'run_digest': run.digest,
            'release_count': 27, 'rows': actual}
        self.browser(scenario, run)
        if scenario == 'balanced':
            result['edge_checks'] = self.edge_checks(run)
        self.output.joinpath(scenario + '.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')

    def browser(self, scenario, run):
        root = Path(__file__).resolve().parents[1]
        process = subprocess.run(['node', str(root / 'scripts/ewaf_synthetic_twelve_browser.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                'QA_SESSION': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                'QA_PROGRAM': str(self.target.pk), 'QA_SCENARIO': scenario, 'QA_OUTPUT': str(self.output),
                'QA_PROPOSAL': json.dumps(proposal(scenario)),
                'QA_EXPECTED': json.dumps({self.members[label].full_name: {
                    'score': run.calculations[str(app.pk)]['score_display'],
                    'rank': run.calculations[str(app.pk)]['comparison']['business_rank']}
                    for label, app in self.apps.items()})},
            capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        print(process.stdout)

    def edge_checks(self, run):
        checks = []
        app = self.apps['T03']
        before = DatasetInputReview.objects.count()
        invalid = [dict(income_monthly=[]), dict(household_four_ps=None), dict(household_four_ps='unverified'),
            dict(four_ps_household_confirmed=False), dict(employment='Employed'),
            dict(employment='Self-employed'), dict(employment='Student'), dict(employment='Retired'),
            dict(history_complete=False), dict(household_members=None), dict(household_members=0),
            dict(household_members=-1), dict(household_members=1.5)]
        for change in invalid:
            with self.subTest(invalid=change), self.assertRaises(ValidationError):
                self.accept('T03', **change)
            self.assertEqual(DatasetInputReview.objects.count(), before)
        checks.append('13 invalid/unresolved accepted-input variants rejected without a saved review')
        for state in ('NEEDS_REVIEW', 'DISPUTED'):
            evidence.record(app.pk, user=self.user, expected=evidence.review_token(app, self.configuration),
                findings=self.findings('T03') | {'household_four_ps': None}, selections={}, state=state,
                reason='SYNTHETIC unresolved 4Ps must block the whole pool', confirmed=True)
            with self.assertRaises(ValidationError):
                self.generate()
            self.accept('T03')
        checks.append('Needs Review and Disputed input states block official complete-pool calculation')
        from programs.models import ProgramLog
        counts = (DatasetInputReview.objects.count(), OperationalRun.objects.count(), ProgramLog.objects.count())
        with patch.object(ProgramLog.objects, 'create', side_effect=RuntimeError('SYNTHETIC audit outage')):
            with self.assertRaises(RuntimeError):
                self.accept('T03')
            with self.assertRaises(RuntimeError):
                self.generate()
        self.assertEqual((DatasetInputReview.objects.count(), OperationalRun.objects.count(), ProgramLog.objects.count()), counts)
        checks.append('Evidence and complete-pool calculation roll back atomically on audit failure')
        with patch('django.utils.timezone.now', return_value=BASE + timedelta(hours=2)):
            with self.assertRaises(ValidationError):
                self.generate()
        with patch('django.utils.timezone.now', return_value=BASE + timedelta(days=1, minutes=30)):
            with self.assertRaises(ValidationError):
                self.generate()
        checks.append('Generation blocked both before program close and between close and assessment cutoff')
        limited = get_user_model().objects.create_user('SYNTHETIC-UNAUTHORIZED-STAFF', is_staff=True)
        grant_permissions(limited, 'accounts.access_dashboard')
        denied = Client()
        denied.force_login(limited)
        for route in (reverse('ewaf:operational_workspace', args=[self.target.pk]),
                      reverse('ewaf:dataset_inputs', args=[app.pk]),
                      reverse('ewaf:operational_export', args=[self.target.pk, run.pk]),
                      reverse('membership:document', args=[self.proofs['T03'].document_id]),
                      reverse('ewaf:operational_breakdown', args=[self.target.pk])):
            self.assertEqual(denied.get(route).status_code, 403)
        with self.assertRaises(PermissionDenied):
            operational.generate(self.target.pk, user=limited, expected={}, request_key=uuid4(), reason='SYNTHETIC denied')
        with self.assertRaises(PermissionDenied):
            evidence.record(app.pk, user=limited, expected=evidence.review_token(app, self.configuration),
                findings=self.findings('T03'), selections={code: [self.proofs['T03'].pk] for code in CODES},
                state='ACCEPTED', reason='SYNTHETIC denied', confirmed=True)
        checks.append('Restricted staff denied private ranking, evidence, breakdown, export and protected services')
        self.assertEqual(Client().get('/media/' + self.proofs['T03'].document.file.name).status_code, 404)
        self.assertIn(Client().get(reverse('membership:document', args=[self.proofs['T03'].document_id])).status_code, (302, 403))
        checks.append('No unrestricted media route; anonymous private attachment retrieval denied')
        retained = deepcopy(run.payload())
        release = next(row for row in self.releases if row.application.member_id == self.members['T01'].pk)
        history_app = release.application
        history_app.refresh_from_db()
        void_release(history_app.pk, release.pk, user=self.user,
            data={'version': history_app.version, 'notes': 'SYNTHETIC ledger mutation test only', 'confirm': True})
        with self.assertRaises(ValidationError):
            self.generate()
        accepted = self.accept('T01')
        self.assertEqual(accepted.inputs['PA']['value'], '2')
        changed = self.generate()
        self.assertNotEqual(changed.calculations[str(self.apps['T01'].pk)]['score_exact'],
                            run.calculations[str(self.apps['T01'].pk)]['score_exact'])
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)
        checks.append('Reasoned release void changes T01 ledger PA 3 to 2 after re-review; full new run; prior run unchanged')
        checks.append('Next scenario rebuilds the original 27 releases through fresh test isolation')
        return checks

    def test_balanced(self):
        self.check_scenario('balanced')

    def test_ses(self):
        self.check_scenario('ses')

    def test_es(self):
        self.check_scenario('es')

    def test_pa(self):
        self.check_scenario('pa')

    def test_hm(self):
        self.check_scenario('hm')
