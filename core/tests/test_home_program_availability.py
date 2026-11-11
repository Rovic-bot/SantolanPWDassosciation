"""Homepage availability agrees with the existing policy; all data is synthetic."""
import re
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programs.models import Program


class HomeProgramAvailabilityTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 11, 4, tzinfo=datetime_timezone.utc)
        clock = patch('django.utils.timezone.now', return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def program(self, **changes):
        return Program.objects.create(**{
            'name': 'Synthetic assistance program', 'description': 'Synthetic public guidance.',
            'assistance_type': 'Synthetic support', 'status': 'published',
            'published_at': self.now - timedelta(days=2),
            'registration_opens_at': self.now - timedelta(days=1),
            'registration_closes_at': self.now + timedelta(days=1),
            'policy_authorized_at': self.now - timedelta(days=2),
            'photo_instructions': 'Synthetic approved photo instructions.',
            'selection_method': 'Synthetic approved selection method.',
            **changes,
        })

    def assert_home(self, available):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['has_open_programs'], available)
        self.assertContains(response, 'Applications are open' if available
            else 'No programs are accepting applications')
        self.assertNotContains(response, 'No programs listed yet')
        # The live availability message itself links to the program catalog.
        from html.parser import HTMLParser

        class LinkText(HTMLParser):
            active = False
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.active = dict(attrs).get('href') == reverse('core:programs')
            def handle_endtag(self, tag):
                if tag == 'a':
                    self.active = False
            def handle_data(self, data):
                if self.active:
                    linked_text.append(data)

        linked_text = []
        LinkText().feed(response.content.decode())
        self.assertIn('Applications are open' if available else 'No programs are accepting applications', linked_text)
        return response

    def assert_policy_agrees(self, program, available):
        program.refresh_from_db()
        self.assertEqual(program.registration_available, available)
        self.assertEqual(Program.objects.accepting_applications().filter(pk=program.pk).exists(), available)
        self.assert_home(available)

    def test_current_authorized_program_is_open(self):
        self.assert_policy_agrees(self.program(), True)

    def test_upcoming_program_is_not_open(self):
        self.assert_policy_agrees(self.program(registration_opens_at=self.now + timedelta(hours=1)), False)

    def test_closed_program_is_not_open(self):
        self.assert_policy_agrees(self.program(registration_closes_at=self.now - timedelta(hours=1)), False)

    def test_cancelled_program_is_not_open(self):
        self.assert_policy_agrees(self.program(status='cancelled'), False)

    def test_missing_policy_authorization_is_not_open(self):
        self.assert_policy_agrees(self.program(policy_authorized_at=None), False)

    def test_blank_required_instructions_match_python_strip(self):
        program = self.program()
        # Include every whitespace codepoint recognized by the running Python,
        # so the native MySQL predicate cannot silently disagree with strip().
        whitespace = [chr(code) for code in range(0x110000) if chr(code).isspace()]
        for field in ('photo_instructions', 'selection_method'):
            for value in ['', ' \t\r\n', *whitespace]:
                with self.subTest(field=field, value=repr(value)):
                    Program.objects.filter(pk=program.pk).update(**{field: value})
                    self.assert_policy_agrees(program, False)
            Program.objects.filter(pk=program.pk).update(**{field: 'Synthetic approved instructions.'})

    def test_padded_nonblank_instructions_remain_open(self):
        self.assert_policy_agrees(self.program(photo_instructions='\t\n Synthetic photo \u00a0',
            selection_method='\u2003Synthetic selection\r\n'), True)

    def test_opening_and_closing_boundaries(self):
        program = self.program()
        microsecond = timedelta(microseconds=1)
        cases = (
            (program.registration_opens_at - microsecond, False),
            (program.registration_opens_at, True),
            (program.registration_opens_at + microsecond, True),
            (program.registration_closes_at - microsecond, True),
            (program.registration_closes_at, False),
            (program.registration_closes_at + microsecond, False),
        )
        for moment, available in cases:
            with self.subTest(moment=moment), patch('django.utils.timezone.now', return_value=moment):
                self.assert_policy_agrees(program, available)

    def test_unpublished_and_future_publication_programs_are_not_open(self):
        program = self.program()
        for changes in ({'status': 'draft'}, {'status': 'archived'},
                        {'status': 'draft', 'published_at': None},
                        {'status': 'published', 'published_at': self.now + timedelta(microseconds=1)}):
            with self.subTest(changes=changes):
                Program.objects.filter(pk=program.pk).update(**changes)
                self.assert_policy_agrees(program, False)
        Program.objects.filter(pk=program.pk).update(status='published', published_at=self.now)
        self.assert_policy_agrees(program, True)

    def test_no_programs_has_accurate_message_and_browse_link(self):
        self.assert_home(False)

    def test_open_program_is_found_beyond_first_three_public_rows(self):
        open_program = self.program()
        Program.objects.filter(pk=open_program.pk).update(created_at=self.now - timedelta(days=2))
        for changes in ({'status': 'cancelled'}, {'policy_authorized_at': None},
                        {'photo_instructions': '\t'}, {'selection_method': ''},
                        {'registration_opens_at': self.now + timedelta(hours=1)}):
            self.program(**changes)
        self.assert_home(True)
        Program.objects.filter(pk=open_program.pk).update(status='cancelled')
        self.assert_home(False)

    def test_nonopen_public_programs_remain_browsable(self):
        upcoming = self.program(name='Synthetic upcoming', registration_opens_at=self.now + timedelta(hours=1))
        cancelled = self.program(name='Synthetic cancelled', status='cancelled')
        closed = self.program(name='Synthetic closed', registration_closes_at=self.now - timedelta(hours=1))
        current = self.client.get(reverse('core:programs'))
        past = self.client.get(reverse('core:programs'), {'period': 'past'})
        self.assertContains(current, upcoming.name)
        self.assertContains(current, cancelled.name)
        self.assertContains(past, closed.name)
        self.assertNotContains(current, 'Applications open')
        for program in (upcoming, cancelled, closed):
            detail = self.client.get(reverse('programs:detail', args=[program.pk]))
            self.assertContains(detail, program.name)
            self.assertNotContains(detail, 'Apply for this program')
        self.assert_home(False)

    def test_home_uses_one_existence_query_without_loading_program_rows(self):
        for _ in range(12):
            self.program(status='cancelled')
        self.program()
        with CaptureQueriesContext(connection) as captured:
            self.assert_home(True)
        # Publication gates may inspect programs inside an announcement subquery.
        # Count the queries that actually fetch FROM the program table as their main operation.
        queries = [item['sql'] for item in captured
                   if (source := re.search(r'\bFROM\s+`([^`]+)`', item['sql'])) and source[1] == 'programs_program']
        self.assertEqual(len(queries), 1)
        self.assertIn('SELECT 1 AS', queries[0])
        self.assertIn('LIMIT 1', queries[0])
        self.assertNotIn('`programs_program`.`description`', queries[0])
