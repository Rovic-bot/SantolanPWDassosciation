"""Determine which models genuinely predate a rehearsed schema rollback."""
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def surviving_models(target):
    plan = MigrationExecutor(connection).migration_plan([target])
    removed = {(migration.app_label, operation.name.lower())
        for migration, backwards in plan if backwards
        for operation in migration.operations if type(operation).__name__ == 'CreateModel'}
    return [model for model in apps.get_models() if (model._meta.app_label, model._meta.model_name) not in removed]
