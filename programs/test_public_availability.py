"""G07-B public lifecycle tests. All fixtures are synthetic."""
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Program
from .services import require_open, verify_member


class PublicProgramAvailabilityTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 11, 4, tzinfo=datetime_timezone.utc)
        clock = patch('django.utils.timezone.now', return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def program(self, **changes):
        return Program.objects.create(**{
            'name': 'Synthetic lifecycle program', 'description': 'Synthetic public guidance.',
            'assistance_type': 'Synthetic support', 'status': 'published',
            'published_at': self.now - timedelta(days=2),
            'registration_opens_at': self.now - timedelta(days=1),
            'registration_closes_at': self.now + timedelta(days=1),
            'policy_authorized_at': self.now - timedelta(days=2),
            'photo_instructions': 'Synthetic photo guidance.',
            'selection_method': 'Synthetic selection guidance.', **changes,
        })

    def listing(self, period='all', **params):
        response = self.client.get(reverse('programs:list'), {'period': period, **params})
        self.assertEqual(response.status_code, 200)
        return response

    def ids(self, response):
        return {program.pk for program in response.context['page_obj']}

    def assert_status(self, program, status, label):
        response = self.client.get(reverse('programs:detail', args=[program.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['program'].public_application_status, status)
        self.assertContains(response, f'<span class="quiet-badge">{label}</span>', html=True)
        self.assertEqual('Apply for this program' in response.content.decode(), program.registration_available)
        self.assertEqual(status == 'open', program.registration_available)
        self.assertEqual(Program.objects.accepting_applications(at=self.now).filter(pk=program.pk).exists(), status == 'open')
        return response

    def test_authorized_open_program_and_application_entry(self):
        program = self.program()
        response = self.assert_status(program, 'open', 'Applications open')
        self.assertContains(response, reverse('programs:verify', args=[program.pk]))
        self.assertContains(response, 'Schedule &amp; capacity')
        self.assertNotContains(response, 'How review and selection work')
        self.assertEqual(self.ids(self.listing('available')), {program.pk})
        require_open(program)
        self.assertRedirects(self.client.get(reverse('programs:apply', args=[program.pk])),
            reverse('programs:verify', args=[program.pk]), fetch_redirect_response=False)

    def test_upcoming_has_scheduled_opening_without_closed_or_apply_label(self):
        program = self.program(registration_opens_at=self.now + timedelta(hours=1))
        detail = self.assert_status(program, 'upcoming', 'Upcoming application period')
        for response in (detail, self.listing('upcoming')):
            self.assertContains(response, 'Scheduled opening')
            self.assertContains(response, 'October 11, 2026, 1:00 PM')
            self.assertContains(response, 'Philippine time')
            self.assertContains(response, '<time datetime="2026-10-11T13:00:00+08:00">')
            self.assertNotContains(response, 'Applications closed')
            self.assertNotContains(response, 'Apply for this program')
        self.assertEqual(self.ids(self.listing('upcoming')), {program.pk})

    def test_ended_period_stays_browsable(self):
        program = self.program(registration_closes_at=self.now - timedelta(hours=1))
        self.assert_status(program, 'ended', 'Application period ended')
        self.assertEqual(self.ids(self.listing('past')), {program.pk})
        self.assertEqual(self.ids(self.listing()), {program.pk})
        self.assertFalse(self.ids(self.listing('available')))

    def test_cancelled_takes_precedence_over_dates_and_configuration(self):
        for changes in ({}, {'registration_opens_at': self.now + timedelta(hours=1)},
                        {'registration_closes_at': self.now - timedelta(hours=1)},
                        {'policy_authorized_at': None}):
            with self.subTest(changes=changes):
                program = self.program(status='cancelled', **changes)
                self.assert_status(program, 'cancelled', 'Cancelled program')
                self.assertIn(program.pk, self.ids(self.listing('unavailable')))
                self.assertNotIn(program.pk, self.ids(self.listing('upcoming')))
                self.assertNotIn(program.pk, self.ids(self.listing('available')))

    def test_missing_authorization_explained_without_internal_details(self):
        program = self.program(policy_authorized_at=None)
        detail = self.assert_status(program, 'unavailable', 'Applications unavailable')
        for response in (detail, self.listing('unavailable')):
            self.assertContains(response, 'required application arrangements are incomplete')
            self.assertContains(response, 'Association Help Desk')
            self.assertNotContains(response, 'policy_authorized_at')
        self.assertEqual(self.ids(self.listing('unavailable')), {program.pk})

    def test_missing_and_whitespace_only_instructions_match_authoritative_policy(self):
        program = self.program()
        whitespace = ''.join(chr(code) for code in range(0x3001) if chr(code).isspace())
        for field in ('photo_instructions', 'selection_method'):
            for value in ('', whitespace, '\t\r\n', '\u00a0\u2003\u3000', '\x1c\x1d\x1e\x1f'):
                with self.subTest(field=field, value=repr(value)):
                    setattr(program, field, value)
                    program.save(update_fields=[field])
                    self.assert_status(program, 'unavailable', 'Applications unavailable')
                    self.assertEqual(self.ids(self.listing('unavailable')), {program.pk})
                    self.assertFalse(self.ids(self.listing('available')))
            setattr(program, field, '  Synthetic meaningful guidance.\t')
            program.save(update_fields=[field])
        self.assert_status(program, 'open', 'Applications open')

    def test_incomplete_upcoming_and_ended_programs_keep_date_labels(self):
        upcoming = self.program(policy_authorized_at=None, registration_opens_at=self.now + timedelta(hours=1))
        ended = self.program(photo_instructions='', registration_closes_at=self.now)
        self.assert_status(upcoming, 'upcoming', 'Upcoming application period')
        self.assert_status(ended, 'ended', 'Application period ended')
        self.assertEqual(self.ids(self.listing('upcoming')), {upcoming.pk})
        self.assertEqual(self.ids(self.listing('past')), {ended.pk})

    def test_exact_opening_boundary(self):
        program = self.program()
        for offset, expected in ((1, 'upcoming'), (0, 'open'), (-1, 'open')):
            with self.subTest(microseconds=offset):
                program.registration_opens_at = self.now + timedelta(microseconds=offset)
                program.save(update_fields=['registration_opens_at'])
                label = 'Upcoming application period' if expected == 'upcoming' else 'Applications open'
                self.assert_status(program, expected, label)
                self.assertEqual(bool(self.ids(self.listing('available'))), expected == 'open')
                self.assertEqual(bool(self.ids(self.listing('upcoming'))), expected == 'upcoming')

    def test_exact_closing_boundary(self):
        program = self.program()
        for offset, expected in ((1, 'open'), (0, 'ended'), (-1, 'ended')):
            with self.subTest(microseconds=offset):
                program.registration_closes_at = self.now + timedelta(microseconds=offset)
                program.save(update_fields=['registration_closes_at'])
                label = 'Applications open' if expected == 'open' else 'Application period ended'
                self.assert_status(program, expected, label)
                self.assertEqual(bool(self.ids(self.listing('available'))), expected == 'open')
                self.assertEqual(bool(self.ids(self.listing('past'))), expected == 'ended')
                self.assertEqual(bool(self.ids(self.listing('current'))), expected == 'open')

    def test_private_and_future_publication_not_exposed_in_any_category_or_detail(self):
        hidden = [self.program(status='draft', published_at=None), self.program(status='archived'),
                  self.program(published_at=self.now + timedelta(microseconds=1)),
                  self.program(status='cancelled', published_at=self.now + timedelta(days=1))]
        for period in ('all', 'available', 'upcoming', 'past', 'unavailable', 'current'):
            self.assertFalse(self.ids(self.listing(period)))
        for program in hidden:
            self.assertEqual(self.client.get(reverse('programs:detail', args=[program.pk])).status_code, 404)
        visible = self.program(published_at=self.now)
        self.assert_status(visible, 'open', 'Applications open')

    def test_default_and_legacy_bookmarks_preserve_public_browsing(self):
        opened = self.program()
        upcoming = self.program(registration_opens_at=self.now + timedelta(hours=1))
        unavailable = self.program(policy_authorized_at=None)
        cancelled = self.program(status='cancelled')
        ended = self.program(registration_closes_at=self.now)
        ended_cancelled = self.program(status='cancelled', registration_closes_at=self.now)
        current = {opened.pk, upcoming.pk, unavailable.pk, cancelled.pk}
        past = {ended.pk, ended_cancelled.pk}
        default = self.client.get(reverse('core:programs'))
        self.assertEqual(default.context['period'], 'all')
        self.assertEqual(self.ids(default), current | past)
        self.assertEqual(self.ids(self.listing('current')), current)
        self.assertEqual(self.ids(self.listing('past')), past)
        self.assertEqual(self.ids(self.listing('unavailable')), {unavailable.pk, cancelled.pk, ended_cancelled.pk})

    def test_pagination_is_bounded_stable_and_preserves_filter(self):
        for index in range(12):
            self.program(name=f'Synthetic paginated program {index}')
        self.program(name='Synthetic excluded upcoming', registration_opens_at=self.now + timedelta(hours=1))
        first = self.listing('available')
        second = self.listing('available', page=2)
        self.assertEqual(len(self.ids(first)), 6)
        self.assertEqual(len(self.ids(second)), 6)
        self.assertFalse(self.ids(first) & self.ids(second))
        self.assertEqual(self.ids(first), self.ids(self.listing('available')))
        self.assertContains(first, '?period=available&amp;page=2')
        self.assertContains(second, '?period=available&amp;page=1')
        self.assertEqual(first.context['page_obj'].paginator.count, 12)

    def test_invalid_period_and_page_are_safe(self):
        program = self.program()
        response = self.listing('<unknown>', page='invalid')
        self.assertEqual(response.context['period'], 'all')
        self.assertEqual(self.ids(response), {program.pk})
        self.assertNotContains(response, '&lt;unknown&gt;')
        self.assertEqual(self.listing(page=999).context['page_obj'].number, 1)

    def test_empty_states_distinguish_empty_category_from_empty_catalog(self):
        self.assertContains(self.listing(), 'There are no published programs to browse yet.')
        self.program(registration_opens_at=self.now + timedelta(hours=1))
        for period in ('available', 'past', 'unavailable'):
            response = self.listing(period)
            self.assertContains(response, 'No programs match this category.')
            self.assertContains(response, 'Browse all programs')
            self.assertNotContains(response, 'There are no published programs')

    def test_accessible_filter_labels_and_application_dates(self):
        self.program()
        for period in ('all', 'available', 'upcoming', 'past', 'unavailable', 'current'):
            response = self.listing(period)
            self.assertContains(response, 'aria-label="Program period"')
            self.assertContains(response, f'href="?period={period}" aria-current="page"')
        response = self.listing()
        self.assertContains(response, 'Application period starts <time datetime=')
        self.assertContains(response, 'Application period ends <time datetime=')
        self.assertContains(response, 'aria-label="View Synthetic lifecycle program"')

    def test_list_uses_bounded_catalog_queries_and_one_limited_program_query(self):
        for index in range(12):
            self.program(name=f'Synthetic query check {index}')
        for period in ('all', 'available', 'current'):
            with CaptureQueriesContext(connection) as queries:
                response = self.listing(period)
            program_queries = [q['sql'] for q in queries if '`programs_program`' in q['sql']]
            # Categories, aggregate tab counts, paginator count, and six cards.
            self.assertEqual(len(program_queries), 4)
            self.assertIn('DISTINCT', program_queries[0])
            self.assertIn('COUNT(', program_queries[1])
            self.assertIn('LIMIT 6', program_queries[-1])
            self.assertEqual(len(response.context['page_obj']), 6)

    def test_list_and_detail_use_one_evaluation_instant_at_closing(self):
        program = self.program(registration_closes_at=self.now + timedelta(microseconds=1))
        for url, params in ((reverse('programs:list'), {'period': 'available'}),
                            (reverse('programs:detail', args=[program.pk]), {})):
            with patch('django.utils.timezone.now', side_effect=[self.now, self.now + timedelta(seconds=1)]) as clock:
                response = self.client.get(url, params)
            self.assertEqual(clock.call_count, 1)
            self.assertContains(response, '<span class="quiet-badge">Applications open</span>', html=True)

    def test_closed_states_cannot_bypass_existing_verification_guard(self):
        for changes in ({'registration_opens_at': self.now + timedelta(hours=1)},
                        {'registration_closes_at': self.now}, {'status': 'cancelled'},
                        {'policy_authorized_at': None}, {'photo_instructions': '\t'},
                        {'selection_method': '\u3000'}):
            with self.subTest(changes=changes):
                program = self.program(**changes)
                with self.assertRaisesMessage(ValidationError, 'Applications are currently closed'):
                    verify_member(program.pk, version=program.version, control_number='SYNTHETIC-ONLY',
                        full_name='Synthetic Applicant', birthdate='2000-01-01', contact_number='00000000000')
                self.assertRedirects(self.client.get(reverse('programs:apply', args=[program.pk])),
                    reverse('programs:verify', args=[program.pk]), fetch_redirect_response=False)
