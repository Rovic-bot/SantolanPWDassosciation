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
    def test_both_pending_migrations_allow_startup_and_observance_routes_fail_closed(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from events.tests import create_event

        actor = get_user_model().objects.create_superuser('fictional_pending_startup')
        event = create_event(title='Fictional retained association event')
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('ewaf', '0004_scoring_diagnostics')])
            MigrationExecutor(connection).migrate([('events', '0005_revised_seventy_workflow')])
            tables = set(connection.introspection.table_names())
            history = set(MigrationExecutor(connection).loader.applied_migrations)

            def read_only(execute, sql, params, many, context):
                self.assertTrue(sql.lstrip().upper().startswith(('SELECT', 'SHOW')), sql)
                return execute(sql, params, many, context)

            output = StringIO()
            with connection.execute_wrapper(read_only):
                Command(stdout=output).check_migrations()
            self.assertIn('Annual observance setup is pending', output.getvalue())
            self.assertIn('Live EWAF processing remains disabled', output.getvalue())
            self.assertEqual(set(connection.introspection.table_names()), tables)
            self.assertEqual(set(MigrationExecutor(connection).loader.applied_migrations), history)
            self.assertNotIn('events_annualobservance', tables)
            self.assertFalse(any(name.startswith('ewaf_durable') for name in tables))
            for url in ('/', '/accounts/login/', '/events/', '/events/?period=past'):
                self.assertEqual(self.client.get(url).status_code, 200)
            calendar = self.client.get('/events/')
            self.assertNotContains(calendar, event.title)
            self.assertEqual(len(calendar.context['observance_months']), 12)
            self.assertTrue(type(event).objects.filter(pk=event.pk, title=event.title).exists())
            self.client.force_login(actor)
            self.assertContains(self.client.get(reverse('events:observances')), 'Setup pending')
            self.assertEqual(self.client.get(reverse('events:observance_create')).status_code, 503)
            with patch('django.core.management.commands.runserver.run') as serve:
                call_command('runlocal', '127.0.0.1:8000', use_reloader=False, stdout=StringIO())
                serve.assert_called_once()
        finally:
            MigrationExecutor(connection).migrate(leaves)

    def test_real_pending_schema_is_deferred_without_writes_and_pages_still_load(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            # Reproduce the normal checkpoint only in the fresh disposable database.
            executor.migrate([('ewaf', '0004_scoring_diagnostics')])
            before = set(connection.introspection.table_names())
            history = set(MigrationExecutor(connection).loader.applied_migrations)
            output = StringIO()
            command = Command(stdout=output)

            def read_only(execute, sql, params, many, context):
                self.assertTrue(sql.lstrip().upper().startswith(('SELECT', 'SHOW')), sql)
                return execute(sql, params, many, context)

            with connection.execute_wrapper(read_only):
                command.check_migrations()
            self.assertIn('remain unapplied as intended', output.getvalue())
            self.assertEqual(set(connection.introspection.table_names()), before)
            self.assertEqual(set(MigrationExecutor(connection).loader.applied_migrations), history)
            self.assertFalse(any(name.startswith('ewaf_durable') for name in before))
            self.assertEqual(self.client.get('/').status_code, 200)
            self.assertEqual(self.client.get('/accounts/login/').status_code, 200)
            # Exercise the actual startup command through checks to server dispatch,
            # without opening a listener during the test suite.
            with patch('django.core.management.commands.runserver.run') as serve:
                call_command('runlocal', '127.0.0.1:8000', use_reloader=False, stdout=StringIO())
                serve.assert_called_once()
            from ewaf.durable_services import require_operational_result
            from django.core.exceptions import ValidationError
            with self.assertRaises(ValidationError):
                require_operational_result()
        finally:
            MigrationExecutor(connection).migrate(leaves)
