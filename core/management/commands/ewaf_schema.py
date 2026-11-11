"""Inspect only local schema metadata; no member/application table contents."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Read local EWAF schema and migration metadata without migrating or opening applicant records.'

    def handle(self, *args, **options):
        if connection.settings_dict['HOST'] not in ('127.0.0.1', 'localhost', '::1'):
            raise CommandError('Schema inspection is restricted to explicitly local MySQL.')
        def metadata_only(execute, sql, params, many, context):
            if not sql.lstrip().upper().startswith(('SELECT', 'SHOW', 'SET')):
                raise CommandError('Refusing a non-read-only metadata operation.')
            return execute(sql, params, many, context)
        with connection.execute_wrapper(metadata_only):
            tables = sorted(name for name in connection.introspection.table_names() if name.startswith('ewaf_'))
            executor = MigrationExecutor(connection)
            applied = sorted(name for app, name in executor.loader.applied_migrations if app == 'ewaf')
            pending = [m.name for m, backwards in executor.migration_plan(executor.loader.graph.leaf_nodes()) if m.app_label == 'ewaf']
        self.stdout.write(json.dumps({'local_mysql': True, 'inspection': 'schema and migration metadata only',
            'ewaf_tables': tables, 'applied': applied, 'pending': pending, 'migrations_applied_by_command': False}, indent=2))
