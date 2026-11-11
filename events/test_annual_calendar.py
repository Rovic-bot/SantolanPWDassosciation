from dataclasses import asdict
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .annual_calendar import calendar_id, publish_annual_calendar
from .models import AnnualObservance, AnnualObservanceRevision, AnnualObservanceLog, Event
from .observances import REFERENCE_CATALOGUE
from .services import change_observance_publication, save_observance, public_observance_calendar
from .test_observance_workflow import draft_data


class AnnualCalendarTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('calendar_admin')

    def install(self):
        return publish_annual_calendar(user=self.admin, notes='Owner-approved recurring calendar.')

    def test_installs_all_months_published_with_history_and_no_scheduled_events(self):
        created, retained = self.install()
        self.assertEqual((len(created), len(retained)), (12, 0))
        self.assertEqual(AnnualObservance.objects.public().count(), 12)
        self.assertEqual(AnnualObservanceRevision.objects.count(), 24)
        self.assertEqual(AnnualObservanceLog.objects.count(), 24)
        self.assertFalse(Event.objects.exists())
        for reference in REFERENCE_CATALOGUE:
            item = AnnualObservance.objects.get(pk=calendar_id(reference.month))
            self.assertEqual(item.title, reference.title)
            self.assertEqual(item.recurrence_rule, reference.recurrence_rule)
            self.assertContains(self.client.get(reverse('core:events')), reference.title)
        may = AnnualObservance.objects.get(month=5)
        self.assertEqual(may.recurrence_kind, 'third_thursday')
        self.assertIsNone(may.day_start)

    def test_recurring_public_calendar_survives_year_change_without_new_rows(self):
        self.install()
        with patch('events.observance_models.timezone.now', return_value=datetime(2030, 1, 1, tzinfo=dt_timezone.utc)):
            self.assertTrue(all(len(m['observances']) == 1 for m in public_observance_calendar()))
        self.assertEqual(AnnualObservance.objects.count(), 12)

    def test_rerun_preserves_admin_edits_and_withdrawals(self):
        self.install()
        item = AnnualObservance.objects.get(month=5)
        item = change_observance_publication(item.pk, user=self.admin, version=item.version,
            action='draft', notes='Edit May details.')
        item = save_observance(user=self.admin, pk=item.pk,
            data=draft_data(**(asdict(REFERENCE_CATALOGUE[4]) | {
                'version': item.version, 'title': 'Edited May observance'})))
        original_version = item.version
        created, retained = self.install()
        self.assertEqual((len(created), len(retained)), (0, 12))
        item.refresh_from_db()
        self.assertEqual((item.title, item.status, item.version), ('Edited May observance', 'draft', original_version))
        self.assertNotContains(self.client.get(reverse('core:events')), item.title)
        item = change_observance_publication(item.pk, user=self.admin, version=item.version,
            action='published', notes='Publish reviewed May edit.')
        self.assertContains(self.client.get(reverse('core:events')), item.title)

    def test_failure_rolls_back_entire_calendar(self):
        with patch('events.services._record_observance', side_effect=RuntimeError('Audit failure')):
            with self.assertRaises(RuntimeError):
                self.install()
        self.assertFalse(AnnualObservance.objects.exists())
        self.assertFalse(AnnualObservanceRevision.objects.exists())

    def test_duplicate_existing_title_is_preserved_without_partial_install(self):
        existing = save_observance(user=self.admin, data=draft_data(**asdict(REFERENCE_CATALOGUE[4])))
        with self.assertRaises(ValidationError):
            self.install()
        self.assertEqual(list(AnnualObservance.objects.values_list('pk', flat=True)), [existing.pk])

    def test_setup_requires_publication_permission_and_gets_do_not_create_rows(self):
        staff = get_user_model().objects.create_user('calendar_staff', is_staff=True)
        with self.assertRaises(PermissionDenied):
            publish_annual_calendar(user=staff, notes='Unauthorized')
        self.client.get(reverse('core:events'))
        self.assertFalse(AnnualObservance.objects.exists())


class AnnualCalendarMigrationTests(TransactionTestCase):
    def test_recurrence_migration_preserves_existing_cards_and_permits_may(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('events', '0007_event_participation_details')])
            user = get_user_model().objects.create_superuser('migration_calendar_admin')
            item = save_observance(user=user, data=draft_data())
            before = AnnualObservance.objects.values().get(pk=item.pk)
            MigrationExecutor(connection).migrate([('events', '0008_annual_calendar_third_thursday')])
            self.assertEqual(AnnualObservance.objects.values().get(pk=item.pk), before)
            may = save_observance(user=user, data=draft_data(**asdict(REFERENCE_CATALOGUE[4])))
            self.assertEqual(may.recurrence_rule, 'Third Thursday of May')
        finally:
            MigrationExecutor(connection).migrate(leaves)
