"""Exact reviewed new migrations on synthetic model-derived schema/history only."""
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase, SimpleTestCase
from django.core.exceptions import PermissionDenied
from unittest.mock import patch

from scripts.durable_test_runner import require_disposable
from scripts.remaining_phases_test_runner import REVIEWED_MIGRATIONS


class RemainingRunnerScopeTests(SimpleTestCase):
    def test_mixed_plan_is_refused_before_any_partial_operation(self):
        loader = MigrationLoader(None)
        executor = object.__new__(MigrationExecutor)
        executor.migration_plan = lambda targets: [
            (loader.disk_migrations[('core', '0002_resource_publication_metadata')], True),
            (loader.disk_migrations[('core', '0001_revised_seventy_workflow')], True)]
        with patch.object(MigrationExecutor, 'apply_migration') as apply, patch.object(MigrationExecutor, 'unapply_migration') as unapply:
            with self.assertRaisesMessage(PermissionDenied, 'outside the exact reviewed'):
                executor.migrate([('core', None)])
            apply.assert_not_called()
            unapply.assert_not_called()
        with self.assertRaisesMessage(PermissionDenied, 'Fake migration'):
            executor.migrate([], fake=True)


class AdditiveSchemaLifecycleTests(TransactionTestCase):
    def test_exact_reviewed_migrations_reverse_forward_preserve_old_rows(self):
        require_disposable()
        from members.tests import create_member
        from members.models import Member
        member = create_member('SYNTHETIC-SCHEMA-REHEARSAL')
        before = Member.objects.filter(pk=member.pk).values().get()
        from core.models import PublicContent, ContentRevision
        content = PublicContent.objects.create(key='contact', title='Retained synthetic guide', body='Retained original text',
            published={'title': 'Retained public title', 'body': 'Retained public text'}, version=3)
        content_fields = ('key', 'title', 'body', 'published', 'version', 'updated_at', 'updated_by_id')
        old_content = PublicContent.objects.filter(pk=content.pk).values(*content_fields).get()
        revision = ContentRevision.objects.create(content=content, actor_label='Synthetic historical editor',
            action='publish', reason='Synthetic retained history', before={}, after=content.published)
        old_revision = ContentRevision.objects.filter(pk=revision.pk).values().get()
        loader = MigrationLoader(None)
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        recorder.migration_qs.all().delete()
        # Explicit fixture history; baseline migrations are NOT executed/faked on
        # working data. This does not validate a deployed historical baseline.
        for key in loader.disk_migrations:
            recorder.record_applied(*key)
        child = ('membership', '0007_registration_membership_handoff')
        # Rehearse the older additions at their own schema version; restore the
        # new handoff child afterward. Its refusal/lifecycle has a separate test.
        call_command('migrate', 'membership', '0006_association_pending_intake',
                     interactive=False, verbosity=0, stdout=StringIO())
        baseline = set(recorder.applied_migrations())
        for target in (key for key in REVIEWED_MIGRATIONS if key != child):
            migration = loader.disk_migrations[target]
            parents = [key for key in migration.dependencies if key[0] == target[0]]
            self.assertEqual(len(parents), 1)
            plan = MigrationExecutor(connection).migration_plan(parents)
            self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in plan], [(*target, True)])
            call_command('migrate', *parents[0], interactive=False, verbosity=0, stdout=StringIO())
            self.assertEqual(set(recorder.applied_migrations()), baseline - {target})
            plan = MigrationExecutor(connection).migration_plan([target])
            self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in plan], [(*target, False)])
            call_command('migrate', *target, interactive=False, verbosity=0, stdout=StringIO())
            self.assertEqual(set(recorder.applied_migrations()), baseline)
            self.assertEqual(Member.objects.filter(pk=member.pk).values().get(), before)
            self.assertEqual(PublicContent.objects.filter(pk=content.pk).values(*content_fields).get(), old_content)
            self.assertEqual(ContentRevision.objects.filter(pk=revision.pk).values().get(), old_revision)
            print('Reviewed additive reverse/forward passed:', target, 'synthetic model-derived schema/history only.', flush=True)
        call_command('migrate', *child, interactive=False, verbosity=0, stdout=StringIO())
