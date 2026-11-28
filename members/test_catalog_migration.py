"""Verify the catalog upgrade preserves existing identities and inactive choices."""
from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CatalogMigrationTests(TransactionTestCase):
    def test_catalog_is_additive_and_idempotent(self):
        old = [('members', '0004_onsite_profile_capture')]
        target = [('members', '0005_controlled_disability_catalog')]
        # Exercise this data migration itself. Rewinding the complete modern
        # graph would reverse unrelated, deliberately irreversible adoption.
        executor = MigrationExecutor(connection)
        state = executor.loader.project_state(old)
        apps = state.apps
        catalog = apps.get_model('members', 'DisabilityType')
        catalog.objects.update_or_create(name='Retained fictional classification', defaults={'is_active': False})
        catalog.objects.update_or_create(name='Visual Disability', defaults={'is_active': False})
        before = list(catalog.objects.order_by('pk').values())
        module = import_module('members.migrations.0005_controlled_disability_catalog')
        migration = module.Migration(target[0][1], target[0][0])
        with connection.schema_editor() as editor:
            migration.apply(state, editor)
        from members.disability_catalog import NAMES
        self.assertEqual(set(catalog.objects.filter(name__in=NAMES).values_list('name', flat=True)), set(NAMES))
        for row in before:
            self.assertEqual(catalog.objects.values().get(pk=row['id']), row)
        after = list(catalog.objects.order_by('pk').values())
        with connection.schema_editor() as editor:
            module.add_catalog(apps, editor)
        self.assertEqual(list(catalog.objects.order_by('pk').values()), after)
