"""Readable action labels, matching filters, and preserved audit boundaries."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from announcements.models import Announcement, AnnouncementEvent
from assistance.models import AssistanceLog
from membership.models import MembershipEvent
from membership.tests import grant
from members.tests import create_member
from programs.models import ProgramLog
from programs.tests import create_program
from programs.testsupport import application_fixture, private_media
from scripts.durable_test_runner import require_disposable


def activity_fixture():
    require_disposable()
    actor = User.objects.create_superuser('synthetic_audit_admin')
    member = create_member('FICTIONAL-AUDIT-001')
    program = create_program(name='Synthetic community support', eligible_disability_types=[])
    application = application_fixture(program, member)
    common = {'actor': actor, 'actor_label': actor.username}
    program_log = ProgramLog.objects.create(program=program, action='updated', notes='Synthetic schedule correction.', **common)
    membership_log = MembershipEvent.objects.create(application=member.application, action='approved',
        description='Synthetic membership approval.', **common)
    eligibility = AssistanceLog.objects.create(application=application, action='eligibility_reviewed',
        snapshot={'after': {'eligibility': 'eligible'}}, notes='Synthetic eligibility review.', **common)
    selected = AssistanceLog.objects.create(application=application, action='decision_recorded',
        snapshot={'after': {'decision': 'approved'}}, notes='Synthetic selection.', **common)
    released = AssistanceLog.objects.create(application=application, action='assistance_released',
        snapshot={}, notes='Synthetic release.', **common)
    notice = Announcement.objects.create(title='Synthetic program results', content='Synthetic notice')
    published = AnnouncementEvent.objects.create(announcement=notice, action='results_published',
        description='Synthetic publication.', **common)
    return actor, program, application, [program_log, membership_log, eligibility, selected, released, published]


class AdministrationActivityTests(TestCase):
    def setUp(self):
        private_media(self)
        self.actor, self.program, self.application, self.logs = activity_fixture()
        self.client.force_login(self.actor)
        self.url = reverse('admin:admin_logentry_changelist')

    def test_each_requested_action_has_the_same_label_in_list_and_filter(self):
        expected = ('Program changed', 'Member approved', 'Member marked eligible',
                    'Assistance approved / member selected', 'Assistance released', 'Results published')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        choices = dict(response.context['form'].fields['activity'].choices)
        for label in expected:
            with self.subTest(label=label):
                self.assertEqual(choices[label], label)
                filtered = self.client.get(self.url, {'activity': label})
                self.assertEqual(filtered.context['page'].paginator.count, 1)
                self.assertEqual(filtered.context['page'][0]['activity_label'], label)

    def test_history_uses_recorded_outcome_and_never_writes_or_leaks_raw_snapshots(self):
        AssistanceLog.objects.create(application=self.application, actor=self.actor, actor_label=self.actor.username,
            action='eligibility_reviewed', notes='A later fictional review.',
            snapshot={'after': {'eligibility': 'ineligible', 'private_marker': 'PRIVATE-SNAPSHOT-MARKER'}})
        original = list(AssistanceLog.objects.values())
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url, {'activity': 'Member marked eligible'})
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertEqual(list(AssistanceLog.objects.values()), original)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for query in queries))
        self.assertNotContains(response, 'PRIVATE-SNAPSHOT-MARKER')
        self.assertEqual(self.client.get(self.url, {'activity': 'Member marked ineligible'}).context['page'].paginator.count, 1)

    def test_search_section_admin_and_local_date_filters_combine(self):
        other = User.objects.create_superuser('synthetic_other_admin')
        old = ProgramLog.objects.create(program=self.program, actor=other, actor_label=other.username,
            action='updated', notes='Old fictional correction.')
        ProgramLog.objects.filter(pk=old.pk).update(occurred_at=timezone.now() - timedelta(days=2))
        today = timezone.localdate().isoformat()
        response = self.client.get(self.url, {'q': 'program changed', 'area': 'programs',
            'activity': 'Program changed', 'actor': self.actor.username, 'date_from': today, 'date_to': today})
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertEqual(response.context['page'][0]['activity_id'], str(self.logs[0].pk))
        for values in ({'date_from': 'bad'}, {'date_from': today, 'date_to': '2000-01-01'},
                       {'activity': 'made-up-action'}, {'area': 'private-unlisted-area'}):
            self.assertEqual(self.client.get(self.url, values).context['page'].paginator.count, 0)

    def test_domain_permissions_and_read_only_details_are_enforced(self):
        reader = User.objects.create_user('synthetic_audit_reader', is_staff=True)
        self.client.force_login(reader)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        grant(reader, 'admin.view_logentry')
        self.assertEqual(self.client.get(self.url).context['page'].paginator.count, 0)
        detail = reverse('admin:administration_activity', args=['program', self.logs[0].pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        grant(reader, 'programs.view_program', 'programs.view_programapplication')
        self.assertEqual(self.client.get(self.url).context['page'].paginator.count, 1)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(detail, {}).status_code, 405)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)
        self.assertEqual(Client().get(self.url).status_code, 302)
        self.assertEqual(self.client.get(reverse('admin:administration_activity', args=['not-a-source', '1'])).status_code, 404)

    def test_pagination_preserves_filters_and_orders_mixed_sources(self):
        ProgramLog.objects.bulk_create([ProgramLog(program=self.program, actor=self.actor, actor_label=self.actor.username,
            action='updated', notes=f'Synthetic additional change {index}.') for index in range(32)])
        response = self.client.get(self.url, {'activity': 'Program changed', 'area': 'programs', 'p': 2})
        self.assertEqual(response.context['page'].paginator.count, 33)
        self.assertEqual(len(response.context['page']), 3)
        self.assertContains(response, 'activity=Program+changed&amp;area=programs&amp;p=1')
        all_records = list(self.client.get(self.url).context['page'])
        self.assertEqual([row['activity_time'] for row in all_records],
                         sorted((row['activity_time'] for row in all_records), reverse=True))

    def test_public_submissions_are_not_misattributed_and_unknown_actions_remain_visible(self):
        ProgramLog.objects.create(program=self.program, action='submitted', notes='Public submission')
        unknown = ProgramLog.objects.create(program=self.program, actor=None, actor_label='Former administrator',
            action='future_recorded_action', notes='<script>synthetic()</script>')
        response = self.client.get(self.url)
        self.assertEqual(response.context['page'].paginator.count, 7)
        row = self.client.get(self.url, {'activity': 'Program activity recorded'}).context['page'][0]
        self.assertEqual(row['activity_actor'], 'Former administrator')
        detail = self.client.get(reverse('admin:administration_activity', args=['program', unknown.pk]))
        self.assertContains(detail, '&lt;script&gt;')
        self.assertNotContains(detail, '<script>synthetic()</script>')

    def test_summary_counts_categories_and_exact_action_filters_share_the_same_records(self):
        response = self.client.get(self.url)
        self.assertEqual([metric['value'] for metric in response.context['metrics']], [6, 2, 0, 1])
        approvals = self.client.get(self.url, {'kind': 'approval'})
        self.assertEqual(approvals.context['page'].paginator.count, 2)
        self.assertEqual({row['activity_label'] for row in approvals.context['page']},
                         {'Member approved', 'Assistance approved / member selected'})
        self.assertEqual([metric['value'] for metric in approvals.context['metrics']], [2, 2, 0, 0])
        self.assertEqual(self.client.get(self.url, {'kind': 'approval', 'activity': 'Program changed'})
                         .context['page'].paginator.count, 0)
        ProgramLog.objects.create(program=self.program, actor=self.actor, actor_label=self.actor.username,
                                  action='document_downloaded', notes='Synthetic authorized access.')
        access = self.client.get(self.url, {'kind': 'access', 'area': 'programs'})
        self.assertEqual(access.context['page'].paginator.count, 1)
        self.assertEqual(access.context['page'][0]['activity_label'], 'Document downloaded')
        self.assertEqual([metric['value'] for metric in access.context['metrics']], [1, 0, 1, 0])
        reader = User.objects.create_user('synthetic_summary_reader', is_staff=True)
        grant(reader, 'admin.view_logentry')
        self.client.force_login(reader)
        self.assertEqual([metric['value'] for metric in self.client.get(self.url).context['metrics']], [0, 0, 0, 0])

    def test_preset_dates_use_inclusive_local_days_and_keep_custom_dates(self):
        from datetime import datetime, time
        first_day = timezone.localdate() - timedelta(days=6)
        boundary = timezone.make_aware(datetime.combine(first_day, time.min))
        ProgramLog.objects.filter(pk=self.logs[0].pk).update(occurred_at=boundary)
        values = {'period': '7', 'activity': 'Program changed'}
        self.assertEqual(self.client.get(self.url, values).context['page'].paginator.count, 1)
        ProgramLog.objects.filter(pk=self.logs[0].pk).update(occurred_at=boundary - timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url, values).context['page'].paginator.count, 0)
        self.assertEqual(self.client.get(self.url, {'period': 'today', 'activity': 'Program changed'})
                         .context['page'].paginator.count, 0)
        self.assertEqual(self.client.get(self.url, {'period': 'custom', 'date_to': first_day.isoformat(),
            'activity': 'Program changed'}).context['page'].paginator.count, 1)
        self.assertEqual(self.client.get(self.url, {'period': 'unrecognized'}).context['page'].paginator.count, 0)

    def test_inspect_fragment_keeps_permissions_escaping_and_read_only_access(self):
        log = self.logs[0]
        ProgramLog.objects.filter(pk=log.pk).update(notes='<script>not_executable()</script>')
        url = reverse('admin:administration_activity', args=['program', log.pk])
        response = self.client.get(url, {'dialog': '1'})
        self.assertContains(response, 'data-activity-detail')
        self.assertContains(response, '&lt;script&gt;not_executable()&lt;/script&gt;')
        self.assertNotContains(response, '<html')
        self.assertNotContains(response, '<script>not_executable()')
        self.assertIn('private', response.headers['Cache-Control'])
        self.assertEqual(self.client.post(url + '?dialog=1', {}).status_code, 405)
        self.assertEqual(Client().get(url, {'dialog': '1'}).status_code, 302)
        reader = User.objects.create_user('synthetic_popup_reader', is_staff=True)
        grant(reader, 'admin.view_logentry')
        self.client.force_login(reader)
        self.assertEqual(self.client.get(url, {'dialog': '1'}).status_code, 404)

    def test_inspect_explains_recorded_changes_without_showing_technical_payloads_or_rewriting_history(self):
        log = self.logs[0]
        digest = 'a' * 64
        ProgramLog.objects.filter(pk=log.pk).update(notes=digest, changes={
            'name': {'before': 'Previous name', 'after': 'New name'},
            'registration_closes_at': {'before': None, 'after': '2026-11-30T09:00:00'},
            'private_snapshot': {'after': 'PRIVATE-SNAPSHOT-MARKER'},
        })
        original = list(ProgramLog.objects.values())
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('admin:administration_activity', args=['program', log.pk]), {'dialog': '1'})
        self.assertContains(response, 'Changed the program details. Updated the name and application closing date.')
        for technical in (digest, 'registration_closes_at', 'PRIVATE-SNAPSHOT-MARKER'):
            self.assertNotContains(response, technical)
        self.assertEqual(list(ProgramLog.objects.values()), original)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for query in queries))

    def test_inspect_distinguishes_approval_eligibility_and_actual_release_and_keeps_written_notes(self):
        expected = [('membership', 1, "Approved this person&#x27;s Association membership."),
                    ('assistance', 2, 'Marked this member as eligible for the program.'),
                    ('assistance', 3, 'Approved this member for assistance.'),
                    ('assistance', 4, 'Recorded the assistance given to this member.'),
                    ('announcement', 5, 'Published the program results for the public to view.')]
        for source, index, text in expected:
            with self.subTest(source=source, index=index):
                response = self.client.get(reverse('admin:administration_activity', args=[source, self.logs[index].pk]), {'dialog': '1'})
                self.assertContains(response, text)
        ProgramLog.objects.filter(pk=self.logs[0].pk).update(notes='[Office review] Corrected the schedule after checking with the organizer.')
        response = self.client.get(reverse('admin:administration_activity', args=['program', self.logs[0].pk]))
        self.assertContains(response, '[Office review] Corrected the schedule after checking with the organizer.')

    def test_native_notes_explain_hashes_and_exports_but_preserve_normal_django_change_messages(self):
        import json
        from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
        from django.contrib.contenttypes.models import ContentType
        weight = LogEntry.objects.create(user=self.actor, action_flag=ADDITION, object_repr='Synthetic weights',
            content_type=ContentType.objects.get(app_label='ewaf', model='vaultrevision'),
            object_id='synthetic', change_message='b' * 64)
        report = LogEntry.objects.create(user=self.actor, action_flag=CHANGE, object_repr='Synthetic member report',
            change_message='Report csv; rows=12; start=; end=; program=; status=; assistance_type=.')
        account = LogEntry.objects.create(user=self.actor, action_flag=CHANGE, object_repr='Synthetic account',
            content_type=ContentType.objects.get_for_model(User),
            change_message=json.dumps([{'changed': {'fields': ['first name', 'last name']}}]))
        for item, text in ((weight, 'Saved a version of the EWAF scoring weights.'),
                           (report, 'Exported a CSV copy of the report containing 12 records.'),
                           (account, 'Changed first name and last name.')):
            with self.subTest(item=item.pk):
                original = item.change_message
                response = self.client.get(reverse('admin:administration_activity', args=['administration', item.pk]), {'dialog': '1'})
                self.assertContains(response, text)
                self.assertNotContains(response, 'b' * 64)
                self.assertNotContains(response, 'rows=12')
                item.refresh_from_db()
                self.assertEqual(item.change_message, original)


from ewaf.operational_testsupport import OperationalHelpers


class SelectionActivityTests(OperationalHelpers, TransactionTestCase):
    def test_ewaf_selection_uses_immutable_decision_and_hides_its_duplicate_digest(self):
        self.setup_operational()
        self.lock_policy()
        run = self.calculate()
        selected = self.choose(run)
        self.choose(run, expected_revision=1, outcome='NOT_SELECTED', reason='Fictional changed human decision.')
        grant(self.officer, 'admin.view_logentry')
        self.client.force_login(self.officer)
        url = reverse('admin:admin_logentry_changelist')
        response = self.client.get(url, {'activity': 'Member selected', 'area': 'ewaf'})
        self.assertEqual(response.context['page'].paginator.count, 1)
        row = response.context['page'][0]
        self.assertEqual(row['activity_source'], 'selection')
        self.assertEqual(row['activity_id'], str(selected.pk))
        self.assertNotContains(response, selected.digest)
        self.assertEqual(self.client.get(url, {'activity': 'Member not selected'}).context['page'].paginator.count, 1)
        detail = self.client.get(reverse('admin:administration_activity', args=['selection', selected.pk]), {'dialog': '1'})
        self.assertContains(detail, 'Selected this member for the program.')
        self.assertNotContains(detail, 'Recorded that this member was not selected')
        self.assertEqual(detail.context['additional_note'], selected.reason)
        selected.refresh_from_db()
        selected.clean()
