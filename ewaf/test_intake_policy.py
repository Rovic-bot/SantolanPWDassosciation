"""Synthetic approved-weights publication/intake; scoring remains unavailable."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from announcements.tests import image_upload
from members.tests import create_member
from programs.models import Program, ProgramLog, ProgramApplication
from programs.tests import program_data, create_program
from programs.test_approved_terms import TermsHelpers
from programs.services import save_program, change_publication, submit_application
from programs import application_workflow as workflow
from assistance.tests import seed_statuses, decision_data, release_data
from assistance.services import decide_assistance, record_release
from scripts.durable_test_runner import require_disposable
from . import vault_services as vault, operational_services as operational, intake_policy
from .vault_policy import source_policy
from .vault_models import VaultRevision
from .household_criteria import PAIRS
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision


@override_settings(EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
    PDAO_ENFORCEMENT_ENABLED=True, EWAF_DATASET_POLICY_ENABLED=False, EWAF_DATASET_SCORING_ENABLED=False)
class ApprovedWeightsIntakeTests(TestCase):
    def setUp(self):
        require_disposable()
        seed_statuses()
        self.user = get_user_model().objects.create_superuser('SYNTHETIC-WEIGHTS-PUBLICATION')
        self.weights = vault.record(user=self.user, expected=vault.token(), proposed=source_policy(),
            judgments=dict.fromkeys(PAIRS,'1'), status='LOCKED', reason='ISOLATED SYNTHETIC approved weights',attested=True)
        self.program = save_program(user=self.user,data=program_data(ewaf_applicable=True,benefit='Synthetic program',
            registration_opens_at=timezone.now()+timedelta(days=1),registration_closes_at=timezone.now()+timedelta(days=2)))
        change_publication(self.program.pk,user=self.user,version=self.program.version,action='authorize_policy',notes='Synthetic program authority')
        self.program.refresh_from_db()
        terms = TermsHelpers()
        terms.program,terms.officer = self.program,self.user
        terms.reconcile()
        self.member = create_member('SYNTHETIC-WEIGHTS-APPLICANT')
        self.member.application.decided_by = self.user
        self.member.application.save(update_fields=['decided_by'])
        self.member.refresh_from_db()

    def publish(self,**changes):
        change_publication(self.program.pk,**(dict(user=self.user,version=self.program.version,
            action='published',notes='Synthetic publication using retained approved weights')|changes))
        self.program.refresh_from_db()

    def grant(self):
        return workflow.verify(self.program.pk,version=self.program.version,control_number=self.member.control_number,
            full_name=self.member.full_name,birthdate=self.member.birthdate,contact_number=self.member.contact_number)[0]

    def submit(self,grant):
        return submit_application(self.program.pk,grant=grant,data=dict(version=self.program.version,
            applicant_name=self.member.full_name,applicant_contact=self.member.contact_number,
            applicant_email='synthetic@example.invalid',pwd_id_number='SYNTHETIC-ID',current_information='unchanged',
            change_details='',confirm_information=True),files=MultiValueDict({'calendar_photo':[image_upload()]}))

    def test_publication_retains_exact_weight_version_schedule_and_scoring_block(self):
        before = self.weights.payload()
        schedule = self.program.registration_opens_at,self.program.registration_closes_at
        self.assertEqual(workflow.publication_configuration_problem(self.program),'')
        self.publish()
        bound = intake_policy.require_configuration(self.program)
        self.assertEqual(bound.source['contract'],intake_policy.CONTRACT)
        self.assertEqual(bound.vault_revision_id,self.weights.pk)
        self.assertEqual(bound.status,'DRAFT')  # Scoring was not approved by publication.
        self.assertEqual((self.program.registration_opens_at,self.program.registration_closes_at),schedule)
        self.weights.refresh_from_db()
        self.assertEqual(self.weights.payload(),before)
        self.assertEqual(VaultRevision.objects.count(),1)
        with self.assertRaises(ValidationError):
            operational.generate(self.program.pk,user=self.user,expected={},request_key=uuid4(),reason='Synthetic scoring denied')
        self.assertFalse(OperationalRun.objects.exists())
        self.assertFalse(OperationalDecision.objects.exists())

    def test_verified_members_apply_only_during_original_schedule_without_scoring_policy(self):
        self.publish()
        with self.assertRaises(ValidationError):
            self.grant()
        with patch('django.utils.timezone.now',return_value=self.program.registration_opens_at+timedelta(minutes=1)):
            self.assertTrue(workflow.availability(self.program))
            grant = self.grant()
            application = self.submit(grant)
            self.assertTrue(application.public_reference)
            self.assertEqual(application.member_id,self.member.pk)
            self.assertEqual(self.submit(grant).pk,application.pk)
            with self.assertRaises(ValidationError):
                decide_assistance(application.pk,user=self.user,data=decision_data(application))
            with self.assertRaises(ValidationError):
                record_release(application.pk,user=self.user,data=release_data(application))
        with patch('django.utils.timezone.now',return_value=self.program.registration_closes_at+timedelta(seconds=1)):
            self.assertFalse(workflow.availability(self.program))
            with self.assertRaises(ValidationError):
                self.grant()
            with self.assertRaises(ValidationError):
                self.submit(grant)
        self.assertEqual(ProgramApplication.objects.count(),1)

    def test_later_vault_revision_does_not_change_published_intake(self):
        self.publish()
        original = intake_policy.require_configuration(self.program)
        retained = original.payload()
        newer = vault.record(user=self.user,expected=vault.token(),proposed=source_policy(),
            judgments=dict.fromkeys(PAIRS,'1'),status='LOCKED',reason='SYNTHETIC later locked version',attested=True)
        self.assertNotEqual(newer.pk,self.weights.pk)
        self.assertEqual(intake_policy.require_configuration(self.program).payload(),retained)

    def test_missing_and_unapproved_configuration_cannot_publish_or_accept_members(self):
        other = create_program(ewaf_applicable=True,policy_authorized_by=self.user)
        self.assertTrue(workflow.publication_configuration_problem(other))
        with self.assertRaises(ValidationError):
            intake_policy.require_configuration(other)
        configuration = OperationalConfiguration.objects.filter(program=self.program).first()
        configuration.vault_revision.status='DRAFT'
        with self.assertRaises(ValidationError):
            intake_policy.validate_weights(configuration)
        with self.assertRaisesMessage(ValidationError,'bound'):
            intake_policy.require_configuration(self.program)

    def test_permissions_approved_terms_stale_requests_and_audit_failure_are_preserved(self):
        other = get_user_model().objects.create_user('SYNTHETIC-NO-PUBLISH',is_staff=True)
        with self.assertRaises(PermissionDenied):
            self.publish(user=other)
        with self.assertRaises(ValidationError):
            self.publish(version=self.program.version-1)
        before = OperationalConfiguration.objects.filter(program=self.program).count(),ProgramLog.objects.filter(program=self.program).count()
        with patch.object(ProgramLog.objects,'create',side_effect=RuntimeError('Synthetic failed audit')):
            with self.assertRaises(RuntimeError):
                self.publish()
        self.program.refresh_from_db()
        self.assertEqual(self.program.status,'draft')
        self.assertEqual((OperationalConfiguration.objects.filter(program=self.program).count(),ProgramLog.objects.filter(program=self.program).count()),before)
        # Changed approved terms remain an intake blocker even in memory.
        self.publish()
        self.program.selection_method='Synthetic unapproved change'
        with self.assertRaisesMessage(ValidationError,'current authorized program terms'):
            intake_policy.require_configuration(self.program)

    def test_admin_ui_reports_publication_readiness_without_claiming_scoring_ready(self):
        self.client.force_login(self.user)
        response=self.client.get(reverse('programs:manage_detail',args=[self.program.pk]))
        self.assertContains(response,'Approved EWAF weights are assigned')
        self.assertNotContains(response,'Programs using this configuration cannot be published yet')
        from .program_cards import configuration_summary
        self.assertEqual(configuration_summary(self.program)['state'],'intake_ready')
        from .dataset_methods import HOUSEHOLD
        self.assertContains(self.client.get(reverse('ewaf:vault')+'?method='+HOUSEHOLD),'Calculation, ranking and selection require')

    @override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True)
    def test_application_review_opens_with_approved_weights_and_pending_scoring_rules(self):
        self.publish()
        with patch('django.utils.timezone.now', return_value=self.program.registration_opens_at + timedelta(minutes=1)):
            application = self.submit(self.grant())
        configuration = OperationalConfiguration.objects.filter(program=self.program).first()
        before = configuration.payload()
        self.client.force_login(self.user)
        url = reverse('programs:application_detail', args=[self.program.pk, application.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Application review')
        self.assertContains(response, 'Current information needs review.')
        self.assertEqual(response.context['household_members'], 'Not recorded')
        self.assertEqual(response.context['household_income'], 'Not recorded')
        self.assertNotContains(response, 'Reviewed information for this application.')
        from programs.review_forms import ApplicationDecisionForm
        from assistance.models import AssistanceCase
        decision = ApplicationDecisionForm(application=application)
        # Keep the review after the synthetic future-dated submission.
        with patch('django.utils.timezone.now', return_value=self.program.registration_opens_at + timedelta(minutes=2)):
            self.client.force_login(self.user)
            response = self.client.post(url, {'action': 'review_decision', **decision.initial,
                                             'eligibility': 'eligible', 'notes': ''})
        self.assertEqual(response.status_code, 302,
                         response.context['decision_form'].errors if response.status_code == 200 else '')
        self.assertRedirects(response, url)
        application.refresh_from_db()
        self.assertEqual(application.status, 'ELIGIBLE')
        self.assertEqual(AssistanceCase.objects.get(application=application).decision, 'pending')
        self.assertEqual(self.client.get(url).context['review_result'], 'Eligible')
        self.assertFalse(application.criterion_assessments.exists())
        configuration.refresh_from_db()
        self.assertEqual(configuration.payload(), before)
        with self.assertRaises(ValidationError):
            operational.latest_configuration(self.program)
        self.assertFalse(OperationalRun.objects.exists())
        self.assertFalse(OperationalDecision.objects.exists())
