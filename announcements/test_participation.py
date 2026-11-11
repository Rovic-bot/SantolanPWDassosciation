"""Owner-authorized applicant/selected tables, with full program references."""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from assistance.services import review_eligibility, decide_assistance
from assistance.tests import review_data, decision_data
from members.tests import create_member
from programs.models import ProgramApplication
from programs.testsupport import application_fixture
from ewaf.operational_testsupport import OperationalHelpers
from ewaf import operational_services
from .models import Announcement, ProgramResultRevision
from .results import prepare_results, results_current
from .participation import collect_program_results, public_program_participation
from . import test_results as legacy_results


class ProgramParticipationTests(TestCase):
    setUp = legacy_results.ProgramResultTests.setUp
    publish = legacy_results.ProgramResultTests.publish

    def draft(self, version=0):
        return prepare_results(self.program.pk, user=self.admin, version=version,
            reason='Synthetic owner-authorized roster preview.', roster=True)

    def notice(self):
        return Announcement.objects.create(linked_program=self.program, title='Program notice',
            content='Program information', source_office='Synthetic office',
            status='published', published_at=timezone.now())

    def test_two_tables_include_all_applicants_and_only_confirmed_selections(self):
        other = application_fixture(self.program, create_member('ROSTER-OTHER'))
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        decide_assistance(other.pk, user=self.admin, data=decision_data(other, decision='rejected'))
        item = self.publish(self.draft())
        payload = item.result_revision.public_payload
        self.assertEqual(payload['schema'], 2)
        self.assertEqual(payload['applicant_count'], 2)
        self.assertEqual([row['reference'] for row in payload['rows']], [self.application.public_reference])
        self.assertEqual(set(payload['applicants'][0]), {'name','reference','status','ambiguous'})
        for route in ('announcements:detail','core:result_detail'):
            response = Client().get(reverse(route, args=[item.pk]))
            self.assertContains(response, 'Members who applied')
            self.assertContains(response, 'Selected members')
            self.assertContains(response, self.application.public_reference, count=2)
            self.assertContains(response, other.public_reference, count=1)
            for private in (self.member.full_name, self.member.control_number, self.application.status_token,
                            str(self.application.pk), item.result_revision.source_digest, item.result_revision.reason):
                self.assertNotContains(response, private)

    def test_open_announcement_lists_applicants_and_remains_visible_after_closing(self):
        self.program.registration_closes_at = timezone.now() + timezone.timedelta(days=1)
        self.program.save()
        item = self.notice()
        url = reverse('announcements:detail', args=[item.pk])
        response = Client().get(url)
        self.assertContains(response, self.application.public_reference, count=1)
        self.assertContains(response, 'Selection results are pending')
        self.program.registration_closes_at = timezone.now() - timezone.timedelta(days=1)
        self.program.save()
        response = Client().get(url)
        self.assertContains(response, self.application.public_reference, count=2)
        self.assertNotIn('member', response.context['participation'])
        self.program.status = 'cancelled'
        self.program.save()
        self.assertEqual(Client().get(url).status_code, 404)

    def test_source_changes_withhold_snapshot_and_live_selection_without_losing_applicant_list(self):
        item = self.publish(self.draft())
        notice = self.notice()
        other = application_fixture(self.program, create_member('ROSTER-PENDING'))
        self.assertFalse(results_current(item))
        self.assertEqual(Client().get(reverse('announcements:detail', args=[item.pk])).status_code, 404)
        response = Client().get(reverse('announcements:detail', args=[notice.pk]))
        self.assertContains(response, other.public_reference)
        self.assertContains(response, 'Selection results are pending')
        self.assertFalse(response.context['participation']['selection_ready'])

    def test_full_references_resolve_same_name_and_suffix_without_extra_name_disclosure(self):
        other = application_fixture(self.program, create_member('ROSTER-COLLISION'))
        other.member.full_name = self.member.full_name
        other.member.save()
        ProgramApplication.objects.filter(pk=other.pk).update(public_reference='OLD-'+self.application.public_reference[-4:])
        other.refresh_from_db()
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        decide_assistance(other.pk, user=self.admin, data=decision_data(other))
        payload, _ = collect_program_results(self.program)
        self.assertEqual(len({row['reference'] for row in payload['rows']}), 2)
        self.assertEqual({row['name'] for row in payload['rows']}, {'J*** D*** C***'})
        self.assertTrue(all(not row['ambiguous'] for row in payload['rows']))

    def test_unified_prepare_routes_need_no_typed_reason_and_use_same_schema(self):
        for route in ('announcements:prepare_results','announcements:prepare_recipients'):
            response = self.client.get(reverse(route, args=[self.program.pk]))
            self.assertContains(response, 'Prepare and publish program results')
            self.assertNotContains(response, 'name="reason"')
            self.assertNotContains(response, 'name="confirm"')
        response = self.client.post(reverse('announcements:prepare_recipients', args=[self.program.pk]),
                                    {'program':str(self.program.pk),'version':0})
        item = Announcement.objects.get(program=self.program)
        self.assertRedirects(response, reverse('announcements:manage_detail', args=[item.pk]))
        self.assertEqual(item.result_revision.public_payload['kind'], 'program_participation')
        preview = self.client.get(reverse('announcements:manage_detail', args=[item.pk]))
        self.assertContains(preview, 'Publish program results')
        self.assertNotContains(preview, '<select name="action"')

    def test_historical_revision_remains_byte_for_byte_and_can_be_superseded(self):
        old = prepare_results(self.program.pk, user=self.admin, version=0, reason='Historical mask.')
        previous = old.result_revision
        before = previous.public_payload.copy()
        new = self.draft(old.version)
        previous.refresh_from_db()
        self.assertEqual(previous.public_payload, before)
        self.assertTrue(previous.public_payload['rows'][0]['reference'].startswith('****'))
        self.assertEqual(new.result_revision.public_payload['rows'][0]['reference'], self.application.public_reference)
        self.assertEqual(ProgramResultRevision.objects.count(), 2)

    def test_preparation_audit_failure_rolls_back_snapshot(self):
        with patch('announcements.results.record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.draft()
        self.assertFalse(Announcement.objects.exists())
        self.assertFalse(ProgramResultRevision.objects.exists())


class EWAFParticipationTests(OperationalHelpers, TransactionTestCase):
    def test_only_current_confirmed_ewaf_selection_can_populate_selected_table(self):
        self.setup_operational()
        self.lock_policy()
        run = self.calculate()
        before = run.payload()
        with self.assertRaises(ValidationError):
            collect_program_results(self.program)
        pending = public_program_participation(self.program)
        self.assertFalse(pending['selection_ready'])
        operational_services.record_decision(self.program.pk, user=self.officer, run_id=run.pk,
            application_id=self.application.pk, expected_revision=0, outcome='SELECTED',
            reason='Synthetic confirmed EWAF selection.')
        payload, _ = collect_program_results(self.program)
        self.assertTrue(payload['selection_ready'])
        self.assertEqual(payload['rows'][0]['reference'], self.application.public_reference)
        self.assertNotIn('score', payload['rows'][0])
        self.assertNotIn('rank', payload['rows'][0])
        run.refresh_from_db()
        self.assertEqual(run.payload(), before)
