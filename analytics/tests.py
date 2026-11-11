"""Synthetic analytics fixtures; run only on the verified disposable test database."""
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from unittest.mock import Mock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import connection, OperationalError
from django.db.models import QuerySet
from django.template import engines
from django.template.loader import render_to_string
from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from django.utils import timezone

from assistance.models import AssistanceCase, AssistanceRelease, EligibilityStatus
from assistance.referral_models import ReferralGrant, ReferralTicket, referral_write
from events.models import Event
from events.observance_models import AnnualObservance
from members.models import Member, DisabilityType
from membership.models import MembershipApplication
from membership.tests import profile, grant
from programs.models import Program, ProgramApplication
from .forms import ActivityRangeForm
from . import services
from .visualizations import simple

ZONE = ZoneInfo('Asia/Manila')
NOW = datetime(2026, 10, 29, 12, tzinfo=ZONE)


def only_reads(execute, sql, params, many, context):
    if sql.lstrip().split()[0].upper() not in ('SELECT', 'SHOW', 'EXPLAIN'):
        raise AssertionError('Dashboard tried to write: ' + sql.split()[0])
    return execute(sql, params, many, context)


def values(**changes):
    form = ActivityRangeForm({'period': 'custom', 'start': '2026-05-01', 'end': '2026-10-29', **changes}, today=NOW.date())
    assert form.is_valid(), form.errors
    return form.cleaned_data


class DateRangeTests(SimpleTestCase):
    def test_presets_and_timezone_half_open_end(self):
        for period, start in [('six_months', date(2026, 5, 1)), ('30_days', date(2026, 9, 30)), ('year', date(2026, 1, 1))]:
            form = ActivityRangeForm({'period': period, 'start': 'ignored'}, today=NOW.date())
            self.assertTrue(form.is_valid())
            self.assertEqual(form.cleaned_data['start'], start)
            self.assertEqual(form.cleaned_data['upper'], datetime(2026, 10, 30, tzinfo=ZONE))

    def test_invalid_excessive_and_missing_ranges(self):
        for changes in [{'start': ''}, {'end': 'bad'}, {'start': '2026-11-01'},
                        {'start': '2020-01-01'}, {'period': 'invalid'},
                        {'start': '9999-12-31', 'end': '9999-12-31'}]:
            form = ActivityRangeForm({'period': 'custom', 'start': '2026-05-01', 'end': '2026-10-29', **changes})
            self.assertFalse(form.is_valid())

    def test_leap_day_future_and_partial_months(self):
        data = values(start='2028-02-29', end='2028-03-01')
        months = list(services.month_ranges(data))
        self.assertEqual([row[0] for row in months], ['Feb 2028', 'Mar 2028'])
        self.assertEqual(months[0][1], data['lower'])
        self.assertEqual(months[-1][2], data['upper'])

    def test_unknown_state_and_missing_timestamp_are_not_discarded(self):
        source = Mock()
        source.order_by.return_value.values.return_value.annotate.return_value = [
            {'status': 'private-unknown-text', 'count': 2}, {'status': None, 'count': 1}]
        self.assertEqual(services.state_counts(source, 'status', []),
                         [('Not recorded', 1), ('Unrecognized state', 2)])
        source.filter.return_value.aggregate.return_value = {'total': 0, 'undated': 2, **{f'm{i}': 0 for i in range(6)}}
        totals, rows = services.activity(source, 'joined_at', values())
        self.assertEqual((totals['total'], totals['undated'], sum(n for _, n in rows)), (0, 2, 0))


@override_settings(REFERRAL_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class OverviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('synthetic_dashboard_admin')
        cls.limited = get_user_model().objects.create_user('synthetic_dashboard_limited', is_staff=True)
        grant(cls.limited, 'accounts.access_dashboard')
        visual = DisabilityType.objects.get_or_create(name='Visual Disability')[0]
        hearing = DisabilityType.objects.get_or_create(name='Deaf or Hard of Hearing')[0]
        cls.members = []
        for i in range(4):
            data = {**profile(), 'control_number': f'SYNTH-DASH-{i}', 'full_name': f'Private fixture name {i}'}
            intake = MembershipApplication.objects.create(**data, submission_key=uuid4(), status='approved')
            member = Member.objects.create(**data, application=intake,
                joined_at=datetime(2026, [5, 6, 10, 10][i], 5, tzinfo=ZONE),
                is_active=i not in (1, 3), archived_at=NOW if i == 3 else None,
                disability_type=visual if i in (0, 1) else None)
            cls.members.append(member)
        for member, birthdate in zip(cls.members, ['2016-10-29', '1986-10-30', '1956-10-29', '1926-10-29']):
            Member.objects.filter(pk=member.pk).update(birthdate=birthdate)
        cls.members[0].disability_types.set([visual, hearing])
        MembershipApplication.objects.create(**{**profile(), 'control_number': 'PENDING-ONLY'}, submission_key=uuid4())
        cls.programs = []
        for i in range(3):
            cls.programs.append(Program.objects.create(name=['Synthetic Health Support', 'Synthetic School Assistance', 'Synthetic Community Supplies'][i], description='Synthetic',
                assistance_type='Support', registration_opens_at=NOW-timedelta(days=200), slots=[None, 10, 20][i],
                registration_closes_at=NOW+timedelta(days=1) if i == 0 else NOW-timedelta(days=1),
                status='draft' if i == 2 else 'published', published_at=NOW-timedelta(days=40) if i != 2 else None,
                policy_authorized_at=NOW-timedelta(days=40), photo_instructions='Synthetic instructions', selection_method='Synthetic method'))
        cls.applications = []
        for i, status in enumerate(['COMPLETED', 'COMPLETED', 'SELECTED', 'NEEDS_INFORMATION', 'INELIGIBLE', 'PENDING_PHOTO_VERIFICATION']):
            app = ProgramApplication.objects.create(program=cls.programs[i % 3], member=cls.members[i // 3],
                public_reference=f'SYNTH-APPLICATION-{i}', status=status)
            ProgramApplication.objects.filter(pk=app.pk).update(submitted_at=datetime(2026, [5, 6, 9, 10, 10, 10][i], [3, 5, 15, 3, 23, 24][i], 12, tzinfo=ZONE))
            cls.applications.append(app)
        EligibilityStatus.objects.get_or_create(code='eligible', defaults={'label': 'Eligible'})
        for app in cls.applications[:3]:
            AssistanceCase.objects.create(application=app, eligibility_id='eligible', eligibility_label='Eligible',
                reviewed_at=NOW, member_version=0, program_version=0, decision='approved')
        for i, app in enumerate(cls.applications[:3]):
            AssistanceRelease.objects.create(application=app, active_application=app if i != 2 else None,
                assistance_type='Support', benefit='Synthetic benefit', released_on=date(2026, 10, 29),
                voided_at=NOW if i == 2 else None)
        for status in ('published', 'cancelled'):
            Event.objects.create(title='Private synthetic event', starts_at=NOW, ends_at=NOW+timedelta(hours=2),
                                 status=status, published_at=NOW-timedelta(days=1), location='Synthetic')
        AnnualObservance.objects.create(title='Reference only', month=10, recurrence_kind='whole_month',
            status='draft', legal_basis='Synthetic', description='Reference, not an activity')
        with referral_write():
            for i, status in enumerate(ReferralTicket.Status.values):
                token = ReferralGrant.objects.create(member=cls.members[0], expires_at=NOW+timedelta(hours=1))
                ticket = ReferralTicket.objects.create(grant=token, member=cls.members[0], reference=f'SYNTH-DESK-{i}',
                    full_name='PRIVATE DESK NAME', email='private@example.invalid', subject='PRIVATE SUBJECT',
                    concern='PRIVATE MEDICAL TEXT', assistance_type='medical', acknowledgement=True,
                    member_snapshot={}, status=status)
                # Test-only timestamp placement; the production append-only manager stays intact.
                QuerySet(model=ReferralTicket).filter(pk=ticket.pk).update(received_at=NOW-timedelta(days=i))

    def projection(self, **changes):
        with connection.execute_wrapper(only_reads):
            return services.overview(self.admin, values(**changes), now=NOW)

    def test_totals_overlap_and_release_recipients(self):
        data = self.projection()
        self.assertEqual([item['value'] for item in data['metrics']], ['3', '4', '2', '1', '2', '5', '1', '2'])
        self.assertEqual(data['members']['new'], 4)
        self.assertEqual({row['label']: row['count'] for row in data['members']['disability']['rows']},
                         {'Visual Disability': 2, 'Deaf or Hard of Hearing': 1, 'Classification not recorded': 1})
        self.assertEqual(data['releases']['recipients'], 1)
        self.assertEqual(data['eligibility']['total'], 6)
        self.assertEqual(data['applications']['chart']['total'], 6)
        self.assertEqual(data['events']['total'], 2)
        self.assertEqual(data['desk']['chart']['total'], 5)

    def test_current_snapshots_do_not_change_for_empty_period(self):
        data = self.projection(start='2020-01-01', end='2020-01-31')
        self.assertEqual([item['value'] for item in data['metrics']], ['3', '4', '0', '1', '0', '0', '0', '0'])
        self.assertEqual(data['members']['growth']['total'], 0)

    def test_live_completion_and_release_mix_do_not_count_selection_or_voids(self):
        data = self.projection()
        self.assertEqual(data['applications']['completed'], 2)
        self.assertEqual(data['applications']['pending'], 1)
        self.assertEqual(data['releases']['mix'], [('Support', 2)])
        charts = {chart['id']: chart for chart in data['visualizations']}
        self.assertEqual(charts['disability-bar']['payload']['denominator'], 3)
        self.assertEqual(sum(charts['disability-bar']['payload']['series'][0]['values']), 4)
        self.assertEqual(charts['disability-bar']['kind'], 'member-donut')
        self.assertEqual(charts['disability-bar']['total'], 4)
        self.assertEqual(charts['disability-bar']['rows'], [
            ['Visual Disability', '2', '66.7%'],
            ['Deaf or Hard of Hearing', '1', '33.3%'],
            ['Classification not recorded', '1', '33.3%']])
        self.assertEqual(charts['program-completion']['rows'], [
            ['Synthetic Community Supplies', '0', '2', '0.0%'],
            ['Synthetic Health Support', '1', '2', '50.0%'],
            ['Synthetic School Assistance', '1', '2', '50.0%']])

    def test_year_to_date_membership_has_independent_boundaries(self):
        Member.objects.filter(pk=self.members[0].pk).update(joined_at=datetime(2025, 12, 31, 23, 59, tzinfo=ZONE))
        Member.objects.filter(pk=self.members[1].pk).update(joined_at=datetime(2026, 1, 1, tzinfo=ZONE))
        Member.objects.filter(pk=self.members[2].pk).update(joined_at=NOW + timedelta(seconds=1))
        data = self.projection(start='2020-01-01', end='2020-01-31')
        self.assertEqual(data['members']['new_year'], 2)  # January join and since-archived October join.
        self.assertEqual(data['members']['new'], 0)

    def test_program_filter_scopes_program_sources_and_preserves_association_sources(self):
        form = ActivityRangeForm({'period': 'six_months', 'program': self.programs[0].pk}, today=NOW.date(), user=self.admin)
        self.assertTrue(form.is_valid(), form.errors)
        with connection.execute_wrapper(only_reads):
            data = services.overview(self.admin, form.cleaned_data, now=NOW)
        self.assertEqual(data['applications']['total'], 2)
        self.assertEqual(data['applications']['completed'], 1)
        self.assertEqual(data['releases']['total'], 1)
        self.assertEqual(data['releases']['mix'], [('Support', 1)])
        self.assertEqual(data['eligibility']['total'], 2)
        self.assertEqual(data['programs']['total'], 1)
        self.assertEqual(data['capacity']['total'], 0)  # Selected program has not closed.
        self.assertEqual(data['members']['total'], 3)
        self.assertEqual((data['events']['total'], data['desk']['total']), (2, 5))
        denied = ActivityRangeForm({'period': 'six_months', 'program': self.programs[0].pk}, today=NOW.date(), user=self.limited)
        self.assertFalse(denied.is_valid())
        with self.assertRaises(PermissionDenied), connection.execute_wrapper(only_reads):
            services.overview(self.limited, form.cleaned_data, now=NOW)

    def test_timezone_boundaries_and_date_only_delivery(self):
        lower = datetime(2026, 10, 29, tzinfo=ZONE)
        for app, submitted in zip(self.applications, [lower-timedelta(microseconds=1), lower,
                lower+timedelta(days=1)-timedelta(microseconds=1), lower+timedelta(days=1), NOW, NOW]):
            ProgramApplication.objects.filter(pk=app.pk).update(submitted_at=submitted)
        data = self.projection(start='2026-10-29', end='2026-10-29')
        self.assertEqual(data['applications']['total'], 4)
        self.assertEqual(data['releases']['total'], 2)
        self.assertEqual(data['events']['total'], 2)

    def test_permissions_guard_source_queries_and_direct_route(self):
        with connection.execute_wrapper(only_reads), CaptureQueriesContext(connection) as queries:
            data = services.overview(self.limited, values(), now=NOW)
        self.assertTrue(all(metric['state'] == 'restricted' for metric in data['metrics']))
        self.assertFalse(any('members_member' in query['sql'] or 'programs_program' in query['sql'] for query in queries))
        for user in (AnonymousUser(), get_user_model()(is_active=True, is_staff=False)):
            with self.assertRaises(PermissionDenied):
                services.overview(user, values())
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 302)
        self.client.force_login(self.limited)
        response = self.client.get(reverse('core:dashboard'))
        self.assertContains(response, 'Not permitted')
        self.assertNotContains(response, 'Visual Disability')
        self.assertEqual(self.client.post(reverse('core:dashboard')).status_code, 405)

    def test_application_permission_does_not_disclose_eligibility(self):
        grant(self.limited, 'programs.view_program', 'programs.view_programapplication')
        user = get_user_model().objects.get(pk=self.limited.pk)
        data = services.overview(user, values(), now=NOW)
        self.assertEqual(data['applications']['total'], 6)
        self.assertEqual(data['eligibility']['state'], 'restricted')
        self.assertEqual(data['releases']['state'], 'restricted')

    def test_module_permission_without_dashboard_gate_is_denied(self):
        viewer = get_user_model().objects.create_user('module_without_dashboard', is_staff=True)
        grant(viewer, 'members.view_member')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 403)

    def test_long_classifications_are_escaped_without_truncation(self):
        label = 'Synthetic long recorded classification ' * 2 + '<script>private()</script>'
        kind = DisabilityType.objects.create(name=label)
        self.members[2].disability_types.add(kind)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:dashboard'))
        from django.utils.html import escape
        self.assertContains(response, escape(label))
        self.assertNotContains(response, '<script>private()</script>')

    def test_unavailable_failed_and_disabled_do_not_become_zero(self):
        for code, state in ((1146, 'unavailable'), (2006, 'failed')):
            with patch('analytics.services.membership', side_effect=OperationalError(code, 'secret SQL')):
                data = self.projection()
            self.assertEqual(data['members']['state'], state)
            self.assertNotEqual(data['metrics'][0]['value'], '0')
        with override_settings(REFERRAL_ENABLED=False):
            data = self.projection()
            self.assertEqual(data['desk']['state'], 'unavailable')

    def test_invalid_filter_does_not_query_analytics(self):
        self.client.force_login(self.admin)
        with patch('analytics.services.overview') as load:
            response = self.client.get(reverse('core:dashboard'), {'period': 'custom', 'start': 'bad'})
        self.assertEqual(response.status_code, 400)
        load.assert_not_called()

    def test_active_programs_use_existing_availability_rule(self):
        with patch('django.utils.timezone.now', return_value=NOW):
            expected = sum(program.registration_available for program in Program.objects.all())
        self.assertEqual(self.projection()['programs']['active'], expected)
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            self.assertEqual(self.projection()['programs']['active'], Program.objects.accepting_applications(at=NOW).count())

    def test_render_privacy_tables_and_capture_synthetic_evidence(self):
        request = RequestFactory().get('/dashboard/')
        request.user, request.session = self.admin, {}
        request.resolver_match = resolve('/dashboard/')
        form = ActivityRangeForm({'period': 'six_months'}, today=NOW.date(), user=self.admin)
        self.assertTrue(form.is_valid())
        output = Path(__file__).resolve().parents[1] / '.local/dashboard-charts-20261029'
        output.mkdir(parents=True, exist_ok=True)
        with connection.execute_wrapper(only_reads), CaptureQueriesContext(connection) as queries:
            start = perf_counter()
            data = self.projection()
            html = render_to_string('admin_portal/dashboard.html', {'overview': data, 'form': form}, request=request)
            elapsed = (perf_counter()-start)*1000
        self.assertLessEqual(len(queries), 27)  # Includes permission-scoped review badges.
        print(f'Dashboard fixture: {len(queries)} SELECT queries; aggregate + render {elapsed:.1f} ms', flush=True)
        for private in ['Private fixture name', 'PRIVATE DESK NAME', 'private@example.invalid', 'PRIVATE SUBJECT',
                        'PRIVATE MEDICAL TEXT', 'SYNTH-DASH-', 'SYNTH-APPLICATION-', '2016-10-29', '1986-10-30']:
            self.assertNotIn(private, html)
        self.assertEqual(html.count('data-chart-kind='), 12)
        self.assertEqual(html.count('class="overview-data-table"'), 12)
        main = html.split('<main', 1)[1].split('</main>', 1)[0]
        for removed in ['Membership reviews', 'Photo Verification</h2>', 'Manage accounts', 'Manage public information',
                        'workspace-priority', 'workspace-aside', 'workspace-sections',
                        'More metrics', 'Additional metrics', 'overview-definitions']:
            self.assertNotIn(removed, main)
        self.assertIn('Member Directory', html)
        self.assertIn('Membership reviews', html)
        output.joinpath('after.html').write_text(html, encoding='utf-8')
        for name, start, end in [('empty', '2020-01-01', '2020-01-31'), ('filtered', '2026-10-29', '2026-10-29')]:
            form = ActivityRangeForm({'period': 'custom', 'start': start, 'end': end}, today=NOW.date())
            self.assertTrue(form.is_valid())
            html = render_to_string('admin_portal/dashboard.html', {'overview': self.projection(start=start, end=end),
                'form': form, 'filtered': True}, request=request)
            output.joinpath(name + '.html').write_text(html, encoding='utf-8')
        import json
        output.joinpath('expected.json').write_text(json.dumps(data, default=str), encoding='utf-8')
        before = output / 'before-template.html'
        if before.exists():
            output.joinpath('before.html').write_text(engines['django'].from_string(before.read_text(encoding='utf-8')).render({}, request), encoding='utf-8')

    def test_twelve_chart_types_and_cumulative_membership(self):
        data = self.projection()
        charts = {item['kind']: item for item in data['visualizations']}
        self.assertEqual(set(charts), {'member-donut', 'column', 'line', 'rings', 'donut', 'stacked', 'area', 'scatter', 'histogram', 'heatmap', 'proportional', 'progress'})
        self.assertEqual(charts['area']['payload']['series'][0]['values'], [1, 2, 2, 2, 2, 4])
        self.assertEqual(charts['area']['total'], 4)
        self.assertEqual(charts['line']['payload']['series'][0]['values'], [1, 1, 0, 0, 1, 3])
        self.assertEqual(charts['column']['payload']['series'][0]['values'], [0, 0, 0, 0, 0, 2])

    def test_pie_donut_partition_and_percent_rounding(self):
        data = self.projection()
        for item in data['visualizations']:
            if item['kind'] in ('pie', 'donut', 'rings'):
                self.assertEqual(sum(item['payload']['series'][0]['values']), item['total'])
                self.assertEqual(sum(round(float(row[2][:-1]) * 10) for row in item['rows']), 1000)
        item = simple('test', 'Test', 'pie', {'state': 'ready'}, '', '', '', [('A', 1), ('B', 1), ('C', 1)])
        self.assertEqual([row[2] for row in item['rows']], ['33.4%', '33.3%', '33.3%'])

    def test_stacks_include_all_current_eligibility_outcomes_without_overlapping_stages(self):
        for app, code in zip(self.applications[3:], ['pending', 'review', 'ineligible']):
            EligibilityStatus.objects.get_or_create(code=code, defaults={'label': code})
            AssistanceCase.objects.create(application=app, eligibility_id=code, eligibility_label=code,
                reviewed_at=NOW, member_version=0, program_version=0)
        data = self.projection()['eligibility']
        self.assertEqual(sum(sum(row['counts']) for row in data['rows']), 6)
        totals = [sum(row['counts'][i] for row in data['rows']) for i in range(6)]
        self.assertEqual(totals, [1, 3, 1, 1, 0, 0])
        self.assertNotIn('Selected', data['labels'])

    def test_scatter_uses_closed_cohort_and_each_full_application_window(self):
        data = self.projection(start='2026-10-28', end='2026-10-28')
        self.assertEqual(data['applications']['total'], 0)
        self.assertEqual(data['capacity']['total'], 2)
        self.assertEqual(sorted((row['slots'], row['submissions']) for row in data['capacity']['rows']), [(10, 2), (20, 2)])
        closed = self.programs[1]
        ProgramApplication.objects.filter(pk=self.applications[1].pk).update(submitted_at=closed.registration_opens_at)
        ProgramApplication.objects.filter(pk=self.applications[4].pk).update(submitted_at=closed.registration_closes_at)
        data = self.projection()['capacity']
        self.assertEqual(next(row['submissions'] for row in data['rows'] if row['slots'] == 10), 1)
        Program.objects.filter(pk=self.programs[2].pk).update(slots=None)
        data = self.projection()['capacity']
        self.assertEqual((data['total'], data['excluded']), (1, 1))

    def test_histogram_completed_age_equal_bins_and_invalid_dates(self):
        data = self.projection()['ages']
        self.assertEqual(data['as_of'], NOW.date())
        self.assertEqual(dict(data['rows']), {'0–9': 0, '10–19': 1, '20–29': 0, '30–39': 1,
                                            '40–49': 0, '50–59': 0, '60–69': 0, '70–79': 1})
        self.assertEqual((data['total'], data['missing'], data['invalid']), (3, 0, 0))
        Member.objects.filter(pk=self.members[2].pk).update(birthdate=NOW.date()+timedelta(days=1))
        data = self.projection()['ages']
        self.assertEqual((data['total'], data['invalid']), (2, 1))

    def test_histogram_birthday_boundaries_leap_day_and_local_date(self):
        Member.objects.exclude(pk=self.members[0].pk).update(archived_at=NOW, is_active=False)
        member = Member.objects.filter(pk=self.members[0].pk)
        for birthdate, instant, expected in [
            ('2016-10-29', NOW, '10–19'),
            ('2016-10-30', NOW, '0–9'),
            ('2016-11-01', NOW, '0–9'),
            ('2016-09-30', NOW, '10–19'),
            ('2004-02-29', datetime(2034, 2, 28, 12, tzinfo=ZONE), '20–29'),
            ('2004-02-29', datetime(2034, 3, 1, 12, tzinfo=ZONE), '30–39'),
            ('2004-02-29', datetime(2024, 2, 29, 12, tzinfo=ZONE), '20–29'),
            ('1926-10-29', NOW, '100–109'),
            ('2016-10-30', datetime(2026, 10, 29, 16, tzinfo=ZoneInfo('UTC')), '10–19'),
        ]:
            with self.subTest(birthdate=birthdate, instant=instant):
                member.update(birthdate=birthdate)
                with connection.execute_wrapper(only_reads):
                    data = services.ages(instant)
                self.assertEqual([(label, count) for label, count in data['rows'] if count], [(expected, 1)])

    def test_histogram_empty_current_members(self):
        Member.objects.update(archived_at=NOW, is_active=False)
        data = services.ages(NOW)
        self.assertEqual((data['state'], data['rows'], data['total']), ('ready', [], 0))

    def test_heatmap_uses_local_start_day_once_not_duration_or_reference(self):
        first, second = Event.objects.all()
        # UTC Sunday afternoon is Monday in Manila; a multiday event is counted once.
        Event.objects.filter(pk=first.pk).update(starts_at=datetime(2026, 10, 4, 16, tzinfo=ZoneInfo('UTC')),
                                               ends_at=NOW+timedelta(days=1))
        Event.objects.filter(pk=second.pk).update(starts_at=datetime(2026, 10, 4, 15, 59, tzinfo=ZoneInfo('UTC')),
                                                ends_at=NOW+timedelta(days=1))
        data = self.projection()['events']
        self.assertEqual(data['matrix'][-1], [1, 0, 0, 0, 0, 0, 1])
        self.assertEqual(data['total'], 2)
        self.assertTrue(all(sum(row) == 0 for row in data['matrix'][:-1]))

    def test_payloads_are_aggregate_only_and_tables_match_every_chart(self):
        data = self.projection()
        for item in data['visualizations']:
            if item['kind'] == 'heatmap':
                self.assertEqual(sum(sum(int(cell.replace(',', '')) for cell in row[1:]) for row in item['rows']), item['total'])
            elif item['kind'] == 'scatter':
                self.assertEqual([(p['x'], p['y']) for p in item['payload']['points']],
                                 [(int(row[1]), int(row[2])) for row in item['rows']])
            elif item['kind'] == 'stacked':
                for i, row in enumerate(item['rows']):
                    self.assertEqual([series['values'][i] for series in item['payload']['series']], [int(cell) for cell in row[1:-1]])
            else:
                self.assertEqual(item['payload']['series'][0]['values'], [int(row[1].replace(',', '')) for row in item['rows']])
        grant(self.limited, 'programs.view_program')
        user = get_user_model().objects.get(pk=self.limited.pk)
        projection = services.overview(user, values(), now=NOW)
        self.assertEqual(projection['capacity']['state'], 'restricted')
        for item in projection['visualizations']:
            if item['state'] != 'ready':
                self.assertNotIn('payload', item)
                self.assertEqual(item['summary'], '')
