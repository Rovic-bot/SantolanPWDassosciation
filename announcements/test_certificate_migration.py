from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from assistance.tests import create_application, seed_statuses
from programs.models import ProgramApplication
from scripts.durable_test_runner import require_disposable
from .certificate_models import SelectionCertificateEmail, SelectionCertificateAttempt


class CertificateMigrationTests(TransactionTestCase):
    def test_additive_tables_preserve_application_records(self):
        require_disposable()
        seed_statuses()
        application = create_application()
        before = ProgramApplication.objects.values().get(pk=application.pk)
        state = ProjectState.from_apps(apps)
        state.remove_model('announcements', 'selectioncertificateattempt')
        state.remove_model('announcements', 'selectioncertificateemail')
        migration = import_module('announcements.migrations.0006_selection_certificate_email').Migration(
            '0006_selection_certificate_email', 'announcements')
        self.assertEqual([type(operation).__name__ for operation in migration.operations],
                         ['CreateModel', 'CreateModel', 'AddConstraint', 'AddConstraint'])
        try:
            with connection.schema_editor() as editor:
                editor.delete_model(SelectionCertificateAttempt)
                editor.delete_model(SelectionCertificateEmail)
            with connection.schema_editor() as editor:
                migration.apply(state, editor)
            self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), before)
            self.assertFalse(SelectionCertificateEmail.objects.exists())
            self.assertFalse(SelectionCertificateAttempt.objects.exists())
        finally:
            for model in (SelectionCertificateEmail, SelectionCertificateAttempt):
                if model._meta.db_table not in connection.introspection.table_names():
                    with connection.schema_editor() as editor:
                        editor.create_model(model)
