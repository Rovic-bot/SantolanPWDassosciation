"""Closing-soon notes use the final registration hour after readiness checks."""
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Program
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class PublicProgramDeadlineTests(TestCase):
    def setUp(self):
        self.at = timezone.now().replace(microsecond=0)
        clock = patch('programs.public_catalog.timezone.now', return_value=self.at)
        clock.start()
        self.addCleanup(clock.stop)
        self.program = create_program(ewaf_applicable=True, name='Closing notice boundary')
        self.detail = reverse('programs:detail', args=[self.program.pk])

    def responses(self):
        return (self.client.get(self.detail),
                self.client.get(reverse('core:programs'), {'q': self.program.name}))

    def presented_program(self, response):
        return response.context['program'] if 'program' in response.context else response.context['page_obj'][0]

    def test_final_hour_is_inclusive_and_the_deadline_is_exclusive_on_both_pages(self):
        for remaining, visible, exists in (
            (timedelta(hours=1, microseconds=1), False, True),
            (timedelta(hours=1), True, True),
            (timedelta(minutes=15), True, True),
            (timedelta(microseconds=1), True, True),
            (timedelta(), False, False),
            (-timedelta(seconds=1), False, False),
        ):
            Program.objects.filter(pk=self.program.pk).update(registration_closes_at=self.at + remaining)
            for response in self.responses():
                with self.subTest(remaining=remaining, detail='program' in response.context):
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(self.presented_program(response).registration_closing_soon, visible)
                    if exists:
                        self.assertContains(response, 'data-public-deadline')
                        attrs = response.content.decode().split('<p class="program-closing-note"', 1)[1].split('>', 1)[0]
                        self.assertEqual(' hidden' not in attrs, visible)
                    else:
                        self.assertNotContains(response, 'data-public-deadline')

    def test_program_end_date_does_not_change_the_registration_notice(self):
        closes = self.at + timedelta(minutes=30)
        Program.objects.filter(pk=self.program.pk).update(registration_closes_at=closes,
            starts_at=self.at + timedelta(days=7), ends_at=self.at + timedelta(days=8))
        for response in self.responses():
            self.assertTrue(self.presented_program(response).registration_closing_soon)
            self.assertContains(response, 'Closing soon.')
            self.assertContains(response, 'Registration ends')
            self.assertContains(response, '(PHT).')

    def test_upcoming_cancelled_and_unavailable_programs_do_not_show_a_notice(self):
        scenarios = (
            {'status': 'published', 'registration_opens_at': self.at + timedelta(minutes=15), 'policy_authorized_at': self.at},
            {'status': 'cancelled', 'registration_opens_at': self.at - timedelta(days=1), 'policy_authorized_at': self.at},
            {'status': 'published', 'registration_opens_at': self.at - timedelta(days=1), 'policy_authorized_at': None},
        )
        for changes in scenarios:
            Program.objects.filter(pk=self.program.pk).update(registration_closes_at=self.at + timedelta(minutes=30), **changes)
            for response in self.responses():
                self.assertFalse(self.presented_program(response).registration_closing_soon)
                self.assertNotContains(response, 'data-public-deadline')

    @override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
    def test_final_hour_cannot_bypass_ewaf_application_readiness(self):
        Program.objects.filter(pk=self.program.pk).update(registration_closes_at=self.at + timedelta(minutes=10))
        for response in self.responses():
            self.assertEqual(self.presented_program(response).public_application_status, 'unavailable')
            self.assertNotContains(response, 'data-public-deadline')

    def test_deadline_is_displayed_in_philippine_time_across_midnight(self):
        at = datetime(2026, 11, 10, 15, 30, tzinfo=datetime_timezone.utc)
        with patch('programs.public_catalog.timezone.now', return_value=at), timezone.override('Asia/Manila'):
            Program.objects.filter(pk=self.program.pk).update(published_at=at - timedelta(days=1),
                policy_authorized_at=at - timedelta(days=1), registration_opens_at=at - timedelta(days=1),
                registration_closes_at=at + timedelta(minutes=40))
            for response in self.responses():
                self.assertContains(response, 'Nov 11, 12:10 AM')
                self.assertContains(response, '2026-11-11T00:10:00+08:00')
