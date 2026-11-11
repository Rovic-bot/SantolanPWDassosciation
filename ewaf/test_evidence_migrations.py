"""Additive schema and complete synthetic business-row preservation."""
from decimal import Decimal
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from assistance.services import review_eligibility, decide_assistance, record_release, void_release
from assistance.tests import review_data, decision_data, release_data
from announcements.models import Announcement, ProgramResultRevision
from programs.test_approved_terms import TermsHelpers
from programs.tests import create_program
from programs.testsupport import application_fixture
from .evidence_testsupport import EvidenceHelpers
from .models import Configuration, ApplicationInput, RankingRun, Snapshot, CriterionAssessment, EvidencePolicyRevision, EligibilityReadinessSnapshot
from .testsupport import test_configuration


class EvidencePreservationTests(EvidenceHelpers, TermsHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_evidence()
        self.reconcile()
        self.configuration = test_configuration()
        ApplicationInput.objects.create(application=self.application, relevance='Historical raw relevance',
                                        socioeconomic=Decimal('321.1234'), updated_by=self.officer)
        run = RankingRun.objects.create(program=self.program, configuration=self.configuration, created_by=self.officer)
        Snapshot.objects.create(run=run, application=self.application,
            raw={'SI': '100', 'ES': 'Historical', 'PA': 0, 'ND': 0, 'PR': 'Historical'},
            encoded={'SI': '100', 'ES': 1, 'PA': 0, 'ND': 0, 'PR': 1}, normalized={'SI': '0.25'},
            weights={'SI': '.4037', 'ES': '.2483', 'PA': '.1680', 'ND': '.0635', 'PR': '.1165'},
            consistency={'CR': '0.01'}, score=Decimal('0.12345678901234567890'),
            classification='Historical class', rank=1, context={'historical': True})
        other_program = create_program(registration_closes_at=timezone.now() - timezone.timedelta(minutes=1))
        other = application_fixture(other_program, self.member)
        review_eligibility(other.pk, user=self.officer, data=review_data(other))
        decide_assistance(other.pk, user=self.officer, data=decision_data(other))
        release = record_release(other.pk, user=self.officer, data=release_data(other))
        other.refresh_from_db()
        void_release(other.pk, release.pk, user=self.officer,
                     data={'version': other.version, 'confirm': True, 'notes': 'Synthetic historical void'})
        review_eligibility(other.pk, user=self.officer, data=review_data(other))
        decide_assistance(other.pk, user=self.officer, data=decision_data(other))
        record_release(other.pk, user=self.officer, data=release_data(other))
        announcement = Announcement.objects.create(title='Synthetic retained result', content='Synthetic result text',
            status='published', published_at=timezone.now(), program=other_program)
        revision = ProgramResultRevision.objects.create(announcement=announcement, number=1,
            public_payload={'synthetic': 'retained'}, source_digest='a' * 64, reason='Synthetic historical revision',
            created_by=self.officer, creator_label=self.officer.username)
        announcement.result_revision = revision
        announcement.save()

    def business_rows(self):
        result = {}
        for model in apps.get_models():
            if model._meta.app_label not in {'membership', 'members', 'documents', 'programs', 'assistance', 'announcements', 'ewaf', 'events'}:
                continue
            if model in (CriterionAssessment, EvidencePolicyRevision, EligibilityReadinessSnapshot):
                continue
            rows = model.objects.order_by('pk')
            if model._meta.label_lower == 'programs.programlog':
                rows = rows.exclude(action__startswith='g12_')
            result[model._meta.label_lower] = list(rows.values())
        return result

    def test_evidence_operations_preserve_complete_existing_business_rows(self):
        before = self.business_rows()
        self.policy = self.policy_record()
        self.assess()
        from .evidence_services import record_readiness
        from .readiness import assess_readiness
        diagnostic = assess_readiness(self.application.pk, user=self.officer)
        record_readiness(self.application.pk, user=self.officer, expected_context=diagnostic['context_digest'],
            expected_assessments={row['criterion']: row['assessment'] for row in diagnostic['criteria']},
            reason='Synthetic preserved diagnostic', confirmed=True)
        self.assertEqual(self.business_rows(), before)

    def test_additive_migration_preserves_all_business_rows_without_verification_backfill(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        before = self.business_rows()
        try:
            executor.migrate([('ewaf', '0001_initial')])
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration('ewaf', '0002_verified_evidence')
            self.assertTrue(all(operation.__class__.__name__ in ('CreateModel', 'AddConstraint', 'AddIndex') for operation in migration.operations))
            executor.migrate(leaves)
            self.assertEqual(self.business_rows(), before)
            for model in (EvidencePolicyRevision, CriterionAssessment, EligibilityReadinessSnapshot):
                self.assertEqual(model.objects.count(), 0)
            self.assertEqual(list(Configuration.objects.get().pairwise), [[1] * 5 for _ in range(5)])
            from .calculation import CRITERIA
            self.assertEqual(CRITERIA, ('SI', 'ES', 'PA', 'ND', 'PR'))
            self.assertFalse(self.officer.groups.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
