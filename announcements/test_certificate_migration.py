from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from assistance.tests import create_application, seed_statuses
from programs.models import ProgramApplication
from scripts.durable_test_runner import require_disposable
from .certificate_models import SelectionCertificateEmail, SelectionCertificateAttempt


class CertificateMigrationTests(TransactionTestCase):
    def test_additive_tables_preserve_application_records(self):
        require_disposable()
        seed_statuses()
        application = create_application()
        before = ProgramApplication.objects.values().get(pk=application.pk)
        from scripts.migration_test_support import migration_database, historical_apps, copy_historical_rows
        from django.db.migrations.executor import MigrationExecutor
        parent = [('announcements', '0005_announcement_categories'), ('programs', '0007_program_picture')]
        target = [('announcements', '0006_selection_certificate_email')]
        with migration_database(parent) as database:
            old_apps = historical_apps(database, parent)
            copy_historical_rows(database, old_apps, [application])
            OldApplication = old_apps.get_model('programs', 'ProgramApplication')
            old = OldApplication.objects.using(database.alias).values().get(pk=application.pk)
            executor = MigrationExecutor(database)
            migration = executor.loader.get_migration(*target[0])
            self.assertEqual([type(operation).__name__ for operation in migration.operations],
                             ['CreateModel', 'CreateModel', 'AddConstraint', 'AddConstraint'])
            executor.migrate(target)
            updated = historical_apps(database, target)
            Application = updated.get_model('programs', 'ProgramApplication')
            self.assertEqual(Application.objects.using(database.alias).values(*old).get(pk=application.pk), old)
            for model in ('SelectionCertificateEmail', 'SelectionCertificateAttempt'):
                self.assertFalse(updated.get_model('announcements', model).objects.using(database.alias).exists())
        self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), before)
