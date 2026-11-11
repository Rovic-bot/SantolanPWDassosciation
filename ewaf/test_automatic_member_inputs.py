"""Automatic record sources, immutable calculation snapshots and no input review."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TransactionTestCase, override_settings, Client
from django.urls import reverse

from members.tests import create_member
from programs.models import ProgramLog
from . import operational_services as operational
from .operational_models import OperationalRun, OperationalDecision
from .revised import automatic_inputs as automatic, live_evidence as evidence, live_math
from .revised.live_models import DatasetInputReview
from .test_member_record_evidence import MemberRecordEvidenceTests as Reviewed


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class AutomaticMemberInputsTests(TransactionTestCase):
    draft = Reviewed.draft
    approve = Reviewed.approve
    bind = Reviewed.bind
    publish = Reviewed.publish
    generate = Reviewed.generate

    def setUp(self):
        Reviewed.setUp(self)
        self.content = automatic.content_for_records(self.content,
            {'employed': 'Full-Time Worker', 'unemployed': 'Unemployed'})

    def applicant(self, code, low=False, prior=False, **changes):
        def registered(identifier):
            member = create_member(identifier)
            values = {'household_monthly_income': Decimal('0' if low else '100000'),
                'employment_status': 'unemployed' if low else 'employed', 'household_members': 6 if low else 2,
                'registration_profile': {'four_ps_member': 'No'}, **changes}
            for key, value in values.items():
                setattr(member, key, value)
            member.save(update_fields=list(values))
            return member
        with patch('ewaf.test_member_record_evidence.create_member', side_effect=registered):
            return Reviewed.applicant(self, code, prior=prior)

    def pool(self):
        self.publish()
        return self.applicant('AUTO-A', low=True), self.applicant('AUTO-B', prior=True)

    def test_ranking_uses_current_member_values_without_review_rows_or_documents(self):
        a, b = self.pool()
        self.assertFalse(DatasetInputReview.objects.exists())
        before = ProgramLog.objects.count()
        token = operational.context(self.program.pk, user=self.user)
        self.assertEqual(ProgramLog.objects.count(), before)
        run = self.generate()
        run.clean()
        self.assertFalse(DatasetInputReview.objects.exists())
        self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())
        self.assertEqual(run.snapshot['eligible'][str(a.pk)]['inputs']['SES']['value'], '0')
        self.assertEqual(run.snapshot['eligible'][str(a.pk)]['inputs']['SES']['household_four_ps'], 0)
        self.assertEqual(run.snapshot['eligible'][str(b.pk)]['inputs']['PA']['value'], '1')
        self.assertEqual(run.snapshot['eligible'][str(b.pk)]['inputs']['ES']['value'], 'Employed')
        self.assertIn('member_record', run.snapshot['eligible'][str(a.pk)]['assessments'])
        retained = deepcopy(run.calculations)
        a.member.household_monthly_income = Decimal('999999')
        self.assertEqual(live_math.calculations(run.snapshot, run.configuration), retained)
        altered = deepcopy(run.snapshot)
        altered['eligible'][str(a.pk)]['inputs']['SES']['value'] = '999999'
        with self.assertRaisesMessage(ValidationError, 'snapshot'):
            live_math.calculations(altered, run.configuration)

    def test_missing_values_and_unknown_employment_block_without_imputation(self):
        self.publish()
        app = self.applicant('AUTO-MISSING')
        source = evidence.context(app)
        source['member_record_inputs'] = automatic.member_values(app.member)
        for change in ({'household_monthly_income': None}, {'household_monthly_income': '-1'},
                       {'household_four_ps': None}, {'household_four_ps': ''},
                       {'household_members': 0}, {'employment_status': 'student'}):
            bad = deepcopy(source)
            bad['member_record_inputs'].update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                automatic.entry(bad, self.configuration)
        self.assertFalse(DatasetInputReview.objects.exists())

    def test_read_only_page_has_no_input_acceptance_step_and_private_sources(self):
        a, b = self.pool()
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        counts = ProgramLog.objects.count(), OperationalRun.objects.count(), DatasetInputReview.objects.count()
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['ready'])
        self.assertContains(page, 'Member record inputs')
        self.assertContains(page, 'Ready for ranking from member records.')
        self.assertNotContains(page, 'Review ranking inputs')
        self.assertNotContains(page, 'Accept ranking inputs')
        review_url = reverse('ewaf:dataset_inputs', args=[a.pk])
        self.assertRedirects(self.client.get(review_url), url + '#readiness')
        self.assertEqual(self.client.post(review_url, {'state': 'ACCEPTED'}).status_code, 405)
        self.assertEqual(counts, (ProgramLog.objects.count(), OperationalRun.objects.count(), DatasetInputReview.objects.count()))
        self.assertEqual(Client().get(url).status_code, 302)
        with self.assertRaisesMessage(ValidationError, 'automatically'):
            evidence.record(a.pk, user=self.user, expected=evidence.review_token(a, self.configuration),
                findings={}, selections={}, state='ACCEPTED', reason='No manual review', confirmed=True)

    def test_two_source_revisions_preserve_an_earlier_member_correction(self):
        from programs import information_confirmation as information
        from programs.services import record_log
        from programs.application_workflow import CONTRACT
        from members.profile import profile_snapshot
        from .revised.member_record_evidence import content_for_records
        self.content = self.document_content
        old = self.publish()
        app = self.applicant('AUTO-CHANGED', low=True)
        app.source_snapshot['application_confirmation'] = {'contract': CONTRACT, 'confirm_information': True,
            'current_information': 'changed', 'change_details': 'Fixture reviewed correction'}
        app.save(update_fields=['source_snapshot'])
        record_log(self.program, information.ACTION, 'Fixture reviewed facts', user=self.user, application=app,
            changes={'method': 'member_update', 'declaration': information.digest(information.declaration(app)),
                'member': information.member_basis(app.member), 'profile': information.digest(profile_snapshot(app.member)),
                'policy': information.policy_basis(self.program), 'member_event': None})
        reviewed = information.confirmation_context(app)
        self.assertTrue(reviewed['resolved'])
        self.content = content_for_records(old.dataset_policy.content)
        middle = self.bind()
        self.content = automatic.content_for_records(middle.dataset_policy.content,
            {'employed': 'Full-Time Worker', 'unemployed': 'Unemployed'})
        self.configuration = self.bind()
        self.assertEqual(information.confirmation_context(app), reviewed)
        _, eligible, errors = evidence.inventory(self.program, [app], self.configuration)
        self.assertFalse(errors)
        self.assertIn(str(app.pk), eligible)

    def test_policy_requires_explicit_mapping_and_current_record_periods(self):
        from .revised import contracts
        bad = deepcopy(self.content)
        bad['registration_inputs']['employment'] = {}
        with self.assertRaisesMessage(ValidationError, 'mapping'):
            self.approve(self.draft(bad))
        bad = deepcopy(self.content)
        bad['choices']['income_period']['value'] = 'before_close'
        with self.assertRaisesMessage(ValidationError, 'current-record'):
            self.approve(self.draft(bad))
        approved = self.approve()
        self.assertEqual(contracts.configuration_policy(approved)['registration_inputs'], self.content['registration_inputs'])

    def test_after_cutoff_delivery_preserves_record_snapshot_and_recalculation(self):
        from assistance.services import record_release
        from assistance.tests import release_data
        a, b = self.pool()
        first = self.generate()
        retained = deepcopy(first.payload())
        operational.record_decision(self.program.pk, user=self.user, run_id=first.pk, application_id=a.pk,
            expected_revision=0, outcome='SELECTED', reason='Fixture explicit human selection')
        a.refresh_from_db()
        record_release(a.pk, user=self.user, data=release_data(a))
        again = self.generate()
        self.assertEqual(first.calculations[str(a.pk)]['score_exact'], again.calculations[str(a.pk)]['score_exact'])
        self.assertEqual(again.snapshot['eligible'][str(a.pk)]['inputs']['PA']['value'], '0')
        first.refresh_from_db(); first.clean()
        self.assertEqual(first.payload(), retained)

    def test_generation_requires_permission_and_rolls_back_missing_audit(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        from uuid import uuid4
        self.pool()
        limited = get_user_model().objects.create_user('AUTO-VIEWER', is_staff=True)
        grant(limited, 'accounts.access_dashboard', *operational.VIEW)
        expected = operational.context(self.program.pk, user=self.user)
        with self.assertRaises(PermissionDenied):
            operational.generate(self.program.pk, user=limited, expected=expected,
                request_key=uuid4(), reason='Unauthorized generation')
        with patch('programs.models.ProgramLog.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.generate()
        self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())

    def test_retired_guide_returns_to_saved_ranking_and_breakdown_keeps_recorded_participation(self):
        a, b = self.pool()
        run = self.generate()
        page = self.client.get(reverse('ewaf:operational_calculation_guide', args=[self.program.pk]), {'run': run.pk})
        self.assertRedirects(page, reverse('ewaf:operational_workspace', args=[self.program.pk]) + f'?run={run.pk}#results')
        page = self.client.get(reverse('ewaf:operational_breakdown', args=[self.program.pk]), {'run': run.pk})
        self.assertContains(page, 'Recorded No')
