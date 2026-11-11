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
        loader = MigrationLoader(None)
        child = loader.disk_migrations[('membership', '0007_registration_membership_handoff')]
        child_base = loader.project_state([('membership', name)])
        with connection.schema_editor() as editor:
            child.unapply(child_base.clone(), editor)
        baseline = loader.project_state()
        for model in created:
            baseline.remove_model('membership', model)
        # The temporary baseline already contains current model tables. Remove
        # only the five empty extension tables, then execute their exact migration.
        with connection.schema_editor() as editor:
            migration.unapply(baseline.clone(), editor)
        tables = set(connection.introspection.table_names())
        self.assertFalse(any('membership_' + model in tables for model in created))
        existing = MembershipApplication.objects.create(**profile(), submission_key=uuid4())
        before = MembershipApplication.objects.filter(pk=existing.pk).values().get()
        require_disposable()
        with connection.schema_editor() as editor:
            migration.apply(baseline.clone(), editor)
        self.assertEqual(before, MembershipApplication.objects.filter(pk=existing.pk).values().get())
        after_tables = set(connection.introspection.table_names())
        self.assertTrue(all('membership_' + model in after_tables for model in created))
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy()):
            binding = services.binding_for('synthetic-upgrade-session')
            context = services.issue_context(binding)
            intake = services.submit_registration(context.pk, binding, submitted())
        with self.assertRaises(IntegrityError), transaction.atomic(), registration_write():
            intake.membership_application = existing
            intake.save()
        intake.refresh_from_db()
        with self.assertRaises(IntegrityError), transaction.atomic(), registration_write():
            intake.category = 'pdao'
            intake.save()
        print('Reviewed migration membership.0006_association_pending_intake: new tables reversed once and applied once; '
              'synthetic legacy row unchanged; PDAO and handoff constraints enforced. No historical migrations executed.', flush=True)
        with connection.schema_editor() as editor:
            child.apply(child_base.clone(), editor)
