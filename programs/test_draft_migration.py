from importlib import import_module

from django.apps import apps
from django.db import connection, IntegrityError, transaction
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from scripts.durable_test_runner import require_disposable
from .models import Program
from .tests import create_program


class DraftMigrationTests(TransactionTestCase):
    def test_nullable_dates_migration_preserves_existing_records(self):
        require_disposable()
        program = create_program()
        before = Program.objects.values().get(pk=program.pk)
        state = ProjectState.from_apps(apps)
        model = state.models['programs', 'program']
        constraint = next(c for c in model.options['constraints'] if c.name == 'public_program_complete')
        model.options['constraints'] = [c for c in model.options['constraints'] if c.name != constraint.name]
        for name in ('name', 'description', 'assistance_type', 'registration_opens_at', 'registration_closes_at'):
            model.fields[name].blank = False
            model.fields[name].null = False
        original_model = state.apps.get_model('programs', 'Program')
        with connection.schema_editor() as editor:
            editor.remove_constraint(Program, constraint)
            for name in ('registration_opens_at', 'registration_closes_at'):
                editor.alter_field(Program, Program._meta.get_field(name), original_model._meta.get_field(name))
        migration = import_module('programs.migrations.0008_incomplete_program_drafts').Migration(
            '0008_incomplete_program_drafts', 'programs')
        with connection.schema_editor() as editor:
            state = migration.apply(state, editor)
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        draft = Program.objects.create()
        self.assertIsNone(Program.objects.get(pk=draft.pk).registration_opens_at)
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, Program._meta.db_table)
        self.assertIn('public_program_complete', constraints)
        # Leave the schema at the current definition after exercising the old migration.
        latest = import_module('programs.migrations.0009_optional_public_description').Migration(
            '0009_optional_public_description', 'programs')
        with connection.schema_editor() as editor:
            latest.apply(state, editor)

    def test_optional_description_migration_preserves_rows_and_other_publication_requirements(self):
        require_disposable()
        program = create_program()
        before = Program.objects.values().get(pk=program.pk)
        old = import_module('programs.migrations.0008_incomplete_program_drafts').Migration.operations[-1].constraint
        current = next(c for c in Program._meta.constraints if c.name == old.name)
        state = ProjectState.from_apps(apps)
        model = state.models['programs', 'program']
        model.options['constraints'] = [old if c.name == old.name else c for c in model.options['constraints']]
        with connection.schema_editor() as editor:
            editor.remove_constraint(Program, current)
            editor.add_constraint(Program, old)
        migration = import_module('programs.migrations.0009_optional_public_description').Migration(
            '0009_optional_public_description', 'programs')
        with connection.schema_editor() as editor:
            migration.apply(state, editor)
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        blank = create_program(description='', benefit='')
        self.assertEqual(Program.objects.get(pk=blank.pk).description, '')
        for changes in ({'name': ''}, {'assistance_type': ''}, {'registration_opens_at': None},
                        {'registration_closes_at': None}):
            with self.subTest(changes=changes), transaction.atomic(), self.assertRaises(IntegrityError):
                Program.objects.filter(pk=blank.pk).update(**changes)
