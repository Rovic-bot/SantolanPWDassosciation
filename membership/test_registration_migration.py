"""Execute only the reviewed additive migration on a verified synthetic baseline.

Baseline tables are model-synchronized by the isolated runner; this is not a
blanket migration/history test or proof of every historical deployment upgrade.
"""
from importlib import import_module
from uuid import uuid4

from django.db import connection, transaction, IntegrityError
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase, override_settings

from scripts.durable_test_runner import require_disposable
from membership.models import MembershipApplication
from membership.tests import profile
from .test_registration_intake import synthetic_policy, submitted
from . import registration_services as services
from .registration_models import RegistrationIntake, registration_write


class RegistrationMigrationTests(TransactionTestCase):
    def test_exact_additive_migration_preserves_legacy_row_and_enforces_constraints(self):
        require_disposable()
        name = '0006_association_pending_intake'
        migration = import_module(f'membership.migrations.{name}').Migration(name, 'membership')
        allowed = {'CreateModel', 'AddField', 'AddIndex', 'AddConstraint'}
        self.assertTrue(all(type(operation).__name__ in allowed for operation in migration.operations))
        created = {operation.name.lower() for operation in migration.operations if type(operation).__name__ == 'CreateModel'}
        self.assertEqual(created, {'registrationintake', 'registrationrevision', 'registrationattachment',
            'registrationaction', 'registrationsubmissioncontext'})
        self.assertTrue(all(getattr(operation, 'model_name', '').lower() in created for operation in migration.operations
            if type(operation).__name__ != 'CreateModel'))
        from scripts.migration_test_support import migration_database, historical_apps, pending_intake
        from django.db.migrations.executor import MigrationExecutor
        parent = [('membership', '0005_onsite_profile_capture')]
        target = [('membership', name)]
        with migration_database(parent) as database:
            before_apps = historical_apps(database, parent)
            Legacy = before_apps.get_model('membership', 'MembershipApplication')
            existing = Legacy.objects.using(database.alias).create(**profile(), submission_key=uuid4())
            original = Legacy.objects.using(database.alias).values().get(pk=existing.pk)
            MigrationExecutor(database).migrate(target)
            state_apps = historical_apps(database, target)
            intake = pending_intake(database, state_apps)
            self.assertEqual(Legacy.objects.using(database.alias).values().get(pk=existing.pk), original)
            self.assertTrue(all('membership_' + model in database.introspection.table_names() for model in created))
            Intake = state_apps.get_model('membership', 'RegistrationIntake')
            with self.assertRaises(IntegrityError), transaction.atomic(using=database.alias):
                Intake.objects.using(database.alias).filter(pk=intake.pk).update(membership_application_id=existing.pk)
            with self.assertRaises(IntegrityError), transaction.atomic(using=database.alias):
                Intake.objects.using(database.alias).filter(pk=intake.pk).update(category='pdao')
            self.assertEqual(Intake.objects.using(database.alias).get(pk=intake.pk).category, 'association')
