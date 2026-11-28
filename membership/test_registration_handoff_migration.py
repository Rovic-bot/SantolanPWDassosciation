"""Execute only 0007 against model-derived synthetic schema/history."""
import hashlib
from pathlib import Path

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from scripts.durable_test_runner import require_disposable
from scripts.registration_handoff_test_runner import HANDOFF_MIGRATION, HANDOFF_SHA256
from .test_registration_handoff import HandoffHelpers
from .models import MembershipApplication


class RegistrationHandoffMigrationTests(TransactionTestCase):
    def test_forward_reverse_forward_preserves_pending_and_old_rows_and_refuses_linked_reverse(self):
        from scripts.migration_test_support import migration_database, historical_apps, pending_intake
        from membership.tests import profile
        from uuid import uuid4
        parent = ('membership', '0006_association_pending_intake')
        with migration_database([parent]) as database:
            apps = historical_apps(database, [parent])
            intake = pending_intake(database, apps)
            Intake = apps.get_model('membership', 'RegistrationIntake')
            original = Intake.objects.using(database.alias).values().get(pk=intake.pk)
            MigrationExecutor(database).migrate([HANDOFF_MIGRATION])
            self.assertEqual(Intake.objects.using(database.alias).values().get(pk=intake.pk), original)
            MigrationExecutor(database).migrate([parent])
            self.assertEqual(Intake.objects.using(database.alias).values().get(pk=intake.pk), original)
            MigrationExecutor(database).migrate([HANDOFF_MIGRATION])
            apps = historical_apps(database, [HANDOFF_MIGRATION])
            Application = apps.get_model('membership', 'MembershipApplication')
            application = Application.objects.using(database.alias).create(**profile(), submission_key=uuid4())
            Intake.objects.using(database.alias).filter(pk=intake.pk).update(
                membership_application_id=application.pk, state='membership_review')
            def schema_snapshot():
                with database.cursor() as cursor:
                    if database.vendor == 'mysql':
                        cursor.execute('SHOW CREATE TABLE membership_registrationintake')
                        return cursor.fetchone()[1]
                    return (database.introspection.get_table_description(cursor, 'membership_registrationintake'),
                            database.introspection.get_constraints(cursor, 'membership_registrationintake'))
            before = schema_snapshot()
            with self.assertRaisesMessage(RuntimeError, 'handoff links exist'):
                MigrationExecutor(database).migrate([parent])
            self.assertEqual(schema_snapshot(), before)
            self.assertIn(HANDOFF_MIGRATION, MigrationRecorder(database).applied_migrations())
            self.assertEqual(Intake.objects.using(database.alias).get(pk=intake.pk).membership_application_id, application.pk)
