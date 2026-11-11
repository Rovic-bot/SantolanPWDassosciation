"""Mandatory EWAF setup and preservation of pre-adoption outcomes."""
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceCase, AssistanceRelease, AssistanceLog
from assistance.services import review_eligibility, record_release, reserved_slots
from assistance.tests import seed_statuses, review_data, release_data
from announcements.models import Announcement, ProgramResultRevision
from announcements.results import prepare_results, results_current
from announcements.services import change_publication as publish_results
from announcements.recorded_results import collect_recorded_results
from members.disability_catalog import current_types
from members.tests import create_member
from .forms import ProgramSetupForm
from .mandatory_ewaf import adopt_existing_programs, retained_selected_ids
from .models import Program, ProgramLog
from .services import save_program, change_publication
from .tests import create_program, program_data
from .test_ui_cleanup import seed_catalog
from .testsupport import application_fixture, private_media


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   CERTIFICATE_EMAIL_BACKGROUND=False, CERTIFICATE_RESEND_ENABLED=False)
class MandatoryEWAFTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_catalog()
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('SYNTHETIC-MANDATORY-EWAF')
        self.client.force_login(self.admin)

    def adopt(self):
        adopt_existing_programs(apps, SimpleNamespace(connection=connection))

    def test_every_created_program_uses_ewaf_even_with_forged_opt_out(self):
        for flag in (False, '', 'false', True):
            program = save_program(user=self.admin, setup_only=True,
                data=program_data(ewaf_applicable=flag, slots=4))
            self.assertTrue(program.ewaf_applicable)
            self.assertEqual(program.slot_limit, 4)
            form = ProgramSetupForm(instance=program)
            self.assertNotIn('ewaf_applicable', form.fields)
            self.assertTrue(form.fields['slots'].required)
            self.assertTrue(form.fields['eligible_disability_types'].required)
        page = self.client.get(reverse('programs:create'))
        self.assertNotContains(page, 'name="ewaf_applicable"')
        self.assertContains(page, 'Select all disability types')
        self.assertNotContains(page, 'Unlimited')

    def test_positive_slots_and_disability_selection_are_required_even_for_private_drafts(self):
        for invalid in ({'slots': ''}, {'slots': None}, {'slots': 0}, {'slots': -1},
                        {'eligible_disability_types': []}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                save_program(user=self.admin, setup_only=True, data=program_data(**invalid))
        self.assertFalse(Program.objects.exists())
        self.assertFalse(ProgramLog.objects.exists())

    def test_select_all_is_an_explicit_complete_selection_and_empty_screening_is_blocked(self):
        ids = list(current_types().filter(is_active=True).values_list('pk', flat=True))
        program = save_program(user=self.admin, setup_only=True,
            data=program_data(slots=3, eligible_disability_types=ids))
        self.assertSetEqual(set(program.eligible_disability_types.values_list('pk', flat=True)), set(ids))
        from .application_workflow import screening
        empty = create_program(ewaf_applicable=True, eligible_disability_types=[])
        self.assertEqual(screening(create_member('SYNTHETIC-EMPTY-TYPES'), empty)[0], 'unable')

    def test_eligible_review_does_not_select_or_generate_ranking(self):
        program = create_program(ewaf_applicable=True)
        application = application_fixture(program, create_member('SYNTHETIC-EWAF-REVIEW'))
        case = review_eligibility(application.pk, user=self.admin, data=review_data(application))
        application.refresh_from_db()
        self.assertEqual((application.status, case.decision), ('ELIGIBLE', 'pending'))
        self.assertIsNone(case.decided_at)
        self.assertNotIn('automatic_selection', application.assistance_history.get().snapshot)
        from ewaf.operational_models import OperationalRun, OperationalDecision
        self.assertFalse(OperationalRun.objects.exists())
        self.assertFalse(OperationalDecision.objects.exists())

    def test_ewaf_setup_cannot_be_bypassed_by_publication(self):
        program = save_program(user=self.admin, setup_only=True, data=program_data(slots=2))
        with self.assertRaises(ValidationError):
            change_publication(program.pk, user=self.admin, version=program.version, action='published')
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')
        self.assertIsNone(program.policy_authorized_at)

    def legacy_outcome(self):
        """Retained pre-change fixture; never a new authorization path."""
        program = create_program(ewaf_applicable=False, slots=3,
            registration_closes_at=timezone.now() - timezone.timedelta(minutes=1))
        application = application_fixture(program, create_member(f'SYNTHETIC-OLD-{program.pk}'))
        AssistanceCase.objects.create(application=application, eligibility_id='eligible',
            eligibility_label='Eligible', checklist=[{'key': 'membership', 'required': True, 'result': 'pass'}],
            review_notes='Synthetic original review.', reviewed_at=timezone.now(), reviewed_by=self.admin,
            member_version=application.member.version, program_version=program.version,
            decision='approved', decision_notes='Synthetic original selection.',
            decided_at=timezone.now(), decided_by=self.admin)
        application.status = 'SELECTED'
        application.save(update_fields=['status'])
        item = prepare_results(program.pk, user=self.admin, version=0, reason='Synthetic earlier publication.', recorded=True)
        publish_results(item.pk, user=self.admin, version=item.version, action='published')
        receipt = record_release(application.pk, user=self.admin, data=release_data(application))
        return program, application, item, receipt

    def test_adoption_preserves_issued_results_receipts_and_existing_capacity(self):
        program, application, item, receipt = self.legacy_outcome()
        old_version = program.version
        before_receipt = AssistanceRelease.objects.values().get(pk=receipt.pk)
        before_revisions = list(ProgramResultRevision.objects.values())
        before_cases = list(AssistanceCase.objects.values())
        before_logs = list(AssistanceLog.objects.values())
        item.refresh_from_db()
        self.assertTrue(results_current(item))
        self.adopt()
        program.refresh_from_db()
        self.assertTrue(program.ewaf_applicable)
        self.assertEqual((program.slots, program.version), (3, old_version + 1))
        self.assertEqual(AssistanceRelease.objects.values().get(pk=receipt.pk), before_receipt)
        self.assertEqual(list(ProgramResultRevision.objects.values()), before_revisions)
        self.assertEqual(list(AssistanceCase.objects.values()), before_cases)
        self.assertEqual(list(AssistanceLog.objects.values()), before_logs)
        item = Announcement.objects.get(pk=item.pk)
        self.assertTrue(results_current(item))
        receipt.refresh_from_db()
        from ewaf.revised.fulfillment import verified_receipt
        self.assertIsNone(verified_receipt(receipt)[1])
        self.assertEqual(retained_selected_ids(program), {application.pk})
        self.assertEqual(reserved_slots(program), 1)
        self.assertEqual(len(collect_recorded_results(program)[0]['rows']), 1)
        self.adopt()
        self.assertEqual(program.history.filter(action='ewaf_required').count(), 1)
        application.refresh_from_db()
        application.selection = None
        application.received = True
        from reports.services import report_row
        self.assertEqual(report_row('applications', application, reveal_assistance=True)[6],
                         'Selected (previous approval)')
        self.client.force_login(self.admin)
        page = self.client.get(reverse('admin:admin_logentry_changelist'),
            {'activity': 'Program EWAF setting changed', 'kind': 'change'})
        self.assertContains(page, 'Program EWAF setting changed')

    def test_existing_all_type_policy_and_locked_sources_are_retained(self):
        program = create_program(ewaf_applicable=True, slots=3, eligible_disability_types=[])
        version = program.version
        self.adopt()
        program.refresh_from_db()
        self.assertEqual(program.version, version)
        self.assertFalse(program.eligible_disability_types.exists())
        self.assertTrue(program.allows_all_disability_types)
        form = ProgramSetupForm(instance=program)
        self.assertEqual(len(form.initial['eligible_disability_types']), current_types().filter(is_active=True).count())
        self.assertTrue(form.fields['eligible_disability_types'].required)
        self.assertTrue(form.fields['eligible_disability_types'].disabled)

    def test_failed_adoption_audit_rolls_back_conversion(self):
        program = create_program(ewaf_applicable=False, slots=3)
        with patch.object(ProgramLog, 'save', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.adopt()
        program.refresh_from_db()
        self.assertFalse(program.ewaf_applicable)

    def test_forward_migration_works_with_historical_model_registry(self):
        from django.db.migrations.loader import MigrationLoader
        state = MigrationLoader(None).project_state([('programs', '0010_mandatory_ewaf')], at_end=False)
        program = create_program(ewaf_applicable=False, slots=3)
        adopt_existing_programs(state.apps, SimpleNamespace(connection=connection))
        program.refresh_from_db()
        self.assertTrue(program.ewaf_applicable)
        self.assertEqual(program.slots, 3)
        self.assertEqual(program.history.filter(action='ewaf_required').count(), 1)

    def test_receipt_and_strict_roster_publications_retain_their_original_sources(self):
        for mode in ('recipients', 'roster'):
            with self.subTest(mode=mode):
                program, application, item, receipt = self.legacy_outcome()
                item.refresh_from_db()
                revision = prepare_results(program.pk, user=self.admin, version=item.version,
                    reason='Synthetic original final publication.', **{mode: True})
                publish_results(revision.pk, user=self.admin, version=revision.version, action='published')
                revision.refresh_from_db()
                before = revision.result_revision.public_payload
                self.assertTrue(results_current(revision))
                self.adopt()
                revision = Announcement.objects.get(pk=revision.pk)
                self.assertTrue(results_current(revision))
                self.assertEqual(revision.result_revision.public_payload, before)
