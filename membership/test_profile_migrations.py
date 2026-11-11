"""Rehearse the additive registration upgrade against retained fictional history."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
from documents.models import MembershipApplicationDocument, DocumentVerification
from programs.models import ProgramApplication


class ProfileMigrationTests(OperationalHelpers, TransactionTestCase):
    def test_old_fields_documents_classifications_and_calculations_survive_upgrade(self):
        from scripts.durable_test_runner import require_disposable
        self.setup_operational()
        require_disposable()
        self.lock_policy()
        self.choose(self.calculate())
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        old = [('members', '0003_disabilitytype_member_disability_type'),
               ('membership', '0004_alter_membershipapplication_options_and_more'),
               ('documents', '0003_revised_seventy_workflow')]
        retained = (OperationalConfiguration, OperationalRun, OperationalDecision,
                    MembershipApplicationDocument, DocumentVerification, ProgramApplication)
        def records():
            return {model._meta.label: list(model.objects.order_by('pk').values()) for model in retained}
        try:
            MigrationExecutor(connection).migrate(old)
            historical = MigrationExecutor(connection).loader.project_state(old).apps
            Member = historical.get_model('members', 'Member')
            Application = historical.get_model('membership', 'MembershipApplication')
            Requirement = historical.get_model('documents', 'MembershipDocumentRequirement')
            before_member = Member.objects.values().get(pk=self.member.pk)
            before_intake = Application.objects.values().get(pk=self.member.application_id)
            before_requirements = list(Requirement.objects.order_by('pk').values())
            before_history = records()
            self.assertIsNotNone(before_member['disability_type_id'])
            MigrationExecutor(connection).migrate(leaves)
            from members.models import Member as UpdatedMember
            from membership.models import MembershipApplication
            from documents.models import MembershipDocumentRequirement
            for model, original in ((UpdatedMember, before_member), (MembershipApplication, before_intake)):
                updated = model.objects.values(*original).get(pk=original['id'])
                self.assertEqual(updated, original)
                row = model.objects.get(pk=original['id'])
                self.assertEqual(list(row.disability_types.values_list('pk', flat=True)), [original['disability_type_id']])
                self.assertEqual(row.first_name, '')
                self.assertEqual(row.municipality, '')
                self.assertEqual(row.income_category, '')
            self.assertEqual(records(), before_history)
            for original in before_requirements:
                self.assertEqual(MembershipDocumentRequirement.objects.values(*original).get(pk=original['id']), original)
            self.assertEqual(MembershipDocumentRequirement.objects.filter(capture_key__isnull=False).count(), 5)
            self.assertFalse(MembershipDocumentRequirement.objects.filter(capture_key__isnull=False, is_required=True).exists())
            for row in OperationalRun.objects.all():
                row.clean()
        finally:
            MigrationExecutor(connection).migrate(leaves)
