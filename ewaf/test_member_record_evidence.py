"""No-upload ranking review with retained policy and source provenance."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.services import review_eligibility, decide_assistance, record_release
from assistance.tests import review_data, decision_data, release_data
from members.tests import create_member
from membership.services import record_event
from programs.tests import create_program
from programs.testsupport import application_fixture
from programs.models import ProgramLog
from . import test_composite_ses as composite
from . import operational_services as operational
from .operational_models import OperationalConfiguration, OperationalDecision
from .revised import live_evidence as evidence, live_services as policies, contracts
from .revised.live_models import DatasetInputReview
from .revised.live_forms import PolicyDraftForm
from .revised import member_record_evidence as records


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class MemberRecordEvidenceTests(TransactionTestCase):
    draft = composite.CompositeSesWorkflowTests.draft
    approve = composite.CompositeSesWorkflowTests.approve
    bind = composite.CompositeSesWorkflowTests.bind
    publish = composite.CompositeSesWorkflowTests.publish
    generate = composite.CompositeSesWorkflowTests.generate

    def setUp(self):
        composite.CompositeSesWorkflowTests.setUp(self)
        self.document_content = deepcopy(self.content)
        self.content = records.content_for_records(self.content)

    def applicant(self, code, prior=False):
        with patch('django.utils.timezone.now', return_value=self.base + timedelta(hours=2)):
            member = create_member(code)
            intake = member.application
            intake.prpwd_verified_by = intake.decided_by = self.user
            intake.save()
            record_event(intake, 'prpwd_verified', 'Fixture manual verification', user=self.user)
            record_event(intake, 'approved', 'Fixture approved intake', user=self.user)
            if prior:
                other = create_program(registration_opens_at=self.base - timedelta(days=2),
                    registration_closes_at=self.base - timedelta(days=1))
                old = application_fixture(other, member)
                review_eligibility(old.pk, user=self.user, data=review_data(old))
                decide_assistance(old.pk, user=self.user, data=decision_data(old))
                record_release(old.pk, user=self.user, data=release_data(old))
            app = application_fixture(self.program, member)
            app.source_snapshot = {'member_id': member.pk, 'member_version': member.version,
                'program_version': self.program.version, 'membership_verified_at': timezone.now().isoformat(),
                'policy_authorized_at': self.program.policy_authorized_at.isoformat()}
            app.save(update_fields=['source_snapshot'])
        review_eligibility(app.pk, user=self.user, data=review_data(app))
        app.refresh_from_db()
        self.assertFalse(member.application.documents.exists())
        return app

    def findings(self, low=False, **changes):
        return {**evidence.periods(self.configuration), 'income_monthly': ['0' if low else '100000'] * 3,
            'employment': 'Unemployed' if low else 'Full-Time Worker', 'household_members': 6 if low else 2,
            'history_complete': True, 'assessment_finding': 'Fixture member record reviewed',
            'income_consistency': 'consistent', 'income_resolution': '', 'household_four_ps': False,
            'four_ps_household_confirmed': True, 'four_ps_household_review': 'Fixture household relationship reviewed',
            **changes}

    def accept(self, app, low=False, **changes):
        return evidence.record(app.pk, user=self.user, expected=evidence.review_token(app, self.configuration),
            findings=self.findings(low, **changes), selections={}, state='ACCEPTED',
            reason='Fixture member-record acceptance', confirmed=True)

    def test_record_policy_needs_no_document_types_and_historical_policy_still_does(self):
        approved = self.approve()
        approved.clean()
        self.assertEqual(approved.content['evidence_catalog'], {})
        form = PolicyDraftForm(content=approved.content)
        self.assertFalse(any(key.startswith('evidence_') and key[9:] in composite.CODES for key in form.fields))
        old = deepcopy(self.document_content)
        old['choices']['evidence_SES']['value'] = []
        self.assertTrue(any('SES' in error for error in contracts.findings(old, approved.weight_snapshot)))
        self.assertEqual(self.document_content['choices']['evidence_rule']['value'], 'verified_documents')

    def test_complete_pool_generates_without_any_ranking_documents(self):
        self.publish()
        a, b = self.applicant('RECORD-A'), self.applicant('RECORD-B', prior=True)
        ar, br = self.accept(a, low=True), self.accept(b)
        self.assertEqual(ar.inputs['SES']['value'], '0')
        self.assertEqual(ar.inputs['SES']['household_four_ps'], 0)
        self.assertEqual(br.inputs['PA']['value'], '1')
        for row in (ar, br):
            row.clean()
            self.assertEqual(row.supporting_reviews, records.supporting(row.source, self.configuration))
            self.assertNotIn('document_type', str(row.supporting_reviews))
        run = self.generate()
        run.clean()
        self.assertEqual(len(run.calculations), 2)
        self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())

    def test_unresolved_findings_and_stale_token_cannot_be_accepted_without_documents(self):
        self.publish()
        app = self.applicant('RECORD-UNRESOLVED')
        for change in ({'household_four_ps': None}, {'four_ps_household_confirmed': False},
                       {'history_complete': False}, {'income_monthly': ['', '', '']}, {'employment': 'unknown'}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.accept(app, **change)
        with self.assertRaises(ValidationError):
            evidence.record(app.pk, user=self.user, expected='stale', findings=self.findings(), selections={},
                state='ACCEPTED', reason='Stale request', confirmed=True)
        self.assertFalse(DatasetInputReview.objects.filter(program=self.program).exists())
        with self.assertRaises(ValidationError):
            self.generate()

    def test_review_page_preserves_no_upload_workflow_and_does_not_accept_on_get(self):
        self.publish()
        app = self.applicant('RECORD-HTTP')
        url = reverse('ewaf:dataset_inputs', args=[app.pk])
        before = DatasetInputReview.objects.count(), ProgramLog.objects.count()
        page = self.client.get(url)
        self.assertContains(page, 'Accept ranking inputs')
        self.assertContains(page, 'Member registration information')
        self.assertNotContains(page, 'name="evidence_SES"')
        self.assertNotContains(page, 'SYNTHETIC documented assessment')
        self.assertEqual(before, (DatasetInputReview.objects.count(), ProgramLog.objects.count()))
        data = self.findings()
        data.update(expected=evidence.review_token(app, self.configuration), state='ACCEPTED',
            reason='Fixture explicit review', confirmed='on', household_four_ps='no',
            income_0='100000', income_1='100000', income_2='100000')
        data.pop('income_monthly')
        for key in evidence.periods(self.configuration):
            data.pop(key)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        page = self.client.get(url)
        self.assertEqual(page.context['form'].initial['household_four_ps'], 'no')
        self.assertFalse(any(key.startswith('evidence_') for key in page.context['form'].fields))

    def test_member_source_changes_and_review_age_require_renewed_review(self):
        self.publish()
        app = self.applicant('RECORD-STALE')
        row = self.accept(app)
        source = deepcopy(row.source)
        source['member_version'] += 1
        with self.assertRaisesMessage(ValidationError, 'stale'):
            evidence.accepted(app, self.configuration, source)
        with patch('django.utils.timezone.now', return_value=row.recorded_at + timedelta(days=91)):
            with self.assertRaisesMessage(ValidationError, 'outdated'):
                evidence.accepted(app, self.configuration, row.source)

    def test_published_unscored_program_can_replace_only_its_evidence_rules(self):
        self.content = self.document_content
        old = self.publish()
        app = self.applicant('RECORD-REBIND')
        retained = deepcopy(old.payload())
        self.content = records.content_for_records(old.dataset_policy.content)
        new = self.bind()
        self.assertEqual(new.previous_id, old.pk)
        self.assertEqual(new.validation, old.validation)
        self.assertEqual(new.assessment_cutoff, old.assessment_cutoff)
        old.refresh_from_db(); old.clean()
        self.assertEqual(old.payload(), retained)
        self.assertEqual(app.status, 'ELIGIBLE')

    def test_rebinding_rejects_changed_calculation_rules_and_rolls_back_audit_failure(self):
        self.content = self.document_content
        old = self.publish()
        self.applicant('RECORD-BIND-GUARDS')
        self.content = records.content_for_records(old.dataset_policy.content)
        self.content['choices']['income_months']['value'] = 4
        with self.assertRaisesMessage(ValidationError, 'Only evidence-source'):
            self.bind()
        self.content['choices']['income_months']['value'] = 3
        approved = self.approve()
        before = OperationalConfiguration.objects.filter(program=self.program).count()
        with patch('programs.models.ProgramLog.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.bind(approved)
        self.assertEqual(OperationalConfiguration.objects.filter(program=self.program).count(), before)

    def test_old_accepted_reviews_block_policy_replacement_and_replay_unchanged(self):
        self.content = self.document_content
        old = self.publish()
        app, proof = composite.CompositeSesWorkflowTests.applicant(self, 'RECORD-OLD')
        row = composite.CompositeSesWorkflowTests.accept(self, app, proof)
        retained = deepcopy(row.payload())
        self.content = records.content_for_records(old.dataset_policy.content)
        with self.assertRaisesMessage(ValidationError, 'accepted inputs or calculations'):
            self.bind()
        row.refresh_from_db(); row.clean()
        self.assertEqual(row.payload(), retained)

    def test_evidence_revision_preserves_reviewed_member_changes_without_a_new_review(self):
        from members.profile import profile_snapshot
        from programs import information_confirmation as information
        from programs.application_workflow import CONTRACT
        from programs.services import record_log
        self.content = self.document_content
        old = self.publish()
        app = self.applicant('RECORD-REVIEWED-CHANGE')
        app.source_snapshot['application_confirmation'] = {
            'contract': CONTRACT, 'confirm_information': True, 'current_information': 'changed',
            'change_details': 'Fixture employment correction already reviewed.'}
        app.save(update_fields=['source_snapshot'])
        record_log(self.program, information.ACTION, 'Fixture reviewed member correction',
            user=self.user, application=app, changes={
                'method': 'member_update', 'declaration': information.digest(information.declaration(app)),
                'member': information.member_basis(app.member),
                'profile': information.digest(profile_snapshot(app.member)),
                'policy': information.policy_basis(self.program), 'member_event': None})
        original = information.confirmation_context(app)
        self.assertTrue(original['resolved'])
        count = ProgramLog.objects.filter(application=app, action=information.ACTION).count()
        self.content = records.content_for_records(old.dataset_policy.content)
        self.configuration = self.bind()
        self.assertEqual(information.confirmation_context(app), original)
        self.accept(app)
        self.assertEqual(information.confirmation_context(app), original)
        self.assertEqual(ProgramLog.objects.filter(application=app, action=information.ACTION).count(), count)

        # Reuse never permits changed facts, member versions, declarations or
        # program dates to inherit the earlier review.
        app.member.household_members = (app.member.household_members or 0) + 1
        self.assertFalse(information.confirmation_context(app)['resolved'])
        app.member.refresh_from_db()
        app.member.version += 1
        self.assertFalse(information.confirmation_context(app)['resolved'])
        app.member.refresh_from_db()
        app.source_snapshot['application_confirmation']['change_details'] = 'A new change report'
        self.assertFalse(information.confirmation_context(app)['resolved'])
        app.refresh_from_db()
        app.program.registration_closes_at += timedelta(minutes=1)
        self.assertFalse(information.confirmation_context(app)['resolved'])

    def test_information_review_reuse_requires_the_exact_predecessor_and_member_update(self):
        from programs import information_confirmation as information
        self.content = self.document_content
        old = self.publish()
        original = information.policy_basis(self.program)
        self.content = records.content_for_records(old.dataset_policy.content)
        self.configuration = self.bind()
        self.assertTrue(information.review_policy_matches({'method': 'member_update', 'policy': original}, self.program))
        self.assertFalse(information.review_policy_matches({'policy': original}, self.program))
        unrelated = {**original, 'configuration': 'unrelated-policy'}
        self.assertFalse(information.review_policy_matches({'method': 'member_update', 'policy': unrelated}, self.program))
        changed = deepcopy(self.content)
        changed['choices']['income_months']['value'] = 4
        self.assertFalse(records.same_assessment_rules(old.dataset_policy.content, changed))
