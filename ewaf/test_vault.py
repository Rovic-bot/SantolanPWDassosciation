"""Synthetic vault rules are test fixtures, never live policy defaults."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from documents.models import DocumentType
from programs.models import Program, ProgramLog
from programs.tests import program_data
from programs.services import save_program, change_publication
from .household_criteria import CRITERIA, PAIRS, SOURCES
from .vault_models import VaultRevision, RegisteredInputReview
from .operational_models import OperationalConfiguration
from . import vault_services as vault, vault_sources, operational_services as operational
from .vault_policy import CONTRACT
from .dataset_methods import HOUSEHOLD
from .operational_testsupport import OperationalHelpers


def proposal(document_type):
    now = timezone.now()
    value = dict(source_contract=CONTRACT, authority_reference='FICTIONAL TEST ONLY',
        authorized_scope='Synthetic shared policy for new test programs', approval_date=str(now.date() - timedelta(days=3)),
        effective_from=(now - timedelta(days=2)).isoformat(), effective_until=(now + timedelta(days=10)).isoformat(),
        assessment_start=str(timezone.localdate() - timedelta(days=30)), assessment_end=str(timezone.localdate()),
        selection_rule='reasoned_human_within_slots', tie_rule='hold', tie_procedure='Synthetic hold for human review',
        classification_mode='none', classifications=None, edge_cases='block', pa_scope='all_programs',
        pa_period='all_retained', pa_start=None, pa_end=None, eligibility={}, criteria={})
    for code, lower, upper, direction, encoding, kind, unit in (
        ('HI', '0', '2000', 'inverse', None, 'decimal', 'PHP/month'),
        ('SI', '0', '1', 'benefit', {'Yes': '1', 'No': '0'}, 'category', 'category'),
        ('ES', '0', '1', 'benefit', {'unemployed': '1'}, 'category', 'category'),
        ('PA', '0', '4', 'inverse', None, 'integer', 'records'),
        ('HM', '1', '7', 'benefit', None, 'integer', 'persons')):
        value['criteria'][code] = dict(measure='Synthetic ' + code, source_type=SOURCES[code], value_type=kind,
            unit=unit, direction=direction, encoding=encoding, bounds={'method': 'fixed', 'lower': lower, 'upper': upper},
            observation_period='Synthetic reviewed period', edge_cases='block')
        if code != 'PA':
            value['criteria'][code]['evidence_document_types'] = [document_type]
    return value


@override_settings(EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class VaultTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('synthetic-vault', password='synthetic-only')
        self.document_type = DocumentType.objects.create(name='Synthetic accepted household evidence')
        self.proposal = proposal(self.document_type.pk)
        self.pairs = dict.fromkeys(PAIRS, '1')

    def record(self, **changes):
        return vault.record(**dict(user=self.admin, expected=vault.token(), proposed=self.proposal,
            judgments=self.pairs, status='LOCKED', reason='Synthetic explicit shared policy approval', attested=True) | changes)

    def program(self, **changes):
        return save_program(user=self.admin, data=program_data(benefit='Synthetic purpose', ewaf_applicable=True, **changes))

    def test_new_programs_inherit_shared_version_and_publish_without_weight_entry(self):
        revision = self.record()
        program = self.program()
        assigned = OperationalConfiguration.objects.get(program=program)
        self.assertEqual(assigned.vault_revision_id, revision.pk)
        self.assertEqual(assigned.status, 'DRAFT')
        change_publication(program.pk, user=self.admin, version=program.version, action='published')
        program.refresh_from_db()
        current = operational.latest_configuration(program)
        from programs.application_workflow import publication_configuration_problem
        self.assertEqual(publication_configuration_problem(program), '')
        self.assertEqual(current.vault_revision_id, revision.pk)
        self.assertEqual(current.policy, revision.policy)
        self.assertEqual(current.judgments, revision.judgments)
        self.assertEqual(OperationalConfiguration.objects.get(pk=assigned.pk).status, 'DRAFT')

    def test_draft_without_vault_can_be_created_and_is_assigned_when_vault_is_approved(self):
        program = self.program()
        self.assertFalse(OperationalConfiguration.objects.filter(program=program).exists())
        self.record(status='DRAFT', attested=False)
        self.assertIsNone(vault.active())
        revision = self.record()
        self.assertEqual(OperationalConfiguration.objects.get(program=program).vault_revision_id, revision.pk)

    def test_new_versions_do_not_rewrite_existing_program_configuration(self):
        first = self.record()
        old = self.program(name='Synthetic earlier program')
        retained = OperationalConfiguration.objects.get(program=old).payload()
        self.proposal['criteria']['HI']['bounds']['upper'] = '3000'
        second = self.record()
        newer = self.program(name='Synthetic later program')
        self.assertEqual(OperationalConfiguration.objects.get(program=old).payload(), retained)
        self.assertEqual(OperationalConfiguration.objects.get(program=newer).vault_revision_id, second.pk)
        first.refresh_from_db()
        first.clean()
        self.assertEqual(first.policy['criteria']['HI']['bounds']['upper'], '2000')

    def test_incomplete_and_unattested_policies_cannot_be_activated(self):
        self.record(status='DRAFT', proposed={'criteria': {}}, judgments={})
        self.assertIsNone(vault.active())
        with self.assertRaises(ValidationError):
            self.record(attested=False)
        bad = deepcopy(self.proposal)
        bad['criteria']['HI']['bounds'] = {'lower': '10', 'upper': '10'}
        with self.assertRaises(ValidationError):
            self.record(proposed=bad)
        self.assertEqual(VaultRevision.objects.count(), 1)

    def test_stale_writes_permissions_and_audit_failure_leave_no_revision(self):
        stale = vault.token()
        self.record()
        with self.assertRaises(ValidationError):
            self.record(expected=stale)
        viewer = get_user_model().objects.create_user('synthetic-no-vault', is_staff=True)
        with self.assertRaises(PermissionDenied):
            self.record(user=viewer)
        with patch.object(LogEntry.objects, 'create', side_effect=RuntimeError('Synthetic failed audit')):
            with self.assertRaises(RuntimeError):
                self.record()
        self.assertEqual(VaultRevision.objects.count(), 1)

    def test_vault_and_inherited_configuration_are_append_only_and_exact(self):
        revision = self.record()
        with self.assertRaises(ValidationError):
            VaultRevision.objects.filter(pk=revision.pk).update(reason='overwrite')
        with self.assertRaises(ValidationError):
            revision.delete()
        program = self.program()
        config = OperationalConfiguration.objects.get(program=program)
        config.policy = deepcopy(config.policy)
        config.policy['criteria']['HI']['bounds']['upper'] = '999'
        with self.assertRaises(ValidationError):
            config.clean()
        with self.assertRaisesMessage(ValidationError, 'Configuration Vault'):
            operational.record_configuration(program.pk, user=self.admin, expected='', proposed={}, judgments={},
                status='DRAFT', reason='Synthetic direct attempt')

    def test_vault_is_only_weight_editor_and_program_cards_have_no_weight_rows(self):
        self.client.force_login(self.admin)
        self.record()
        program = self.program()
        page = self.client.get(reverse('ewaf:operational_programs'))
        self.assertContains(page, 'Configuration Vault')
        self.assertNotContains(page, 'ewaf-card-weights')
        page = self.client.get(reverse('ewaf:operational_workspace', args=[program.pk]))
        self.assertNotContains(page, 'ewaf-configuration-form')
        self.assertNotContains(page, 'Shared configuration')
        self.assertEqual(page.context['configuration'].vault_revision_id, vault.active().pk)
        self.assertContains(self.client.get(reverse('ewaf:vault')), 'Approve &amp; Save Configuration')
        response = self.client.post(reverse('ewaf:operational_workspace', args=[program.pk]), {'action': 'LOCKED'})
        self.assertEqual(response.status_code, 400)

    def test_future_vault_version_does_not_replace_current_active_version(self):
        first = self.record()
        self.proposal['effective_from'] = (timezone.now() + timedelta(days=1)).isoformat()
        self.record()
        self.assertEqual(vault.active().pk, first.pk)

    def test_one_click_retains_approved_rules_and_ignores_posted_source_overrides(self):
        from .vault_forms import VaultForm
        initial = self.record()
        form = VaultForm(configuration=initial, initial={'expected': vault.token()})
        data = {name: form[name].value() for name in form.fields if form[name].value() is not None}
        data.update(action='LOCKED', HI_source_type='monthly_income', HI_upper='999999',
                    selection_rule='automatic', reason='Forged reason', attested=False)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('ewaf:vault'), data)
        self.assertRedirects(response, reverse('ewaf:vault'))
        row = vault.active()
        self.assertEqual(row.policy['criteria']['HI']['source_type'], 'household_monthly_income')
        self.assertEqual(row.policy['assessment_end'], self.proposal['assessment_end'])
        self.assertEqual({key: value for key, value in row.policy.items() if key != 'weight_input'}, self.proposal)
        self.assertNotEqual(row.reason, 'Forged reason')
        initial.refresh_from_db()
        initial.clean()

    def test_empty_vault_approves_weights_and_sources_without_policy_fields(self):
        from .vault_forms import VaultForm
        from .vault_policy import source_policy, scoring_pending, SCORING_PENDING_MESSAGE
        from programs.application_workflow import publication_configuration_problem, require_publication_policy
        self.client.force_login(self.admin)
        page = self.client.get(reverse('ewaf:vault'))
        self.assertContains(page, 'name="reason"')
        for text in ('Authority and selection policy', 'name="authority_reference"',
                     'name="attested"', 'name="HI_upper"', 'name="SI_encoding"',
                     'name="assessment_end"', 'name="accept_derived_weights"', 'Save vault draft'):
            self.assertNotContains(page, text)
        form = VaultForm(initial={'expected': vault.token()})
        response = self.client.post(reverse('ewaf:vault'),
            {name: form[name].value() for name in form.fields} | {'action': 'LOCKED'})
        self.assertRedirects(response, reverse('ewaf:vault'))
        from django.contrib.messages import get_messages
        self.assertIn(SCORING_PENDING_MESSAGE, [str(message) for message in get_messages(response.wsgi_request)])
        row = vault.active()
        row.clean()
        self.assertTrue(scoring_pending(row.policy))
        self.assertEqual(row.actor, self.admin)
        self.assertEqual({key: value for key, value in row.policy.items() if key != 'weight_input'}, source_policy())
        self.assertContains(self.client.get(reverse('ewaf:vault') + '?method=' + HOUSEHOLD), 'Scoring is pending approved calculation rules')
        program = self.program()
        self.assertEqual(OperationalConfiguration.objects.get(program=program).vault_revision, row)
        change_publication(program.pk, user=self.admin, version=program.version,
            action='authorize_policy', notes='Synthetic program approval without scoring rules')
        program.refresh_from_db()
        self.assertEqual(publication_configuration_problem(program), '')
        page = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertEqual(page.context['detail_ewaf']['source'], f'Shared vault revision {row.revision}')
        self.assertTrue(page.context['detail_ewaf']['configured'])
        require_publication_policy(program)
        retained = row.payload()
        change_publication(program.pk, user=self.admin, version=program.version,
            action='published', notes='Synthetic approved-weights publication')
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        row.refresh_from_db()
        self.assertEqual(row.payload(), retained)
        vault.prepare_publication(program, user=self.admin)
        with self.assertRaises(ValidationError):
            operational.latest_configuration(program)
        from .operational_policy import validate
        with self.assertRaisesMessage(ValidationError, 'Scoring is pending'):
            validate(row.policy, row.judgments)

    def test_one_click_rejects_invalid_weights_stale_requests_and_unauthorized_staff(self):
        import json
        from django.contrib.auth.models import Permission
        from .weight_input import initial_state
        self.client.force_login(self.admin)
        data = {'expected': vault.token(), 'action': 'LOCKED',
                'slider_proposal': json.dumps(initial_state(None)['proposal'])}
        invalid = self.client.post(reverse('ewaf:vault'), data | {'slider_proposal': '{}'})
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(VaultRevision.objects.exists())
        self.assertRedirects(self.client.post(reverse('ewaf:vault'), data), reverse('ewaf:vault'))
        self.assertContains(self.client.post(reverse('ewaf:vault'), data), 'The vault changed')
        configurator = get_user_model().objects.create_user('synthetic-configurator', is_staff=True)
        configurator.user_permissions.add(Permission.objects.get(codename='configure_operational'))
        self.client.force_login(configurator)
        self.assertEqual(self.client.post(reverse('ewaf:vault'), data).status_code, 403)
        self.assertEqual(VaultRevision.objects.count(), 1)

    def test_one_click_audit_failure_rolls_back_and_unapproved_draft_rules_are_not_adopted(self):
        from .weight_input import initial_state
        self.record(status='DRAFT', attested=False)
        with patch.object(LogEntry.objects, 'create', side_effect=RuntimeError('Synthetic failed audit')):
            with self.assertRaises(RuntimeError):
                vault.approve(user=self.admin, expected=vault.token(), proposal=initial_state(None)['proposal'])
        self.assertEqual(VaultRevision.objects.count(), 1)
        row = vault.approve(user=self.admin, expected=vault.token(), proposal=initial_state(None)['proposal'])
        self.assertNotIn('bounds', row.policy['criteria']['HI'])
        self.assertNotIn('encoding', row.policy['criteria']['SI'])


@override_settings(EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class RegisteredInputTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()
        Program.objects.filter(pk=self.program.pk).update(policy_authorized_at=None, policy_authorized_by=None)
        self.program.refresh_from_db()
        change_publication(self.program.pk, user=self.officer, version=self.program.version,
            action='authorize_policy', notes='Synthetic explicit program policy authorization')
        self.program.refresh_from_db()
        self.member.household_monthly_income = Decimal('1000')
        self.member.household_members = 4
        self.member.employment_status = 'unemployed'
        self.member.registration_profile = {'four_ps_member': 'Yes'}
        self.member.version += 1
        self.member.save()
        from documents.services import verify_document
        self.accepted_document = verify_document(self.criterion_documents['SI'].pk, user=self.officer,
            member_version=self.member.version, verified=True, expires_on=None, reason='Synthetic accepted registered evidence')
        from programs.testsupport import verified_photo
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        self.application.refresh_from_db()
        verified_photo(self.application)
        review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application,
            **{f'check_{row.pk}': 'pass' for row in self.relevance_requirements}))
        self.application.refresh_from_db()
        self.proposal = proposal(self.accepted_document.document.requirement.document_type_id)
        vault.record(user=self.officer, expected=vault.token(), proposed=self.proposal, judgments=dict.fromkeys(PAIRS, '1'),
            status='LOCKED', reason='Synthetic shared rules for accepted household inputs', attested=True)
        vault.inherit(self.program, user=self.officer)
        vault.prepare_publication(self.program, user=self.officer)
        self.configuration = operational.latest_configuration(self.program)

    def review(self, **changes):
        return vault_sources.record_review(self.application.pk, **dict(user=self.officer,
            expected=vault_sources.review_token(self.application, self.configuration),
            supporting_review_ids={code: [self.accepted_document.pk] for code in CRITERIA if code != 'PA'},
            observation_start=timezone.localdate(), observation_end=timezone.localdate(),
            reason='Synthetic human acceptance of registered household evidence', confirmed=True) | changes)

    def test_verified_registered_values_calculate_without_changing_member_or_selecting(self):
        from members.models import Member
        before = Member.objects.values().get(pk=self.member.pk)
        rows, _, problems = operational.inventory(self.program, [self.application], self.configuration)
        self.assertTrue(problems)
        review = self.review()
        self.assertEqual(review.source['inputs']['HI']['value'], '1000.00')
        self.assertEqual(review.source['inputs']['SI']['value'], 'Yes')
        self.assertEqual(review.source['inputs']['HM']['value'], 4)
        self.assertEqual(review.source['inputs']['PA']['value'], 0)
        run = self.calculate()
        run.clean()
        self.assertEqual(Decimal(run.calculations[str(self.application.pk)]['score_0_100']), Decimal('80'))
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'ELIGIBLE')

    def test_changed_registered_value_invalidates_review_and_cannot_be_overridden(self):
        self.review()
        from members.models import Member
        Member.objects.filter(pk=self.member.pk).update(household_monthly_income='1500')
        self.application.member.refresh_from_db()
        _, accepted, problems = operational.inventory(self.program, [self.application], self.configuration)
        self.assertFalse(accepted)
        self.assertTrue(any('changed' in issue for issue in problems))

    def test_stale_review_evidence_wrong_owner_and_cutoff_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.review(expected='stale')
        with self.assertRaises(ValidationError):
            self.review(supporting_review_ids={code: [] for code in CRITERIA if code != 'PA'})
        with self.assertRaises(ValidationError):
            self.review(observation_end=timezone.localdate() + timedelta(days=1))
        self.assertFalse(RegisteredInputReview.objects.exists())

    def test_review_audit_failure_rolls_back_and_source_page_has_read_only_values(self):
        with patch.object(ProgramLog.objects, 'create', side_effect=RuntimeError('Synthetic failed audit')):
            with self.assertRaises(RuntimeError):
                self.review()
        self.assertFalse(RegisteredInputReview.objects.exists())
        self.client.force_login(self.officer)
        response = self.client.get(reverse('ewaf:registered_review', args=[self.application.pk]))
        self.assertContains(response, 'Current source values')
        self.assertNotContains(response, 'name="household_monthly_income"')

    def test_assistance_is_counted_only_after_confirmed_release_and_excludes_voids(self):
        from assistance.services import record_release, void_release
        from assistance.tests import release_data
        from .evidence import source_context
        self.review()
        run = self.calculate()
        self.choose(run)
        def count():
            return vault_sources.sources(self.application, self.configuration,
                source_context(self.application))['inputs']['PA']['value']
        self.assertEqual(count(), 0)
        receipt = record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        self.application.refresh_from_db()
        self.assertEqual(count(), 1)
        void_release(self.application.pk, receipt.pk, user=self.officer,
            data={'version': self.application.version, 'notes': 'Synthetic void of receipt', 'confirm': True})
        self.application.refresh_from_db()
        self.assertEqual(count(), 0)


@override_settings(EWAF_VAULT_ENABLED=True)
class VaultConcurrencyTests(TransactionTestCase):
    def test_concurrent_vault_saves_have_one_successful_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from programs.models import ProgramTermsLock
        ProgramTermsLock.objects.get_or_create(pk=1)
        admin = get_user_model().objects.create_superuser('synthetic-concurrent-vault', password='synthetic-only')
        expected = vault.token()
        barrier = Barrier(2)
        def save():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    vault.record(user=admin, expected=expected, proposed={'criteria': {}}, judgments={},
                        status='DRAFT', reason='Synthetic concurrent vault draft')
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: save(), range(2)))
        self.assertCountEqual(results, ['saved', 'stale'])
        self.assertEqual(VaultRevision.objects.count(), 1)
