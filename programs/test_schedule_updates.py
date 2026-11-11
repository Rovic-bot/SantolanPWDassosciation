from copy import deepcopy
from datetime import timedelta
from html.parser import HTMLParser
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from documents.models import DocumentType
from members.tests import create_member
from membership.tests import grant
from ewaf import vault_services
from ewaf.dataset_methods import COMPOSITE
from ewaf.operational_models import OperationalConfiguration
from ewaf.operational_services import configuration_token
from ewaf.revised import contracts, live_services
from ewaf.test_composite_ses import proposal
from .forms import ProgramSetupForm
from .models import Program, ProgramApplication, ProgramLog
from .services import save_program, change_publication
from .terms import snapshot_terms
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
    EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True, EWAF_VAULT_ENABLED=True)
class ScheduleUpdateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('synthetic-schedule-admin')
        self.program = create_program(ewaf_applicable=True, policy_authorized_by=self.user,
            benefit='Synthetic schedule support.', ends_at=timezone.now() + timedelta(days=10))
        Program.objects.filter(pk=self.program.pk).update(status='draft', published_at=None)
        self.program.refresh_from_db()
        document = DocumentType.objects.create(name='Synthetic schedule assessment')
        for status in ('DRAFT', 'LOCKED'):
            weights = vault_services.record_ses_weights(user=self.user, expected=vault_services.token(),
                proposal=proposal(), method=COMPOSITE, status=status, reason='SYNTHETIC schedule test weights')
        content = contracts.initial_content(COMPOSITE)
        for key, (_, _, kind) in contracts.specifications(content).items():
            if isinstance(kind, dict):
                value = next(iter(kind))
            elif kind == 'documents':
                value = [document.pk]
            elif kind == 'integer':
                value = 90 if key == 'evidence_max_age_days' else 12 if key == 'pa_months' else 3
            elif kind == 'datetime':
                value = (timezone.now() + timedelta(days=-30 if key == 'effective_from' else 30)).isoformat()
            else:
                value = 'SYNTHETIC test procedure; not Association operating policy.'
            content['choices'][key] = {'value': value, 'specified': True}
        draft = live_services.save_draft(user=self.user, expected=live_services.token(), content=content,
            weight_id=weights.pk, reason='SYNTHETIC schedule policy draft')
        self.policy = live_services.approve(draft.pk, user=self.user, expected=draft.digest,
            reviewed_groups=['A', 'B', 'C'], reason='SYNTHETIC schedule policy approval')
        self.configuration = live_services.bind(self.program.pk, user=self.user,
            expected=configuration_token(self.program), policy_id=self.policy.pk,
            cutoff=self.program.registration_closes_at, reason='SYNTHETIC closing-time cutoff')
        change_publication(self.program.pk, user=self.user, version=self.program.version,
            action='published', notes='Synthetic published schedule.')
        self.program.refresh_from_db()
        self.application = ProgramApplication.objects.create(program=self.program,
            member=create_member('SYNTHETIC-SCHEDULE'), public_reference='SYNTHETIC-SCHEDULE-APPLICATION',
            status='ELIGIBLE', program_snapshot=snapshot_terms(self.program)['program'])
        self.url = reverse('programs:edit', args=[self.program.pk])
        self.client.force_login(self.user)

    def data(self, **changes):
        form = ProgramSetupForm(instance=Program.objects.get(pk=self.program.pk))
        values = {name: form.initial.get(name, '') for name in form.fields}
        return {key: '' if value is None else value for key, value in values.items()} | {
            'notes': 'Authorized synthetic date correction.', **changes}

    def save(self, **changes):
        return save_program(pk=self.program.pk, user=self.user, data=self.data(**changes), setup_only=True)

    def test_date_update_preserves_application_and_appends_same_policy_with_following_cutoff(self):
        application = ProgramApplication.objects.values().get(pk=self.application.pk)
        retained = deepcopy(self.configuration.payload())
        close = self.program.registration_closes_at + timedelta(hours=2)
        result = self.save(registration_closes_at=close)
        self.assertEqual(result.registration_closes_at, close)
        self.assertEqual(result.version, self.program.version + 1)
        self.assertEqual(ProgramApplication.objects.values().get(pk=self.application.pk), application)
        self.configuration.refresh_from_db()
        self.assertEqual(self.configuration.payload(), retained)
        current = OperationalConfiguration.objects.filter(program=result).first()
        self.assertEqual(current.previous_id, self.configuration.pk)
        self.assertEqual(current.dataset_policy_id, self.policy.pk)
        self.assertEqual(current.assessment_cutoff, close)
        live_services.require_binding(current)
        self.assertEqual(ProgramLog.objects.filter(program=result, action='updated').count(), 1)

    def test_program_dates_change_without_moving_registration_cutoff(self):
        cutoff = self.configuration.assessment_cutoff
        result = self.save(starts_at=timezone.now(), ends_at=timezone.now() + timedelta(days=12))
        current = OperationalConfiguration.objects.filter(program=result).first()
        self.assertEqual(current.assessment_cutoff, cutoff)
        live_services.require_binding(current)

    def test_existing_submissions_must_remain_inside_registration_dates(self):
        for changes, field in (({'registration_closes_at': self.application.submitted_at - timedelta(minutes=1)}, 'registration_closes_at'),
                ({'registration_opens_at': self.application.submitted_at + timedelta(minutes=1)}, 'registration_opens_at')):
            form = ProgramSetupForm(self.data(**changes), instance=self.program)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
            with self.assertRaises(ValidationError):
                self.save(**changes)

    def test_date_error_and_earliest_valid_time_appear_above_the_enhanced_calendar(self):
        latest = self.application.submitted_at.replace(second=5, microsecond=123)
        ProgramApplication.objects.filter(pk=self.application.pk).update(submitted_at=latest)
        earliest = latest.replace(second=0, microsecond=0) + timedelta(minutes=1)
        response = self.client.post(self.url, self.data(registration_closes_at=latest - timedelta(minutes=1)),
            HTTP_X_PROGRAM_BUILDER='1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-saved="false"')

        class SummaryText(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth = 0
                self.parts = []
            def handle_starttag(self, tag, attrs):
                if tag == 'div':
                    if self.depth or 'data-validation-content' in dict(attrs):
                        self.depth += 1
            def handle_endtag(self, tag):
                if tag == 'div' and self.depth:
                    self.depth -= 1
            def handle_data(self, data):
                if self.depth:
                    self.parts.append(data)

        parser = SummaryText()
        parser.feed(response.content.decode())
        summary = ''.join(parser.parts)
        from django.utils.formats import date_format
        self.assertIn('Registration cannot close before an existing application', summary)
        self.assertIn(date_format(timezone.localtime(earliest), 'M j, Y, g:i A'), summary)
        self.assertContains(response, 'href="#setup-schedule" data-error-field="registration_closes_at"')
        self.program.refresh_from_db()
        self.assertGreater(self.program.registration_closes_at, latest)

    def test_other_terms_and_direct_model_form_saves_remain_protected(self):
        result = self.save(name='Corrected program title')
        self.assertEqual(result.name, 'Corrected program title')
        current = OperationalConfiguration.objects.filter(program=result).first()
        self.assertEqual(current.dataset_policy_id, self.policy.pk)
        live_services.require_binding(current)
        self.program.refresh_from_db()
        form = ProgramSetupForm(self.data(registration_closes_at=self.program.registration_closes_at + timedelta(hours=1)),
            instance=self.program)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaisesMessage(ValidationError, 'protected'):
            form.save()

    def test_stale_edit_and_failed_audit_leave_dates_and_configuration_unchanged(self):
        values = self.data(registration_closes_at=self.program.registration_closes_at + timedelta(hours=1))
        before = Program.objects.values().get(pk=self.program.pk)
        configurations = list(OperationalConfiguration.objects.filter(program=self.program).values())
        with patch('programs.services.record_log', side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                save_program(pk=self.program.pk, user=self.user, data=values, setup_only=True)
        self.assertEqual(Program.objects.values().get(pk=self.program.pk), before)
        self.assertEqual(list(OperationalConfiguration.objects.filter(program=self.program).values()), configurations)
        self.save(starts_at=timezone.now())
        with self.assertRaisesMessage(ValidationError, 'changed'):
            save_program(pk=self.program.pk, user=self.user, data=values, setup_only=True)

    def test_final_outcomes_and_external_approval_mode_remain_protected(self):
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True), self.assertRaisesMessage(ValidationError, 'external approval'):
            self.save(starts_at=timezone.now())
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='COMPLETED')
        with self.assertRaisesMessage(ValidationError, 'final outcome'):
            self.save(starts_at=timezone.now())

    def test_expired_policy_date_is_not_accepted(self):
        far = timezone.now() + timedelta(days=40)
        with self.assertRaisesMessage(ValidationError, 'policy period'):
            self.save(registration_closes_at=far, ends_at=far + timedelta(days=2))

    def test_real_edit_endpoint_requires_permission_and_csrf(self):
        values = self.data(starts_at=timezone.now())
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.post(self.url, values).status_code, 403)
        editor = get_user_model().objects.create_user('synthetic-dates-editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'programs.view_program', 'programs.change_program')
        self.client.force_login(editor)
        self.assertEqual(self.client.post(self.url, values).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url, values).status_code, 302)

    def test_fixed_cutoff_stays_fixed_and_rejects_later_registration_close(self):
        cutoff = self.program.registration_closes_at + timedelta(hours=3)
        from django.db import transaction
        from .terms import terms_lock
        with terms_lock(), transaction.atomic():
            previous = OperationalConfiguration.objects.filter(program=self.program).first()
            live_services.store_binding(self.program, previous, self.policy, cutoff, user=self.user,
                reason='Synthetic separately scheduled assessment cutoff.')
        result = self.save(registration_closes_at=self.program.registration_closes_at + timedelta(hours=1))
        current = OperationalConfiguration.objects.filter(program=result).first()
        self.assertEqual(current.assessment_cutoff, cutoff)
        with self.assertRaisesMessage(ValidationError, 'separately approved assessment cutoff'):
            self.save(registration_closes_at=cutoff + timedelta(hours=1))

    def test_published_non_scored_program_dates_can_be_updated(self):
        self.program = create_program(ewaf_applicable=False, policy_authorized_by=self.user,
            benefit='Synthetic non-scored support.')
        result = self.save(starts_at=timezone.now())
        self.assertEqual(result.version, self.program.version + 1)
        self.assertFalse(OperationalConfiguration.objects.filter(program=result).exists())

    def test_published_weights_only_program_retains_exact_weight_version(self):
        from ewaf.intake_policy import require_configuration
        self.program = create_program(ewaf_applicable=True, policy_authorized_by=self.user,
            benefit='Synthetic weights-only support.')
        Program.objects.filter(pk=self.program.pk).update(status='draft', published_at=None)
        self.program.refresh_from_db()
        change_publication(self.program.pk, user=self.user, version=self.program.version,
            action='published', notes='Synthetic weights-only publication.')
        self.program.refresh_from_db()
        previous = require_configuration(self.program)
        result = self.save(starts_at=timezone.now())
        current = require_configuration(result)
        self.assertEqual(current.previous_id, previous.pk)
        self.assertEqual(current.vault_revision_id, previous.vault_revision_id)
        self.assertEqual(current.policy, previous.policy)
