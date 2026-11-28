"""Startup exception is exact; actual schema checks use disposable MySQL only."""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management.base import CommandError
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from core.management.commands.runlocal import Command, validate_plan


def planned(app, name, backwards=False):
    return (SimpleNamespace(app_label=app, name=name), backwards)


class LocalStartupPolicyTests(SimpleTestCase):
    def test_current_schema_needs_no_exception(self):
        self.assertFalse(validate_plan([]))

    def test_only_exact_development_migration_may_be_deferred(self):
        self.assertTrue(validate_plan([planned('ewaf', '0005_durable_development')]))

    def test_exact_observance_migration_may_be_deferred_alone_or_with_ewaf(self):
        self.assertTrue(validate_plan([planned('events', '0006_annual_observances')]))
        self.assertTrue(validate_plan([planned('events', '0006_annual_observances'),
                                       planned('ewaf', '0005_durable_development')]))

    def test_earlier_other_or_future_migration_still_blocks(self):
        for item in (planned('ewaf', '0004_scoring_diagnostics'), planned('programs', '0005_approved_terms'),
                     planned('ewaf', '0006_future'), planned('ewaf', '0005_durable_development', True),
                     planned('events', '0005_revised_seventy_workflow'), planned('events', '0007_future'),
                     planned('events', '0006_annual_observances', True)):
            with self.subTest(item=item), self.assertRaises(CommandError):
                validate_plan([planned('ewaf', '0005_durable_development'), item])

    def test_changed_deferred_file_is_not_silently_allowed(self):
        with patch('core.management.commands.runlocal.DEFERRED_SHA256', '0' * 64), self.assertRaises(CommandError):
            validate_plan([planned('ewaf', '0005_durable_development')])

    def test_changed_observance_migration_still_blocks(self):
        with patch('core.management.commands.runlocal.OBSERVANCE_SHA256', '0' * 64), self.assertRaises(CommandError):
            validate_plan([planned('events', '0006_annual_observances'),
                           planned('ewaf', '0005_durable_development')])

    def test_registration_schema_is_required_and_deferred_features_are_not_reported_as_blockers(self):
        for app, name in (('documents', '0004_onsite_profile_capture'),
                          ('members', '0004_onsite_profile_capture'),
                          ('membership', '0005_onsite_profile_capture')):
            with self.subTest(app=app), self.assertRaises(CommandError) as caught:
                validate_plan([planned('events', '0006_annual_observances'), planned(app, name)])
            message = str(caught.exception)
            self.assertIn(f'{app}.{name}', message)
            self.assertNotIn('events.0006_annual_observances', message)
            self.assertIn('No migrations were applied', message)

    def test_missing_schema_fails_before_autoreloader_starts(self):
        command = Command(stdout=StringIO())
        with patch.object(command, 'pending_migrations', side_effect=CommandError('Required schema missing')), \
                patch('django.core.management.commands.runserver.autoreload.run_with_reloader') as reload:
            with self.assertRaisesMessage(CommandError, 'Required schema missing'):
                command.run(use_reloader=True)
            reload.assert_not_called()

    def test_valid_schema_still_starts_autoreloader(self):
        command = Command(stdout=StringIO())
        with patch.object(command, 'pending_migrations', return_value=set()) as inspect, \
                patch('django.core.management.commands.runserver.autoreload.run_with_reloader') as reload:
            command.run(use_reloader=True)
            inspect.assert_called_once_with()
            reload.assert_called_once()


class LocalStartupDatabaseTests(TransactionTestCase):
    def assert_read_only_check(self):
        def read_only(execute, sql, params, many, context):
            self.assertTrue(sql.lstrip().upper().startswith(('SELECT', 'SHOW')), sql)
            return execute(sql, params, many, context)
        with connection.execute_wrapper(read_only):
            return Command(stdout=StringIO()).pending_migrations()

    def test_current_migrated_schema_starts_without_writes(self):
        tables = set(connection.introspection.table_names())
        history = set(MigrationExecutor(connection).loader.applied_migrations)
        self.assertEqual(self.assert_read_only_check(), set())
        self.assertEqual(set(connection.introspection.table_names()), tables)
        self.assertEqual(set(MigrationExecutor(connection).loader.applied_migrations), history)
        for url in ('/', '/accounts/login/', '/events/', '/events/?period=past'):
            self.assertEqual(self.client.get(url).status_code, 200)
        with patch('django.core.management.commands.runserver.run') as serve:
            call_command('runlocal', '127.0.0.1:8000', use_reloader=False, stdout=StringIO())
            serve.assert_called_once()

    def test_required_pending_migration_blocks_startup_without_applying_it(self):
        from django.db.migrations.recorder import MigrationRecorder
        # Change only the disposable migration ledger, never reverse irreversible
        # business migrations. The real loader must identify the missing leaf.
        from scripts.durable_test_runner import require_disposable
        require_disposable()
        executor = MigrationExecutor(connection)
        required = next(node for node in executor.loader.graph.leaf_nodes() if node[0] == 'core')
        recorder = MigrationRecorder(connection)
        tables = set(connection.introspection.table_names())
        recorder.record_unapplied(*required)
        try:
            with self.assertRaisesMessage(CommandError, '.'.join(required)):
                self.assert_read_only_check()
            with patch('django.core.management.commands.runserver.run') as serve:
                with self.assertRaises(CommandError):
                    call_command('runlocal', '127.0.0.1:8000', use_reloader=False, stdout=StringIO())
                serve.assert_not_called()
            self.assertEqual(set(connection.introspection.table_names()), tables)
            self.assertNotIn(required, recorder.applied_migrations())
        finally:
            recorder.record_applied(*required)
