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
        from assistance.testsupport import historical_receipt
        release = historical_receipt(other, self.officer)
        other.refresh_from_db()
        void_release(other.pk, release.pk, user=self.officer,
                     data={'version': other.version, 'confirm': True, 'notes': 'Synthetic historical void'})
        historical_receipt(other, self.officer)
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
        from scripts.migration_test_support import assert_additive_upgrade
        migration = MigrationExecutor(connection).loader.get_migration('ewaf', '0002_verified_evidence')
        self.assertTrue(all(type(op).__name__ in ('CreateModel', 'AddConstraint', 'AddIndex') for op in migration.operations))
        assert_additive_upgrade(self, [('ewaf', '0001_initial'), ('programs', '0005_approved_terms'),
            ('announcements', '0004_preserve_result_source_content')],
            [('ewaf', '0002_verified_evidence'), ('announcements', '0004_preserve_result_source_content')],
            ['ewaf.EvidencePolicyRevision', 'ewaf.CriterionAssessment', 'ewaf.EligibilityReadinessSnapshot'])
        self.assertEqual(list(Configuration.objects.get().pairwise), [[1] * 5 for _ in range(5)])
        from .calculation import CRITERIA
        self.assertEqual(CRITERIA, ('SI', 'ES', 'PA', 'ND', 'PR'))
        self.assertFalse(self.officer.groups.exists())
