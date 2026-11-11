"""Local development server with a narrowly reviewed migration deferral."""
from hashlib import sha256
from pathlib import Path

from django.contrib.staticfiles.management.commands.runserver import Command as RunserverCommand
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor


# Only explicitly reviewed, safely unavailable features may lack tables at startup.
# Pin the reviewed file: a future edit or dependent migration needs a new review.
DEFERRED = ('ewaf', '0005_durable_development')
DEFERRED_SHA256 = 'da54fb46e014b14fe8d12f62fd4f0662babcfaf15a6860bb6a4cf259cba7d9e9'
MIGRATION_FILE = Path(__file__).resolve().parents[3] / 'ewaf/migrations/0005_durable_development.py'
FOUNDATION_DEFERRED = ('ewaf', '0006_source_invalidation_foundation')
FOUNDATION_SHA256 = 'b7a9a78aa36de0fb05c0ca57bce6596caf8d337c56b4394f9411a7c9d6874540'
FOUNDATION_MIGRATION_FILE = Path(__file__).resolve().parents[3] / 'ewaf/migrations/0006_source_invalidation_foundation.py'
OBSERVANCE_DEFERRED = ('events', '0006_annual_observances')
OBSERVANCE_SHA256 = '0df6e6a58546dc9406ac0c10ae4e178e22e82702174e2c1fd15adab27d3bc0db'
OBSERVANCE_MIGRATION_FILE = Path(__file__).resolve().parents[3] / 'events/migrations/0006_annual_observances.py'
DECISION_DEFERRED = ('ewaf', '0007_development_human_decisions')
DECISION_SHA256 = '955cfef9b040d6a2c901ae4235515115b58b0c53d2ede985e04d66679afe96f2'
DECISION_MIGRATION_FILE = Path(__file__).resolve().parents[3] / 'ewaf/migrations/0007_development_human_decisions.py'
OPERATIONAL_DEFERRED = ('ewaf', '0008_operational_four')
OPERATIONAL_SHA256 = 'b076df37cb0d5bb5e808e5e09a72f2f3ac7fda4477f84978e9dc6d78a77413d7'
OPERATIONAL_MIGRATION_FILE = Path(__file__).resolve().parents[3] / 'ewaf/migrations/0008_operational_four.py'


def validate_plan(plan):
    pending = [(migration.app_label, migration.name) for migration, backwards in plan]
    deferred = (DEFERRED, FOUNDATION_DEFERRED, OBSERVANCE_DEFERRED, DECISION_DEFERRED, OPERATIONAL_DEFERRED)
    if any(backwards for migration, backwards in plan) or any(
            item not in deferred for item in pending):
        labels = ', '.join(f'{migration.app_label}.{migration.name}' +
                          (' (backwards)' if backwards else '')
                          for migration, backwards in plan
                          if backwards or (migration.app_label, migration.name) not in deferred)
        raise CommandError('Required application migrations are pending: ' + labels +
            '. Startup stopped before opening the website. Back up the database and verify '
            'these migrations in disposable MySQL before applying them to the authorized local database. '
            'Do not run a blanket migrate command or apply disposable-only EWAF migrations. '
            'No migrations were applied.')
    # Normalize Windows/Git newlines only; substantive file changes still block.
    if DEFERRED in pending and sha256(MIGRATION_FILE.read_text(encoding='utf-8').encode('utf-8')).hexdigest() != DEFERRED_SHA256:
        raise CommandError('The deferred EWAF migration changed. Review startup compatibility before proceeding.')
    if (FOUNDATION_DEFERRED in pending and
            sha256(FOUNDATION_MIGRATION_FILE.read_text(encoding='utf-8').encode('utf-8')).hexdigest() != FOUNDATION_SHA256):
        raise CommandError('The deferred EWAF foundation migration changed. Review startup compatibility before proceeding.')
    if (OBSERVANCE_DEFERRED in pending and
            sha256(OBSERVANCE_MIGRATION_FILE.read_text(encoding='utf-8').encode('utf-8')).hexdigest() != OBSERVANCE_SHA256):
        raise CommandError('The deferred annual observance migration changed. Review startup compatibility before proceeding.')
    if (DECISION_DEFERRED in pending and
            sha256(DECISION_MIGRATION_FILE.read_text(encoding='utf-8').encode('utf-8')).hexdigest() != DECISION_SHA256):
        raise CommandError('The deferred fictional decision migration changed. Review startup compatibility before proceeding.')
    if (OPERATIONAL_DEFERRED in pending and
            sha256(OPERATIONAL_MIGRATION_FILE.read_text(encoding='utf-8').encode('utf-8')).hexdigest() != OPERATIONAL_SHA256):
        raise CommandError('The operational EWAF migration changed. Review startup compatibility before proceeding.')
    return bool(pending)


class Command(RunserverCommand):
    help = 'Start the local website with only the reviewed, unavailable-feature migrations deferred.'

    def pending_migrations(self):
        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        validate_plan(plan)
        return {(migration.app_label, migration.name) for migration, backwards in plan}

    def run(self, **options):
        # Fail in the main management-command thread, before StatReloader starts.
        # The launcher then receives a clean CommandError and a nonzero exit code.
        self.pending_migrations()
        super().run(**options)

    def check_migrations(self):
        pending = self.pending_migrations()
        if pending:
            if DEFERRED in pending or FOUNDATION_DEFERRED in pending or DECISION_DEFERRED in pending:
                self.stdout.write('EWAF development tables remain unapplied as intended. '
                    'Live EWAF processing remains disabled.')
            if OBSERVANCE_DEFERRED in pending:
                self.stdout.write('Annual observance setup is pending. The website can start; '
                    'observance editing and photo uploads await the separately approved Events migration.')
            self.stdout.write('No migrations were applied or faked.\n')
