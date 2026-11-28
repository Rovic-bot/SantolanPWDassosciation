"""Report regressions using synthetic records and current optional draft fields."""
from datetime import datetime, timezone as datetime_timezone
from io import BytesIO, StringIO
import csv

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import load_workbook

from programs.models import Program
from reports.services import report_row


class DraftReportFormattingTests(SimpleTestCase):
    def test_draft_without_schedule_has_a_readable_report_row(self):
        program = Program(name='Synthetic unscheduled draft',
                          created_at=datetime(2026, 11, 26, tzinfo=datetime_timezone.utc))
        row = report_row('programs', program)
        self.assertEqual(row[3], 'Not specified')
        self.assertEqual(row[5], 'Draft')

    def test_scheduled_program_keeps_manila_date_and_time(self):
        instant = datetime(2026, 11, 26, 18, 30, tzinfo=datetime_timezone.utc)
        row = report_row('programs', Program(created_at=instant, registration_closes_at=instant))
        self.assertEqual(row[3], '2026-11-27 02:30')


class DraftReportRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('synthetic_report_auditor')
        self.client.force_login(self.user)
        Program.objects.create(name='Synthetic unscheduled draft', created_by=self.user)

    def test_program_report_screen_and_all_exports_accept_unscheduled_drafts(self):
        for output in ('', 'csv', 'xlsx', 'pdf'):
            with self.subTest(format=output or 'screen'):
                response = self.client.get(reverse('reports:programs'), {'format': output})
                self.assertEqual(response.status_code, 200)
                self.assertIn('no-store', response['Cache-Control'])
                if output == 'csv':
                    rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
                    self.assertEqual(rows[1][3], 'Not specified')
                elif output == 'xlsx':
                    workbook = load_workbook(BytesIO(response.content), read_only=True)
                    self.assertEqual(workbook.active['D2'].value, 'Not specified')
                    workbook.close()
                elif output == 'pdf':
                    self.assertTrue(response.content.startswith(b'%PDF-'))
                else:
                    self.assertContains(response, 'Not specified')
