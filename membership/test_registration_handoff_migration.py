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


class RegistrationHandoffMigrationTests(HandoffHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_handoff()

    def test_forward_reverse_forward_preserves_pending_and_old_rows_and_refuses_linked_reverse(self):
        require_disposable()
        call_command('makemigrations', check=True, dry_run=True, interactive=False, verbosity=1)
        path = Path(__file__).parent / 'migrations' / (HANDOFF_MIGRATION[1] + '.py')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), HANDOFF_SHA256)
        intake = self.make()
        original = dict(type(intake).objects.filter(pk=intake.pk).values().get())
        loader = MigrationLoader(None)
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        recorder.migration_qs.all().delete()
        # Model sync and synthetic history only. No older migration executes.
        for key in loader.disk_migrations:
            recorder.record_applied(*key)
        parent = ('membership', '0006_association_pending_intake')
        plan = MigrationExecutor(connection).migration_plan([parent])
        self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in plan], [(*HANDOFF_MIGRATION, True)])
        call_command('migrate', *parent, interactive=False, verbosity=1)
        self.assertEqual(original, dict(type(intake).objects.filter(pk=intake.pk).values().get()))
        call_command('migrate', *HANDOFF_MIGRATION, interactive=False, verbosity=1)
        self.assertEqual(original, dict(type(intake).objects.filter(pk=intake.pk).values().get()))
        application = self.prepare(intake)
        before = MembershipApplication.objects.filter(pk=application.pk).values().get()
        with connection.cursor() as cursor:
            cursor.execute('SHOW CREATE TABLE membership_registrationintake')
            table_before = cursor.fetchone()[1]
        with self.assertRaisesMessage(RuntimeError, 'handoff links exist'):
            call_command('migrate', *parent, interactive=False, verbosity=1)
        with connection.cursor() as cursor:
            cursor.execute('SHOW CREATE TABLE membership_registrationintake')
            self.assertEqual(cursor.fetchone()[1], table_before)
        self.assertEqual(before, MembershipApplication.objects.filter(pk=application.pk).values().get())
        self.assertIn(HANDOFF_MIGRATION, recorder.applied_migrations())
        print('0007 reversed/forward on synthetic pending data; reversal with a link refused BEFORE DDL. Working database untouched.', flush=True)
