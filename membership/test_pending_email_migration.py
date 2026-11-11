"""Rehearse only the new pending notification tables on disposable MySQL."""
from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from assistance.referral_models import ReferralSettings, referral_write
from scripts.durable_test_runner import require_disposable
from .pending_email_models import MembershipPendingEmail, MembershipPendingEmailAttempt
from .registration_models import RegistrationIntake
from .test_registration_decisions import DecisionHelpers


class MembershipPendingEmailMigrationTests(DecisionHelpers, TransactionTestCase):
    def test_additive_tables_preserve_registration_and_sender(self):
        require_disposable()
        self.setup_decisions()
        intake = self.make()
        before = RegistrationIntake.objects.values().get(pk=intake.pk)
        original = intake.revisions.get().data
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='migration@example.invalid', version=8)
        old_state = ProjectState.from_apps(apps)
        old_state.remove_model('membership', 'membershippendingemailattempt')
        old_state.remove_model('membership', 'membershippendingemail')
        migration = import_module('membership.migrations.0012_membership_pending_email').Migration(
            '0012_membership_pending_email', 'membership')
        self.assertEqual([type(operation).__name__ for operation in migration.operations],
                         ['CreateModel', 'CreateModel'] + ['AddConstraint'] * 4)
        try:
            with connection.schema_editor() as editor:
                editor.delete_model(MembershipPendingEmailAttempt)
                editor.delete_model(MembershipPendingEmail)
            with connection.schema_editor() as editor:
                migration.apply(old_state, editor)
            self.assertEqual(RegistrationIntake.objects.values().get(pk=intake.pk), before)
            self.assertEqual(intake.revisions.get().data, original)
            self.assertEqual(ReferralSettings.objects.get(pk=1).sender_email, 'migration@example.invalid')
            self.assertEqual(ReferralSettings.objects.get(pk=1).version, 8)
            self.assertFalse(MembershipPendingEmail.objects.exists())
            self.assertFalse(MembershipPendingEmailAttempt.objects.exists())
        finally:
            for model in (MembershipPendingEmail, MembershipPendingEmailAttempt):
                if model._meta.db_table not in connection.introspection.table_names():
                    with connection.schema_editor() as editor:
                        editor.create_model(model)
