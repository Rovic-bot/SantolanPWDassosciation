from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from members.models import DisabilityType, Member
from members.tests import create_member
from .models import Program, ProgramApplication, ProgramLog
from .tests import create_program, program_data
from .testsupport import private_media, verified_photo
from . import application_workflow as workflow
from . import information_confirmation as information
from .services import submit_application, change_publication, save_program


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ConfirmedApplicationTests(TestCase):
    def setUp(self):
        private_media(self)
        self.admin = get_user_model().objects.create_superuser('workflow-admin', password='synthetic-only')
        self.member = create_member('SYNTHETIC-WORKFLOW')
        self.member.application.decided_by = self.admin
        self.member.application.save(update_fields=['decided_by'])
        self.member.refresh_from_db()
        self.program = create_program(policy_authorized_by=self.admin, benefit='Synthetic program purpose.')
        self.verify_url = reverse('programs:verify', args=[self.program.pk])
        self.apply_url = reverse('programs:apply', args=[self.program.pk])

    def identity(self, **overrides):
        return {'control_number': self.member.control_number, 'full_name': self.member.full_name,
            'version': self.program.version, **overrides}

    def grant(self):
        return workflow.verify(self.program.pk, **self.identity())[0]

    def data(self, **overrides):
        return {'version': self.program.version, 'applicant_name': self.member.full_name,
            'applicant_email': 'different@example.invalid',
            'confirm_information': True, **overrides}

    def submit(self, **overrides):
        return submit_application(self.program.pk, grant=self.grant(), data=self.data(**overrides),
            files=MultiValueDict())

    def test_membership_failure_is_generic_and_does_not_assert_nonmembership(self):
        for changes in ({'full_name': 'Wrong'}, {'control_number': 'NOT-IN-RECORDS'}):
            response = self.client.post(self.verify_url, self.identity(**changes))
            self.assertContains(response, workflow.FAILED)
            self.assertContains(response, 'does not prove that someone is a non-member')
            self.assertNotContains(response, self.member.control_number if 'control_number' in changes else 'PRIVATE-PROFILE')
            self.assertNotIn('program_verification', self.client.session)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_identity_uses_control_and_name_not_self_declared_disability(self):
        response = self.client.get(self.verify_url)
        for field in ('control_number', 'full_name'):
            self.assertContains(response, f'name="{field}"')
        for field in ('birthdate', 'contact_number'):
            self.assertNotContains(response, f'name="{field}"')
        self.assertNotContains(response, 'name="disability_types"')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertRedirects(self.client.post(self.verify_url, self.identity()), self.apply_url)
        response = self.client.get(self.apply_url)
        self.assertContains(response, 'Application details')
        for field in ('applicant_name', 'applicant_email', 'confirm_information'):
            self.assertContains(response, f'name="{field}"')
        for field in ('pwd_id_number', 'calendar_photo', 'applicant_contact', 'current_information', 'change_details'):
            self.assertNotContains(response, f'name="{field}"')
        self.assertNotContains(response, self.member.contact_number)
        self.assertNotContains(response, self.member.email or 'NEVER-PREFILL-DATABASE-EMAIL')

    def test_one_allowed_classification_passes_even_with_additional_types(self):
        extra = DisabilityType.objects.create(name='Synthetic additional classification')
        self.member.disability_types.set([self.member.disability_type, extra])
        self.assertEqual(workflow.screening(self.member, self.program)[0], 'passed')
        self.assertIsNotNone(self.grant())

    def test_confirmed_mismatch_explains_requirement_and_creates_no_queue_entry(self):
        self.client.post(self.verify_url, self.identity())
        other = DisabilityType.objects.create(name='Synthetic unmatched classification')
        self.program.eligible_disability_types.set([other])
        response = self.client.post(self.verify_url, self.identity())
        self.assertContains(response, 'Application cannot proceed')
        self.assertContains(response, 'You cannot proceed with this application because')
        self.assertContains(response, 'target disability types')
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, reverse('core:contact'))
        self.assertNotIn('program_verification', self.client.session)
        self.assertNotContains(response, 'name="calendar_photo"')
        self.assertRedirects(self.client.post(self.apply_url, self.data()), self.verify_url)
        self.assertFalse(ProgramApplication.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='submitted').exists())

    def test_mismatch_is_not_disclosed_before_identity_is_verified(self):
        other = DisabilityType.objects.create(name='Synthetic unmatched classification')
        self.program.eligible_disability_types.set([other])
        response = self.client.post(self.verify_url, self.identity(full_name='Wrong name'))
        self.assertContains(response, workflow.FAILED)
        self.assertNotContains(response, 'target disability types')
        self.assertNotIn('program_verification', self.client.session)

    def test_disability_change_after_verification_blocks_direct_submission(self):
        grant = self.grant()
        other = DisabilityType.objects.create(name='Synthetic changed classification')
        Member.objects.filter(pk=self.member.pk).update(disability_type=other)
        with self.assertRaises(ValidationError):
            submit_application(self.program.pk, grant=grant, data=self.data(), files=MultiValueDict())
        self.assertFalse(ProgramApplication.objects.exists())

    def test_unrestricted_program_does_not_require_a_disability_match(self):
        self.program.eligible_disability_types.clear()
        Member.objects.filter(pk=self.member.pk).update(disability_type=None)
        self.member.refresh_from_db()
        self.assertIsNotNone(self.grant())
        self.assertRedirects(self.client.post(self.verify_url, self.identity()), self.apply_url)

    def test_missing_or_inactive_classification_requires_correction_not_rejection(self):
        Member.objects.filter(pk=self.member.pk).update(disability_type=None)
        self.member.refresh_from_db()
        response = self.client.post(self.verify_url, self.identity())
        self.assertContains(response, 'Unable to confirm / correctable information')
        self.assertNotContains(response, 'Application cannot proceed')
        self.assertFalse(ProgramApplication.objects.exists())

    def test_inactive_classification_requests_review_instead_of_confirming_mismatch(self):
        inactive = DisabilityType.objects.create(name='Synthetic historical classification', is_active=False)
        Member.objects.filter(pk=self.member.pk).update(disability_type=inactive)
        response = self.client.post(self.verify_url, self.identity())
        self.assertContains(response, 'need clarification')
        self.assertNotContains(response, 'target disability types')
        self.assertNotIn('program_verification', self.client.session)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_inactive_or_unapproved_member_is_not_admitted(self):
        Member.objects.filter(pk=self.member.pk).update(is_active=False)
        self.assertContains(self.client.post(self.verify_url, self.identity()), workflow.FAILED)
        Member.objects.filter(pk=self.member.pk).update(is_active=True)
        self.member.application.decided_by = None
        self.member.application.save(update_fields=['decided_by'])
        self.assertContains(self.client.post(self.verify_url, self.identity()), workflow.FAILED)

    def test_success_keeps_reference_and_links_declarations_without_changing_member(self):
        Member.objects.filter(pk=self.member.pk).update(email='saved-member@example.invalid')
        before = Member.objects.values().get(pk=self.member.pk)
        application = self.submit()
        declaration = information.declaration(application)
        self.assertEqual(application.member_id, self.member.pk)
        self.assertEqual(declaration['applicant_email'], 'different@example.invalid')
        self.assertNotIn('pwd_id_number', declaration)
        self.assertEqual(application.status, 'ELIGIBILITY_REVIEW')
        self.assertIsNone(application.current_photo_id)
        self.assertNotIn(self.member.full_name, application.public_reference)
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertTrue(information.confirmation_context(application)['resolved'])
        self.assertEqual(self.submit().pk, application.pk)
        self.assertEqual(ProgramApplication.objects.count(), 1)

    def test_contact_is_taken_from_the_member_record_and_public_overrides_are_ignored(self):
        application = self.submit(applicant_contact='FORGED CONTACT', contact_source='public_override')
        report = information.declaration(application)
        self.assertEqual(report['applicant_contact'], self.member.contact_number)
        self.assertEqual(report['contact_source'], 'member_record')
        self.member.refresh_from_db()
        self.assertNotEqual(self.member.contact_number, 'FORGED CONTACT')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('programs:application_detail', args=[self.program.pk, application.pk]))
        self.assertNotContains(response, self.member.contact_number)
        self.assertNotContains(response, 'Contact number provided')

    def test_later_directory_changes_do_not_rewrite_the_saved_application_contact(self):
        application = self.submit()
        saved = self.member.contact_number
        Member.objects.filter(pk=self.member.pk).update(contact_number='09990000000', version=self.member.version + 1)
        application.refresh_from_db()
        self.assertEqual(information.declaration(application)['applicant_contact'], saved)

    def test_removed_change_fields_are_ignored_without_holding_the_application(self):
        application = self.submit(current_information='changed',
            change_details='My household income changed. Please review the evidence.')
        self.assertEqual(application.status, 'ELIGIBILITY_REVIEW')
        report = information.declaration(application)
        self.assertEqual(report['information_basis'], 'member_record')
        self.assertNotIn('current_information', report)
        self.assertNotIn('change_details', report)
        self.assertEqual(information.confirmation_context(application)['report'], 'not_requested')
        information.require_resolved(application)
        self.assertNotIn('household_monthly_income', application.answers)

    @override_settings(PROGRAM_INTAKE_ENABLED=True)
    def test_confirmed_submission_is_compatible_with_the_runtime_intake_guard(self):
        application = self.submit()
        self.assertEqual(information.declaration(application)['contract'], workflow.CONTRACT)

    def test_confirmation_fields_are_validated_inside_submission(self):
        for changes in ({'confirm_information': False},
                {'applicant_email': 'invalid'}, {'applicant_email': ''}, {'applicant_email': '   '}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.submit(**changes)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_forged_or_stale_grant_cannot_submit(self):
        grant = self.grant()
        for bad in ({**grant, 'entered_name': 'Forged'}, {**grant, 'identity': 'changed'},
                {key: value for key, value in grant.items() if key != 'signature'}):
            with self.assertRaises(ValidationError):
                submit_application(self.program.pk, grant=bad, data=self.data(), files=MultiValueDict())
        Member.objects.filter(pk=self.member.pk).update(contact_number='09990000000')
        self.assertFalse(workflow.secure_grant(grant, self.program))

    def test_unlocked_ewaf_program_cannot_accept_applications(self):
        Program.objects.filter(pk=self.program.pk).update(ewaf_applicable=True)
        self.program.refresh_from_db()
        self.assertFalse(workflow.availability(self.program))
        self.assertContains(self.client.get(self.verify_url), 'Applications are currently unavailable')
        self.assertNotContains(self.client.get(reverse('programs:detail', args=[self.program.pk])), 'Apply for this program')

    def test_receipt_retains_reference_print_download_guidance_and_tracking(self):
        self.client.post(self.verify_url, self.identity())
        response = self.client.post(self.apply_url, self.data(), follow=True)
        self.assertContains(response, 'Save as PDF to download a receipt copy')
        self.assertContains(response, 'Track this application')
        self.assertNotContains(response, 'different@example.invalid')

    def test_publish_records_policy_authorization_in_the_same_action(self):
        program = save_program(user=self.admin, data=program_data(benefit='Synthetic purpose', ewaf_applicable=False))
        change_publication(program.pk, user=self.admin, version=program.version, action='published')
        program.refresh_from_db()
        self.assertEqual(program.policy_authorized_by, self.admin)
        self.assertEqual(program.status, 'published')
        self.assertEqual(list(program.history.order_by('pk').values_list('action', flat=True))[-2:], ['policy_authorized', 'published'])

    def test_published_policy_does_not_authorize_ewaf_configuration_implicitly(self):
        program = save_program(user=self.admin, data=program_data(benefit='Synthetic purpose', ewaf_applicable=True))
        change_publication(program.pk, user=self.admin, version=program.version, action='authorize_policy', notes='Synthetic policy authorization')
        program.refresh_from_db()
        with self.assertRaises(ValidationError):
            change_publication(program.pk, user=self.admin, version=program.version, action='published', notes='Attempt without scoring authorization')
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')

    def test_admin_can_create_ewaf_draft_and_open_settings_before_publication(self):
        from ewaf.operational_models import OperationalConfiguration
        self.client.force_login(self.admin)
        create_url = reverse('programs:create')
        self.assertContains(self.client.get(create_url), 'Save draft')
        data = {key: value for key, value in program_data(
            name='Synthetic EWAF draft', benefit='Synthetic purpose', ewaf_applicable=True).items()
            if value is not None}
        response = self.client.post(create_url, data)
        program = Program.objects.get(name='Synthetic EWAF draft')
        review_url = reverse('programs:manage_detail', args=[program.pk])
        self.assertRedirects(response, review_url)
        self.assertEqual(program.status, 'draft')
        self.assertIsNone(program.policy_authorized_at)
        self.assertFalse(OperationalConfiguration.objects.filter(program=program).exists())
        response = self.client.get(review_url)
        self.assertContains(response, 'Complete program setup')
        self.assertFalse(response.context['detail_ready'])
        settings_url = reverse('ewaf:operational_workspace', args=[program.pk]) + '?settings=1'
        response = self.client.get(settings_url)
        self.assertContains(response, 'Save configuration')
        evidence_url = reverse('ewaf:evidence_policy', args=[program.pk])
        self.assertContains(self.client.get(evidence_url), 'Record evidence definitions')
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')
        self.assertIsNone(program.policy_authorized_at)
        self.assertFalse(OperationalConfiguration.objects.filter(program=program).exists())

    def test_missing_ewaf_publication_explains_recovery_and_preserves_draft(self):
        self.client.force_login(self.admin)
        program = save_program(user=self.admin, data=program_data(benefit='Synthetic purpose', ewaf_applicable=True))
        change_publication(program.pk, user=self.admin, version=program.version,
            action='authorize_policy', notes='Synthetic explicit policy authorization')
        program.refresh_from_db()
        original = Program.objects.values().get(pk=program.pk)
        history = list(program.history.values())
        response = self.client.post(reverse('programs:manage_detail', args=[program.pk]), {
            'version': program.version, 'action': 'published', 'confirm': True,
            'notes': 'Synthetic attempt before EWAF setup'})
        self.assertContains(response, 'Open EWAF settings for this program')
        self.assertContains(response, 'Complete program setup')
        self.assertNotContains(response, 'configuration: no program-specific scoring configuration')
        self.assertNotContains(response, 'Correctable missing information can be completed.')
        self.assertEqual(Program.objects.values().get(pk=program.pk), original)
        self.assertEqual(list(program.history.values()), history)

    def test_program_viewer_without_ewaf_permissions_gets_staff_guidance(self):
        from membership.tests import grant
        viewer = get_user_model().objects.create_user('synthetic-program-viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(viewer)
        program = save_program(user=self.admin, data=program_data(benefit='Synthetic purpose', ewaf_applicable=True))
        response = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertContains(response, 'Publication requires an administrator with publishing permission.')
        self.assertNotContains(response, 'Complete EWAF settings')
        settings_url = reverse('ewaf:operational_workspace', args=[program.pk]) + '?settings=1'
        self.assertEqual(self.client.get(settings_url).status_code, 403)


from ewaf.operational_testsupport import OperationalHelpers


class ConfirmationEvidenceTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()
        self.lock_policy()

    def declare(self):
        source = dict(self.application.source_snapshot)
        source['application_confirmation'] = {'contract': workflow.CONTRACT, 'current_information': 'changed',
            'confirm_information': True, 'change_details': 'Synthetic household change reported for evidence review.'}
        ProgramApplication.objects.filter(pk=self.application.pk).update(source_snapshot=source)
        self.application.refresh_from_db()

    def test_historical_context_and_configuration_source_are_preserved(self):
        from ewaf.evidence import source_context
        from ewaf.operational_services import configuration_source
        self.assertNotIn('current_information', source_context(self.application))
        self.assertNotIn('contract', configuration_source(self.program))
        with override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True):
            self.assertEqual(configuration_source(self.program), self.operational_configuration.source)

    def test_changed_information_blocks_complete_pool_and_is_not_a_scoring_value(self):
        from ewaf.operational_services import inventory
        self.declare()
        rows, accepted, problems = inventory(self.program, [self.application], self.operational_configuration)
        self.assertIn('CURRENT_INFORMATION_REVIEW_REQUIRED', rows[0]['errors'])
        self.assertFalse(accepted)
        with self.assertRaises(ValidationError):
            self.calculate()

    def test_resolution_requires_current_owned_evidence_and_retains_member_values(self):
        from documents.models import DocumentVerification
        self.declare()
        evidence = list(DocumentVerification.objects.filter(document__application=self.application.member.application,
            verified=True).values_list('pk', flat=True))
        self.assertTrue(evidence)
        before = Member.objects.values().get(pk=self.application.member_id)
        token = information.review_token(self.application)
        with self.assertRaises(ValidationError):
            information.resolve(self.application.pk, user=self.officer, expected=token, evidence_ids=[],
                reason='Synthetic evidence review', confirmed=True)
        information.resolve(self.application.pk, user=self.officer, expected=token, evidence_ids=evidence,
            reason='Synthetic accepted evidence reviewed under this program reference period and cutoff.', confirmed=True)
        self.application.refresh_from_db()
        self.assertTrue(information.confirmation_context(self.application)['resolved'])
        self.assertEqual(Member.objects.values().get(pk=self.application.member_id), before)
        self.assertEqual(self.application.history.filter(action=information.ACTION).count(), 1)
        with self.assertRaises(ValidationError):
            information.resolve(self.application.pk, user=self.officer, expected=token, evidence_ids=evidence,
                reason='Stale review must fail', confirmed=True)
        Member.objects.filter(pk=self.application.member_id).update(household_members=7)
        self.application.member.refresh_from_db()
        self.assertFalse(information.confirmation_context(self.application)['resolved'])

    def test_unauthorized_resolution_and_terminal_reopening_are_denied(self):
        self.declare()
        outsider = get_user_model().objects.create_user('unprivileged-reviewer', is_staff=True)
        with self.assertRaises(PermissionDenied):
            information.resolve(self.application.pk, user=outsider, expected=information.review_token(self.application),
                evidence_ids=[], reason='No permission', confirmed=True)
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='CLOSED')
        with self.assertRaisesMessage(ValidationError, 'return-for-review'):
            information.resolve(self.application.pk, user=self.officer, expected=information.review_token(self.application),
                evidence_ids=[], reason='Unsupported reopening', confirmed=True)

    def test_eligibility_confirmation_cannot_bypass_a_change_report(self):
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        self.declare()
        with self.assertRaisesMessage(ValidationError, 'Review and save the reported changes'):
            review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application))

    def test_decision_and_release_preconditions_also_require_resolution(self):
        from assistance.models import AssistanceCase
        from assistance.services import require_current_review
        self.declare()
        case = AssistanceCase.objects.get(application=self.application)
        with self.assertRaisesMessage(ValidationError, 'Review and save the reported changes'):
            require_current_review(case, self.application.program, self.application.member)

    def test_evidence_resolution_audit_failure_rolls_back_application(self):
        from documents.models import DocumentVerification
        self.declare()
        before = ProgramApplication.objects.values().get(pk=self.application.pk)
        evidence = list(DocumentVerification.objects.filter(document__application=self.application.member.application,
            verified=True).values_list('pk', flat=True))
        with patch('programs.services.record_log', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                information.resolve(self.application.pk, user=self.officer,
                    expected=information.review_token(self.application), evidence_ids=evidence,
                    reason='Synthetic review rollback', confirmed=True)
        self.assertEqual(ProgramApplication.objects.values().get(pk=self.application.pk), before)
        self.assertFalse(self.application.history.filter(action=information.ACTION).exists())

    def test_private_staff_update_page_displays_report_and_member_editor(self):
        self.declare()
        route = reverse('programs:information_review', args=[self.application.pk])
        self.assertEqual(Client().get(route).status_code, 302)
        client = Client()
        client.force_login(self.officer)
        response = client.get(route)
        self.assertContains(response, 'Update applicant information')
        self.assertContains(response, 'name="employment_status"')
        self.assertNotContains(response, 'Accepted supporting evidence')
        self.assertContains(response, 'Synthetic household change reported')
        self.assertIn('no-store', response['Cache-Control'])


class PrepublicationConfigurationTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()

    @override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
    def test_locked_terms_configuration_survives_publication_without_rewriting_it(self):
        from ewaf.operational_services import latest_configuration, configuration_source
        Program.objects.filter(pk=self.program.pk).update(status='draft', policy_authorized_at=None, policy_authorized_by=None)
        self.program.refresh_from_db()
        change_publication(self.program.pk, user=self.officer, version=self.program.version,
            action='authorize_policy', notes='Explicit synthetic prepublication program authorization.')
        self.program.refresh_from_db()
        locked = self.lock_policy()
        original = type(locked).objects.values().get(pk=locked.pk)
        self.assertEqual(workflow.publication_configuration_problem(self.program), '')
        self.assertEqual(locked.source['contract'], 'approved_program_terms_v2')
        change_publication(self.program.pk, user=self.officer, version=self.program.version,
            action='published', notes='Publish after the explicit policy and locked calculation approvals.')
        self.program.refresh_from_db()
        self.assertEqual(latest_configuration(self.program).pk, locked.pk)
        self.assertEqual(configuration_source(self.program), locked.source)
        self.assertEqual(type(locked).objects.values().get(pk=locked.pk), original)
        Program.objects.filter(pk=self.program.pk).update(slots=self.program.slots + 1)
        self.program.refresh_from_db()
        self.assertIn('no longer matches', workflow.publication_configuration_problem(self.program))
        with self.assertRaises(ValidationError):
            latest_configuration(self.program)
