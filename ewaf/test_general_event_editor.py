"""The simple event editor retains historical program links and source audits."""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

from accounts import authority_services
from events.models import Event
from events.services import save_event
from events.tests import event_data
from programs.models import Program
from .test_source_writers import SourceHelpers


class GeneralEventEditorAuditTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        Program.objects.filter(pk=self.program.pk).update(status='draft', published_at=None)
        self.program.refresh_from_db()
        self.event = save_event(user=self.officer, data=event_data())
        # Seed a historical link before registering disposable source authority.
        # The current editor never creates, clears, or replaces this hidden link.
        Event.objects.filter(pk=self.event.pk).update(application_program=self.program,
            event_category='specific', capacity=50, target_audience='Historical audience')
        self.event.refresh_from_db()
        self.bootstrap()
        authority = authority_services._disposable_authority_session(user=self.officer)
        authority.__enter__()
        self.addCleanup(authority.__exit__, None, None, None)

    def save(self):
        return save_event(user=self.officer, pk=self.event.pk, source_expected=self.expected(),
            data=event_data(version=self.event.version, title='Revised community event', notes='',
                application_program='', event_category='general', capacity=1, target_audience='Ignored'))

    def test_generated_edit_note_is_audited_and_hidden_history_is_preserved(self):
        item = self.save()
        self.assertEqual(item.application_program_id, self.program.pk)
        self.assertEqual((item.event_category, item.capacity, item.target_audience),
                         ('specific', 50, 'Historical audience'))
        self.assertEqual(item.history.first().notes, 'Event updated from the event editor.')
        self.assert_transition(2)

    def test_audit_failure_rolls_back_the_visible_edit_and_source_generation(self):
        before = Event.objects.values().get(pk=self.event.pk)
        with patch('events.services.record_log', side_effect=ValidationError('Synthetic unavailable audit')):
            with self.assertRaises(ValidationError):
                self.save()
        self.assertEqual(Event.objects.values().get(pk=self.event.pk), before)
        self.assertEqual(self.event.history.count(), 1)
        self.assert_transition(1)
