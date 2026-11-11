"""Owner-confirmed scores, real generation, immutable history and stale guards."""
from copy import deepcopy
from fractions import Fraction
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from . import employment_scoring as employment, operational_services as service
from .revised import live_math
from .test_rolling_pool import RollingPoolTests as Fixture


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class EmploymentScoringTests(TransactionTestCase):
    draft = Fixture.draft
    approve = Fixture.approve
    bind = Fixture.bind
    publish = Fixture.publish
    applicant = Fixture.applicant
    generate = Fixture.generate

    def setUp(self):
        # Exercise retained shared-policy programs from before fixed code rules.
        # New programs receive their fixed binding during policy authorization.
        with patch('ewaf.fixed_scoring.bind', return_value=None):
            Fixture.setUp(self)

    def test_all_five_categories_use_exact_scores_and_normalized_weighted_contributions(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            applications = [self.applicant(f'ES-FIVE-{i}', employment_status=key)
                            for i, key in enumerate(employment.MAPPING)]
            original = deepcopy(self.configuration.payload())
            run = self.generate()
            run.clean()
            for i, app in enumerate(applications):
                result = run.calculations[str(app.pk)]
                trace = next(row for row in result['traces'] if row['criterion'] == 'ES')
                self.assertEqual(Fraction(trace['input']['exact']), i + 1)
                self.assertEqual(Fraction(trace['normalized']['exact']), Fraction(i, 4))
                self.assertEqual(Fraction(trace['contribution']['exact']), Fraction(i, 4) * Fraction(trace['weight']))
                self.assertEqual(result['comparison']['business_rank'], 5-i)
            self.configuration.refresh_from_db()
            self.assertEqual(self.configuration.payload(), original)
            self.assertEqual(employment.encoding(run.snapshot), employment.SCORES)
            bad = deepcopy(run.snapshot)
            bad[employment.KEY]['scores']['Student'] = 5
            with self.assertRaisesMessage(ValidationError, 'exact version'):
                live_math.calculations(bad, run.configuration)
            page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
            self.assertContains(page, 'Self-Employed')
            self.assertContains(page, 'Student')
            self.assertContains(page, 'Retired')
            self.assertContains(page, 'Unemployed')

    def test_legacy_replay_unchanged_and_old_token_and_decisions_require_new_generation(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            a = self.applicant('ES-OLD-A', low=True)
            self.applicant('ES-OLD-B')
            with patch('ewaf.employment_scoring.capture', return_value={}):
                old = self.generate()
                token = service.context(self.program.pk, user=self.user)
            saved = deepcopy(old.payload())
            old.clean()
            self.assertEqual(employment.encoding(old.snapshot)['Unemployed'], 4)
            with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
                service.generate(self.program.pk, user=self.user, expected=token,
                    reason='Synthetic stale employment rule', request_key=uuid4())
            with service.fence(self.program.pk, self.user) as (actor, program, applications):
                with self.assertRaisesMessage(ValidationError, 'Employment scoring changed'):
                    service.current_result_run(program, applications, actor, old.pk)
            new = self.generate()
            new.clean(); old.refresh_from_db(); old.clean()
            self.assertEqual(old.payload(), saved)
            self.assertEqual(new.previous_id, old.pk)
            trace = next(row for row in new.calculations[str(a.pk)]['traces'] if row['criterion']=='ES')
            self.assertEqual(trace['input']['exact'], '5')

    def test_new_policy_form_fixes_each_recorded_category_and_unknown_still_blocks(self):
        from .revised.live_forms import PolicyDraftForm
        form = PolicyDraftForm(content=self.content)
        for key, label in employment.MAPPING.items():
            field = form.fields['employment_map_'+key]
            self.assertTrue(field.disabled)
            self.assertEqual(field.initial, label)
            self.assertEqual(field.choices, [(label, f'{label} = {employment.SCORES[label]}')])
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            self.applicant('ES-UNKNOWN', employment_status='unknown')
            with self.assertRaisesMessage(ValidationError, 'no assigned scoring category'):
                service.context(self.program.pk, user=self.user)

    def test_permission_and_audit_rollback_are_preserved(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import PermissionDenied
        from membership.tests import grant
        from .operational_models import OperationalRun
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            self.applicant('ES-AUDIT', employment_status='retired')
            limited = get_user_model().objects.create_user('ES-VIEWER', is_staff=True)
            grant(limited, 'accounts.access_dashboard', *service.VIEW)
            expected = service.context(self.program.pk, user=self.user)
            with self.assertRaises(PermissionDenied):
                service.generate(self.program.pk, user=limited, expected=expected,
                    request_key=uuid4(), reason='Synthetic permission check')
            with patch('programs.models.ProgramLog.objects.create', side_effect=RuntimeError('audit unavailable')):
                with self.assertRaises(RuntimeError):
                    self.generate()
            self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())

    def test_manual_review_form_and_evidence_accept_all_five_categories(self):
        from .revised.live_forms import InputReviewForm
        from .revised import live_evidence as evidence
        from .test_member_record_evidence import MemberRecordEvidenceTests as Reviewed
        self.content = deepcopy(self.document_content)
        self.publish()
        app = self.applicant('ES-MANUAL')
        form = InputReviewForm(application=app, configuration=self.configuration)
        self.assertEqual([value for value, _ in form.fields['employment'].choices if value], list(employment.SCORES))
        for label in employment.SCORES:
            values = Reviewed.findings(self, employment=label)
            inputs = evidence.derive_inputs(values, self.configuration, evidence.context(app))
            self.assertEqual(inputs['ES']['value'], label)
