"""Rehearse the exact PDAO schema change on disposable native MySQL."""
from importlib import import_module

from django.apps import apps
from django.db import connection, models
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase, override_settings

from scripts.durable_test_runner import require_disposable
from .pdao_email_models import PDAOReviewEmail, PDAOReviewEmailAttempt
from .pdao_models import PDAORegistration, PDAORegistrationEvent
from .test_pdao_registration import PDAOHelpers


def previous_state():
    state = ProjectState.from_apps(apps)
    state.remove_model('membership', 'pdaoreviewemailattempt')
    state.remove_model('membership', 'pdaoreviewemail')
    state.remove_field('membership', 'pdaoregistrationevent', 'details')
    model = state.models['membership', 'pdaoregistration']
    model.options['constraints'] = [models.CheckConstraint(
        condition=models.Q(status__in=['received', 'ready', 'forwarded']), name='pdao_registration_status')]
    state.reload_model('membership', 'pdaoregistration')
    return state


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAOReviewMigrationTests(PDAOHelpers, TransactionTestCase):
    def test_preserves_originals_events_and_references(self):
        require_disposable()
        item, _ = self.submit()
        before = PDAORegistration.objects.values().get(pk=item.pk)
        event_fields = [field.name for field in PDAORegistrationEvent._meta.fields if field.name != 'details']
        events = list(item.events.values(*event_fields))
        old_state = previous_state()
        old_model = old_state.apps.get_model('membership', 'PDAORegistration')
        migration = import_module('membership.migrations.0014_pdao_review_notices').Migration('0014_pdao_review_notices', 'membership')
        with connection.schema_editor() as editor:
            editor.delete_model(PDAOReviewEmailAttempt)
            editor.delete_model(PDAOReviewEmail)
            editor.remove_field(PDAORegistrationEvent, PDAORegistrationEvent._meta.get_field('details'))
            editor.remove_constraint(PDAORegistration, PDAORegistration._meta.constraints[0])
            editor.add_constraint(old_model, old_model._meta.constraints[0])
        with connection.schema_editor() as editor:
            migration.apply(old_state, editor)
        self.assertEqual(PDAORegistration.objects.values().get(pk=item.pk), before)
        self.assertEqual(list(item.events.values(*event_fields)), events)
        self.assertEqual(item.events.get().details, {})
        self.assertFalse(PDAOReviewEmail.objects.exists())
        self.assertFalse(PDAOReviewEmailAttempt.objects.exists())
