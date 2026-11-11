"""Apply only the new credential-column migration on disposable MySQL."""
from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from scripts.durable_test_runner import require_disposable
from .referral_models import ReferralSettings, referral_write


class GmailConnectionMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_sender_and_starts_disconnected(self):
        require_disposable()
        with referral_write():
            ReferralSettings.objects.create(pk=1, sender_email='migration@example.invalid', version=7)
        field = ReferralSettings._meta.get_field('gmail_password_encrypted')
        old_state = ProjectState.from_apps(apps)
        old_state.remove_field('assistance', 'referralsettings', field.name)
        migration = import_module('assistance.migrations.0006_referral_gmail_connection').Migration(
            '0006_referral_gmail_connection', 'assistance')
        try:
            with connection.schema_editor() as editor:
                editor.remove_field(ReferralSettings, field)
            with connection.schema_editor() as editor:
                migration.apply(old_state, editor)
            row = ReferralSettings.objects.get(pk=1)
            self.assertEqual((row.sender_email, row.version, row.gmail_password_encrypted),
                             ('migration@example.invalid', 7, ''))
        finally:
            with connection.cursor() as cursor:
                columns = connection.introspection.get_table_description(cursor, ReferralSettings._meta.db_table)
            if field.column not in {column.name for column in columns}:
                with connection.schema_editor() as editor:
                    editor.add_field(ReferralSettings, field)
