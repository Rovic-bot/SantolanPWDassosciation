"""Verify the catalog upgrade preserves existing identities and inactive choices."""
from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CatalogMigrationTests(TransactionTestCase):
    def test_catalog_is_additive_and_idempotent(self):
        old = [('members', '0004_onsite_profile_capture')]
        target = [('members', '0005_controlled_disability_catalog')]
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate(old)
            apps = MigrationExecutor(connection).loader.project_state(old).apps
            catalog = apps.get_model('members', 'DisabilityType')
            catalog.objects.all().delete()
            catalog.objects.create(name='Retained fictional classification', is_active=False)
            catalog.objects.create(name='Visual Disability', is_active=False)
            before = list(catalog.objects.order_by('pk').values())

            plan = MigrationExecutor(connection).migration_plan(target)
            self.assertEqual([(m.app_label, m.name, reverse) for m, reverse in plan],
                             [('members', '0005_controlled_disability_catalog', False)])
            MigrationExecutor(connection).migrate(target)
            from members.disability_catalog import NAMES
            self.assertEqual(set(catalog.objects.filter(name__in=NAMES)
                                 .values_list('name', flat=True)), set(NAMES))
            for row in before:
                self.assertEqual(catalog.objects.values().get(pk=row['id']), row)
            after = list(catalog.objects.order_by('pk').values())
            migration = import_module('members.migrations.0005_controlled_disability_catalog')
            with connection.schema_editor() as editor:
                migration.add_catalog(apps, editor)
            self.assertEqual(list(catalog.objects.order_by('pk').values()), after)
        finally:
            MigrationExecutor(connection).migrate(leaves)
