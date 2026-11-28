"""Run historical migration graphs without altering the current test schema."""
from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4

from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import load_backend
from scripts.durable_test_runner import require_disposable


@contextmanager
def migration_database(targets):
    require_disposable()
    name = 'test_g12_migration_' + uuid4().hex
    alias = 'migration_' + uuid4().hex
    config = deepcopy(connection.settings_dict)
    config['NAME'] = name
    config['TEST'] = {'NAME': name}
    with connection.cursor() as cursor:
        cursor.execute('CREATE DATABASE ' + connection.ops.quote_name(name))
    database = load_backend(config['ENGINE']).DatabaseWrapper(config, alias)
    registered = False
    try:
        # Django explicitly allows a newly-created dynamic connection. Establish
        # it before registering the alias; never disable its database guards.
        database.ensure_connection()
        connections.databases[alias] = config
        connections[alias] = database
        registered = True
        executor = MigrationExecutor(database)
        executor.migrate(targets)
        yield database
    finally:
        database.close()
        if registered:
            del connections[alias]
            connections.databases.pop(alias)
        require_disposable()
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE ' + connection.ops.quote_name(name))


def historical_apps(database, targets):
    return MigrationExecutor(database).loader.project_state(targets).apps


def copy_historical_rows(database, apps, rows):
    """Copy a disposable fixture's FK closure using only historical fields."""
    require_disposable()
    if not database.settings_dict['NAME'].startswith('test_g12_migration_'):
        raise AssertionError('Historical fixture destination must be an isolated migration schema.')
    copied = set()

    def copy_row(row):
        key = row._meta.label_lower, row.pk
        if key in copied:
            return
        copied.add(key)
        Model = apps.get_model(row._meta.app_label, row._meta.model_name)
        values = {}
        for field in Model._meta.local_fields:
            if not hasattr(row, field.attname):
                continue
            values[field.attname] = getattr(row, field.attname)
            if field.many_to_one or field.one_to_one:
                related = getattr(row, field.name)
                if related is not None:
                    copy_row(related)
        Model.objects.using(database.alias).update_or_create(pk=row.pk, defaults=values)

    # PostgreSQL defers cyclic fixture references only within a transaction.
    with transaction.atomic(using=database.alias), database.constraint_checks_disabled():
        for row in rows:
            copy_row(row)
        database.check_constraints()


def pending_intake(database, apps):
    """Minimal fictional 0006 row, independent of today's intake services."""
    from django.utils import timezone
    Context = apps.get_model('membership', 'RegistrationSubmissionContext')
    Intake = apps.get_model('membership', 'RegistrationIntake')
    context = Context.objects.using(database.alias).create(
        binding_digest='0' * 64, policy_digest='1' * 64, channel='online',
        expires_at=timezone.now() + timezone.timedelta(hours=1))
    return Intake.objects.using(database.alias).create(
        reference='SYNTHETIC-MIGRATION', request_key=context.request_key,
        payload_digest='2' * 64, channel='online', policy_snapshot={}, context=context)


def assert_additive_upgrade(test, old, new, empty_models, *, rows=None, reversible=False):
    """Rehearse actual historical migrations and compare every retained field.

    The fixture starts in its own historical schema. Current models are used
    only to copy fictional data before the migration; all checks use historical
    registries, so later tables cannot make a historical downgrade fail.
    """
    from django.apps import apps as current_apps
    auth = ('auth', '0012_alter_user_first_name_max_length')
    old, new = [*old, auth], [*new, auth]
    with migration_database(old) as database:
        registry = historical_apps(database, old)
        models = list(registry.get_models(include_auto_created=True))
        if rows is None:
            rows = []
            for model in models:
                try:
                    current = current_apps.get_model(model._meta.app_label, model._meta.model_name)
                except LookupError:
                    continue
                rows.extend(current.objects.all())
        copy_historical_rows(database, registry, rows)
        def snapshot(state):
            return {model._meta.label: list(state.get_model(model._meta.app_label, model._meta.model_name)
                .objects.using(database.alias).order_by('pk')
                .values(*[field.attname for field in model._meta.local_fields])) for model in models}
        before = snapshot(registry)
        for cycle in range(2 if reversible else 1):
            MigrationExecutor(database).migrate(new)
            updated = historical_apps(database, new)
            test.assertEqual(snapshot(updated), before)
            for label in empty_models:
                test.assertFalse(updated.get_model(label).objects.using(database.alias).exists(), label)
            if reversible:
                MigrationExecutor(database).migrate(old)
                test.assertEqual(snapshot(historical_apps(database, old)), before)
