"""Disposable database checks for a review-only shared policy draft."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.utils import timezone

from programs.models import Program, ProgramLog, ProgramTermsLock
from scripts.durable_test_runner import require_disposable
from .operational_models import OperationalConfiguration, OperationalRun
from .revised import policy, services
from .revised.models import RevisedPreviewRun
from .vault_models import VaultRevision


class RevisedPolicyIsolationTests(TransactionTestCase):
    def setUp(self):
        require_disposable()
        self.user = get_user_model().objects.create_superuser('synthetic-policy-review', password='synthetic-only')
        self.program = Program.objects.create(name='Synthetic retained program context',
            description='Fictional', assistance_type='Fictional', slots=1,
            registration_opens_at=timezone.now() - timedelta(days=2),
            registration_closes_at=timezone.now() - timedelta(days=1))
        ProgramTermsLock.objects.get_or_create(pk=1)

    def counts(self):
        return {model.__name__: model.objects.count() for model in
            (Program, ProgramLog, VaultRevision, OperationalConfiguration, OperationalRun, RevisedPreviewRun, LogEntry)}

    def test_draft_and_demonstration_create_no_approvals_or_operational_mutations(self):
        before = self.counts()
        program = Program.objects.filter(pk=self.program.pk).values().get()
        with patch('ewaf.vault_services.approve', side_effect=AssertionError('Do not reapprove weights')), \
                patch('ewaf.vault_services.record', side_effect=AssertionError('Do not manufacture approvals')), \
                patch('ewaf.operational_services.record_configuration', side_effect=AssertionError('Do not activate scoring')):
            draft = policy.load_draft()
            policy.demonstrate(draft)
            policy.revise_proposal(draft, expected_digest=draft.digest, name='si_rubric',
                description='Synthetic review proposal only.')
        self.assertEqual(self.counts(), before)
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), program)

    def test_official_readiness_requires_approved_program_binding_and_keeps_prior_guards(self):
        before = self.counts()
        blockers = services.official_readiness(self.program)
        codes = {item['code'] for item in blockers}
        self.assertTrue({code for code, _ in services.BLOCKERS} <= codes)
        self.assertIn('PROGRAM_POLICY_BINDING', codes)
        with self.assertRaisesMessage(ValidationError, 'PROGRAM_POLICY_BINDING'):
            services.require_official_ready(self.program)
        self.assertEqual(self.counts(), before)

    def test_draft_revision_preserves_existing_program_and_retained_calculation(self):
        run = services.retain(self.program.pk, user=self.user, expected=services.token(self.program),
            request_key=uuid4(), reason='Retained synthetic baseline before policy review.')
        snapshot, current_token, before = run.payload(), services.token(self.program), self.counts()
        draft = policy.load_draft()
        revised = policy.revise_proposal(draft, expected_digest=draft.digest, name='pa_scope',
            description='Synthetic proposed revised scope; no adoption.')
        demonstration = policy.demonstrate(revised)
        self.assertEqual(demonstration.data['policy_reference']['revision'], 2)
        run.refresh_from_db()
        run.clean()
        self.assertEqual(run.payload(), snapshot)
        self.assertEqual(services.token(self.program), current_token)
        self.assertEqual(self.counts(), before)
