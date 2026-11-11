"""Exact additive outcome migration rehearsal on disposable native MySQL."""
from importlib import import_module

from django.apps import apps
from django.db import connection, models
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase, override_settings

from scripts.durable_test_runner import require_disposable
from .approval_email_models import approval_email_write
from .pdao_email_models import PDAOReviewEmail as Email, PDAOReviewEmailAttempt as Attempt
from .pdao_models import PDAORegistration, PDAORegistrationEvent
from .test_pdao_claim_email import ClaimHelpers


def previous_state():
    state = ProjectState.from_apps(apps)
    email = state.models['membership', 'pdaoreviewemail']
    email.fields['outcome'].choices = [('ready', 'Office verification invitation'), ('needs_info', 'Information request')]
    email.options['constraints'] = [models.CheckConstraint(
        condition=models.Q(outcome__in=['ready', 'needs_info']), name='pdao_review_email_outcome')
        if item.name == 'pdao_review_email_outcome' else item for item in email.options['constraints']]
    event = state.models['membership', 'pdaoregistrationevent']
    event.fields['action'].choices = [(value, label) for value, label in event.fields['action'].choices if value != 'claim_notice_queued']
    state.reload_model('membership', 'pdaoreviewemail')
    state.reload_model('membership', 'pdaoregistrationevent')
    return state


@override_settings(PDAO_REGISTRATION_ENABLED=True, PDAO_CLAIM_EMAIL_BACKGROUND=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDAOClaimMigrationTests(ClaimHelpers, TransactionTestCase):
    def test_preserves_existing_applicants_notices_attempts_and_events(self):
        require_disposable()
        self.setup_claims()
        item = self.record()
        with approval_email_write():
            job = Email.objects.create(registration=item, expected_version=1, outcome='ready',
                recipient=item.data['email'], sender='association@example.invalid',
                subject='Saved invitation', body='Preserve this prior message.', requested_by=self.staff,
                requested_by_label=self.staff.username, state='failed', attempt_count=1)
            Attempt.objects.create(email=job, number=1, outcome='failed', error_type='SyntheticFailure')
        models_to_preserve = (PDAORegistration, Email, Attempt, PDAORegistrationEvent)
        before = {model._meta.label: list(model.objects.order_by('pk').values()) for model in models_to_preserve}
        old_state = previous_state()
        old_model = old_state.apps.get_model('membership', 'PDAOReviewEmail')
        current_constraint = next(item for item in Email._meta.constraints if item.name == 'pdao_review_email_outcome')
        old_constraint = next(item for item in old_model._meta.constraints if item.name == 'pdao_review_email_outcome')
        with connection.schema_editor() as editor:
            editor.remove_constraint(Email, current_constraint)
            editor.add_constraint(old_model, old_constraint)
        migration = import_module('membership.migrations.0015_pdao_claim_notices').Migration('0015_pdao_claim_notices', 'membership')
        with connection.schema_editor() as editor:
            migration.apply(old_state, editor)
        after = {model._meta.label: list(model.objects.order_by('pk').values()) for model in models_to_preserve}
        self.assertEqual(before, after)
        self.request_claims(item)
        self.assertEqual(Email.objects.filter(outcome='claim_ready').count(), 1)
        job.refresh_from_db()
        self.assertEqual((job.body, job.state, job.attempt_count), ('Preserve this prior message.', 'failed', 1))
