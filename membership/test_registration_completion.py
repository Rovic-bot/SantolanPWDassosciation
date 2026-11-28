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

    def test_state_filters_validate_and_retired_channel_cannot_hide_results(self):
        response = self.client.get(self.url, {'state': 'under_review', 'channel': 'online'})
        self.assertEqual(list(response.context['page_obj']), [self.rows[0]])
        self.assertEqual(self.client.get(self.url, {'channel': 'walk_in'}).context['page_obj'].paginator.count, 2)
        response = self.client.get(self.url, {'state': 'approved'})
        self.assertContains(response, 'Choose a listed processing status')
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
        from scripts.migration_test_support import migration_database, historical_apps
        from django.contrib.auth.management import create_permissions
        target = ('membership', '0006_association_pending_intake')
        parent = ('membership', '0005_onsite_profile_capture')
        # The historical membership branch only depends on auth's initial
        # schema. Permissions need its later 255-character name migration.
        with migration_database([parent, ('auth', '0012_alter_user_first_name_max_length')]) as database:
            old_apps = historical_apps(database, [parent])
            Legacy = old_apps.get_model('membership', 'MembershipApplication')
            legacy = Legacy.objects.using(database.alias).create(**profile(), submission_key=uuid4())
            original = Legacy.objects.using(database.alias).values().get(pk=legacy.pk)
            recorder = MigrationRecorder(database)
            before = set(recorder.applied_migrations())
            executor = MigrationExecutor(database)
            plan = executor.migration_plan([target])
            self.assertEqual([(m.app_label, m.name, backwards) for m, backwards in plan], [(*target, False)])
            from core.management.commands.runlocal import validate_plan
            with self.assertRaisesMessage(CommandError, target[1]):
                validate_plan(plan)
            executor.migrate([target])
            self.assertEqual(set(recorder.applied_migrations()), before | {target})
            state_apps = historical_apps(database, [target, ('auth', '0012_alter_user_first_name_max_length')])
            create_permissions(apps.get_app_config('membership'), verbosity=0,
                               apps=state_apps, using=database.alias)
            Permissions = state_apps.get_model('auth', 'Permission')
            self.assertTrue(Permissions.objects.using(database.alias).filter(
                content_type__app_label='membership', codename='view_registration_documents').exists())
            self.assertEqual(Legacy.objects.using(database.alias).values().get(pk=legacy.pk), original)
            MigrationExecutor(database).migrate([parent])
            self.assertEqual(set(recorder.applied_migrations()), before)
            self.assertNotIn('membership_registrationintake', database.introspection.table_names())
            self.assertEqual(Legacy.objects.using(database.alias).values().get(pk=legacy.pk), original)
            MigrationExecutor(database).migrate([target])
            self.assertIn('membership_registrationintake', database.introspection.table_names())
            self.assertEqual(Legacy.objects.using(database.alias).values().get(pk=legacy.pk), original)
