"""Recorded exclusions do not require renewed inputs to rank eligible applicants."""
from copy import deepcopy
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import F
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceCase, AssistanceLog
from assistance.services import review_eligibility
from assistance.tests import review_data
from members.models import Member
from members.tests import create_member
from programs.models import ProgramApplication
from programs.testsupport import application_fixture
from . import operational_services as operational
from . import test_automatic_member_inputs as automatic
from . import test_composite_ses as documents
from . import test_member_record_evidence as records
from . import test_vault as vault
from .operational_models import OperationalRun, OperationalDecision
from .operational_testsupport import OperationalHelpers


def exclude(application, user):
    review_eligibility(application.pk, user=user, direct_review=True,
        data=review_data(application, eligibility='ineligible', other_requirements='fail',
            notes='Synthetic confirmed failure of a required program qualification.'))
    application.refresh_from_db()


def change_excluded_sources(application):
    # Synthetic changed profile, missing scoring input, and a late submission.
    # None of these records may enter the eligible scoring pool.
    Member.objects.filter(pk=application.member_id).update(
        version=F('version') + 1, household_monthly_income=None)
    ProgramApplication.objects.filter(pk=application.pk).update(
        submitted_at=application.program.registration_closes_at + timedelta(minutes=1))
    application.refresh_from_db()


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DocumentExclusionTests(TransactionTestCase):
    setUp = documents.CompositeSesWorkflowTests.setUp
    draft = documents.CompositeSesWorkflowTests.draft
    approve = documents.CompositeSesWorkflowTests.approve
    bind = documents.CompositeSesWorkflowTests.bind
    publish = documents.CompositeSesWorkflowTests.publish
    generate = documents.CompositeSesWorkflowTests.generate
    applicant = documents.CompositeSesWorkflowTests.applicant
    accept = documents.CompositeSesWorkflowTests.accept

    def pool(self):
        self.publish()
        a, ar = self.applicant('EXCLUDE-A')
        b, br = self.applicant('EXCLUDE-B', prior=True)
        self.seed_exclusion()
        self.accept(a, ar, low=True)
        self.accept(b, br)
        return a, b

    def extra_applicant(self, code='SYNTHETIC-EXCLUDED'):
        added = self.applicant(code)
        return added[0] if isinstance(added, tuple) else added

    def seed_exclusion(self):
        self.excluded = self.extra_applicant()
        exclude(self.excluded, self.user)

    def test_changed_excluded_sources_leave_only_eligible_applicants_in_ranking(self):
        a, b = self.pool()
        original = self.generate()
        retained = deepcopy(original.payload())
        excluded = self.excluded
        change_excluded_sources(excluded)
        reviews = list(AssistanceLog.objects.filter(application=excluded).values())
        case = AssistanceCase.objects.values().get(application=excluded)

        current = self.generate()
        current.clean()
        self.assertEqual(set(current.calculations), {str(a.pk), str(b.pk)})
        self.assertEqual(current.calculations, original.calculations)
        self.assertNotIn(str(excluded.pk), current.snapshot['eligible'])
        manifest = next(row for row in current.snapshot['manifest'] if row['application'] == str(excluded.pk))
        self.assertEqual(manifest['status'], 'INELIGIBLE')
        self.assertEqual(manifest['errors'], [])
        self.assertLess(manifest['source']['case']['member_version'], manifest['source']['member_version'])
        self.assertFalse(manifest['evidence'])
        self.assertFalse(OperationalDecision.objects.exists())
        self.assertEqual(AssistanceCase.objects.values().get(application=excluded), case)
        self.assertEqual(list(AssistanceLog.objects.filter(application=excluded).values()), reviews)

        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]),
            {'review': excluded.pk})
        self.assertTrue(page.context['ready'])
        self.assertEqual(page.context['ready_count'], 2)
        self.assertEqual(page.context['pending_count'], 0)
        self.assertFalse(page.context['selected_input']['needs_review'])
        self.assertEqual(page.context['selected_input']['input_state'], 'excluded')
        panel = page.content.decode().split('id="readiness"', 1)[1].split('</aside>', 1)[0]
        self.assertNotIn('name="action" value="SELECT_ASSISTANCE"', panel)

        # The same outdated source still blocks an applicant who IS eligible.
        Member.objects.filter(pk=a.member_id).update(version=F('version') + 1)
        with self.assertRaises(ValidationError):
            self.generate()
        self.assertEqual(OperationalRun.objects.filter(program=self.program).count(), 2)
        original.refresh_from_db()
        original.clean()
        self.assertEqual(original.payload(), retained)

    def test_status_without_an_ineligible_decision_cannot_omit_an_applicant(self):
        self.pool()
        added = self.extra_applicant('SYNTHETIC-UNREVIEWED-EXCLUSION')
        ProgramApplication.objects.filter(pk=added.pk).update(status='INELIGIBLE')
        with self.assertRaisesMessage(ValidationError, 'INELIGIBLE_OUTCOME_STALE_OR_UNVERIFIED'):
            self.generate()
        self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())


class ReviewedMemberExclusionTests(DocumentExclusionTests):
    setUp = records.MemberRecordEvidenceTests.setUp
    applicant = records.MemberRecordEvidenceTests.applicant
    findings = records.MemberRecordEvidenceTests.findings
    accept = records.MemberRecordEvidenceTests.accept

    def pool(self):
        self.publish()
        a, b = self.applicant('EXCLUDE-A'), self.applicant('EXCLUDE-B', prior=True)
        self.seed_exclusion()
        self.accept(a, low=True)
        self.accept(b)
        return a, b


class AutomaticExclusionTests(DocumentExclusionTests):
    setUp = automatic.AutomaticMemberInputsTests.setUp
    applicant = automatic.AutomaticMemberInputsTests.applicant

    def pool(self):
        a, b = automatic.AutomaticMemberInputsTests.pool(self)
        self.seed_exclusion()
        return a, b


class OperationalExclusionTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()
        self.lock_policy()

    def test_excluded_source_changes_do_not_block_retained_operational_workflow(self):
        original = self.calculate()
        retained = deepcopy(original.payload())
        added = application_fixture(self.program, create_member('SYNTHETIC-LEGACY-EXCLUDED'))
        exclude(added, self.officer)
        change_excluded_sources(added)
        current = self.calculate()
        current.clean()
        self.assertEqual(set(current.calculations), {str(self.application.pk)})
        self.assertEqual(current.calculations, original.calculations)
        self.assertNotIn(str(added.pk), current.snapshot['eligible'])
        original.refresh_from_db()
        self.assertEqual(original.payload(), retained)


@override_settings(EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class VaultExclusionTests(OperationalExclusionTests):
    review = vault.RegisteredInputTests.review

    def setUp(self):
        vault.RegisteredInputTests.setUp(self)
        self.review()
