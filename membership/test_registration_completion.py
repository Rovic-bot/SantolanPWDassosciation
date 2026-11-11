"""Association-only compatibility and exact additive migration rehearsal."""
from io import StringIO
from uuid import uuid4

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from core.management.commands.runlocal import Command, DEFERRED, FOUNDATION_DEFERRED, OBSERVANCE_DEFERRED, DECISION_DEFERRED, OPERATIONAL_DEFERRED
from scripts.durable_test_runner import require_disposable
from . import registration_services as services
from .models import MembershipApplication
from .registration_models import RegistrationIntake
from .test_registration_intake import synthetic_policy, submitted, staff
from .tests import profile


class RegistrationInboxCompletionTests(TestCase):
    def setUp(self):
        require_disposable()
        override = override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy())
        override.enable()
        self.addCleanup(override.disable)
        self.actor = staff('synthetic_inbox_filter', 'membership.review_registrationintake')
        self.client.force_login(self.actor)
        self.url = reverse('membership:registration_inbox')
        self.rows = []
        for number in range(2):
            binding = services.binding_for('synthetic-inbox-' + str(number))
            context = services.issue_context(binding)
            self.rows.append(services.submit_registration(context.pk, binding, submitted(full_name='Synthetic ' + str(number))))
        services.review_registration(self.rows[0].reference, user=self.actor, version=0,
            action='begin_review', reason='Synthetic review')

    def test_state_channel_filter_and_invalid_filter_never_broaden_results(self):
        response = self.client.get(self.url, {'state': 'under_review', 'channel': 'online'})
        self.assertEqual(list(response.context['page_obj']), [self.rows[0]])
        self.assertEqual(self.client.get(self.url, {'channel': 'walk_in'}).context['page_obj'].paginator.count, 0)
        response = self.client.get(self.url, {'state': 'approved'})
        self.assertContains(response, 'Choose a listed processing state')
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_reference_lookup_ignores_filters_without_changing_records(self):
        before = list(RegistrationIntake.objects.values())
        response = self.client.get(self.url, {'reference': self.rows[1].reference, 'state': 'under_review'})
        self.assertEqual(list(response.context['page_obj']), [self.rows[1]])
        self.assertEqual(before, list(RegistrationIntake.objects.values()))
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {'state': 'received'}).status_code, 302)


class RegistrationMigrationLifecycleTests(TransactionTestCase):
    def test_exact_forward_reverse_history_metadata_and_startup_guard(self):
        require_disposable()
        target = ('membership', '0006_association_pending_intake')
        parent = ('membership', '0005_onsite_profile_capture')
        loader = MigrationLoader(None)
        child = ('membership', '0007_registration_membership_handoff')
        handoff = loader.disk_migrations[child]
        with connection.schema_editor() as editor:
            handoff.unapply(loader.project_state([target]), editor)
        migration = loader.disk_migrations[target]
        names = {op.name.lower() for op in migration.operations if type(op).__name__ == 'CreateModel'}
        # This is an explicitly synthetic model-derived schema/history fixture,
        # not a claim of a historical upgrade or a working-history repair.
        state = loader.project_state()
        for name in names:
            state.remove_model('membership', name)
        with connection.schema_editor() as editor:
            migration.unapply(state.clone(), editor)
        ContentType.objects.filter(app_label='membership', model__in=names).delete()
        ContentType.objects.clear_cache()
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        recorder.migration_qs.all().delete()
        deferred = {DEFERRED, FOUNDATION_DEFERRED, OBSERVANCE_DEFERRED, DECISION_DEFERRED, OPERATIONAL_DEFERRED}
        for app, name in sorted(set(loader.disk_migrations) - deferred - {target, child}):
            recorder.record_applied(app, name)
        legacy = MembershipApplication.objects.create(**profile(), submission_key=uuid4())
        snapshot = MembershipApplication.objects.filter(pk=legacy.pk).values().get()
        baseline_history = set(recorder.applied_migrations())
        with self.assertRaisesMessage(CommandError, 'membership.0006_association_pending_intake'):
            Command(stdout=StringIO()).pending_migrations()
        executor = MigrationExecutor(connection)
        self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in executor.migration_plan([target])],
                         [('membership', target[1], False)])
        call_command('migrate', 'membership', target[1], interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(set(recorder.applied_migrations()), baseline_history | {target})
        with self.assertRaisesMessage(CommandError, child[1]):
            Command(stdout=StringIO()).pending_migrations()
        call_command('migrate', *child, interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(Command(stdout=StringIO()).pending_migrations(), deferred)
        self.assertEqual(MembershipApplication.objects.filter(pk=legacy.pk).values().get(), snapshot)
        self.assertEqual(ContentType.objects.filter(app_label='membership', model__in=names).count(), 5)
        self.assertTrue(Permission.objects.filter(content_type__app_label='membership',
            codename='view_registration_documents').exists())
        self.assertFalse(Permission.objects.filter(content_type__app_label='membership',
            content_type__model__in=names, user__isnull=False).exists())
        # Reverse the new child first. Original 0006 assertions remain scoped to
        # its exact one-operation plan; no historical migration is executed.
        call_command('migrate', *target, interactive=False, verbosity=0, stdout=StringIO())
        executor = MigrationExecutor(connection)
        self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in executor.migration_plan([parent])],
                         [('membership', target[1], True)])
        call_command('migrate', 'membership', parent[1], interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(set(recorder.applied_migrations()), baseline_history)
        self.assertFalse(any('membership_' + name in connection.introspection.table_names() for name in names))
        self.assertEqual(MembershipApplication.objects.filter(pk=legacy.pk).values().get(), snapshot)
        with self.assertRaisesMessage(CommandError, target[1]):
            Command(stdout=StringIO()).pending_migrations()
        # Restore the temporary model-derived test schema for subsequent flush.
        call_command('migrate', 'membership', target[1], interactive=False, verbosity=0, stdout=StringIO())
        call_command('migrate', *child, interactive=False, verbosity=0, stdout=StringIO())
        print('Exact membership 0006 lifecycle: forward/reverse/forward, real migration recorder and permission metadata; '
              'synthetic legacy row unchanged. Synthetic baseline history only; no historical migrations executed.', flush=True)
