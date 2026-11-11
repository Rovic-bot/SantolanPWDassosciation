from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from . import tests as intake_tests
from .models import ApplicationCode, SocioeconomicReview


@override_settings(PROGRAM_INTAKE_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=True)
class IntakeMigrationTests(TransactionTestCase):
    setUp = intake_tests.IntakeTests.setUp

    def test_additive_intake_schema_round_trip_preserves_every_preexisting_row(self):
        models = [model for model in apps.get_models() if model._meta.app_label != 'program_intake']
        def rows():
            return {model._meta.label: list(model.objects.order_by('pk').values()) for model in models}
        before = rows()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        new_tables = {ApplicationCode._meta.db_table, SocioeconomicReview._meta.db_table}
        try:
            MigrationExecutor(connection).migrate([('program_intake', None)])
            self.assertFalse(new_tables.intersection(connection.introspection.table_names()))
            self.assertEqual(rows(), before)
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(rows(), before)
            self.assertTrue(new_tables <= set(connection.introspection.table_names()))
            self.assertFalse(ApplicationCode.objects.exists())
            self.assertFalse(SocioeconomicReview.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
