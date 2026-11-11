"""Rehearse only the additive notification migration on disposable MySQL."""
from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from assistance.referral_models import ReferralSettings, referral_write
from assistance.tests import create_application, seed_statuses
from scripts.durable_test_runner import require_disposable
from .decision_email_models import ApplicationDecisionEmail, ApplicationDecisionEmailAttempt
from .models import ProgramApplication


class DecisionEmailMigrationTests(TransactionTestCase):
    def test_additive_tables_preserve_existing_applications_and_sender(self):
        require_disposable()
        seed_statuses()
        application = create_application()
        before = ProgramApplication.objects.values().get(pk=application.pk)
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='migration@example.invalid', version=8)
        old_state = ProjectState.from_apps(apps)
        old_state.remove_model('programs', 'applicationdecisionemailattempt')
        old_state.remove_model('programs', 'applicationdecisionemail')
        migration = import_module('programs.migrations.0006_application_decision_email').Migration(
            '0006_application_decision_email', 'programs')
        self.assertEqual([type(operation).__name__ for operation in migration.operations],
                         ['CreateModel', 'CreateModel'] + ['AddConstraint'] * 5)
        try:
            with connection.schema_editor() as editor:
                editor.delete_model(ApplicationDecisionEmailAttempt)
                editor.delete_model(ApplicationDecisionEmail)
            with connection.schema_editor() as editor:
                migration.apply(old_state, editor)
            self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), before)
            self.assertEqual(ReferralSettings.objects.get(pk=1).sender_email, 'migration@example.invalid')
            self.assertEqual(ReferralSettings.objects.get(pk=1).version, 8)
            self.assertFalse(ApplicationDecisionEmail.objects.exists())
            self.assertFalse(ApplicationDecisionEmailAttempt.objects.exists())
        finally:
            for model in (ApplicationDecisionEmail, ApplicationDecisionEmailAttempt):
                if model._meta.db_table not in connection.introspection.table_names():
                    with connection.schema_editor() as editor:
                        editor.create_model(model)
