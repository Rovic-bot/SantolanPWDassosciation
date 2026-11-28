"""Rehearse the additive registration upgrade against retained fictional history."""
from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
from documents.models import MembershipApplicationDocument, DocumentVerification
from programs.models import ProgramApplication
from scripts.migration_test_support import migration_database, historical_apps


class ProfileMigrationTests(OperationalHelpers, TransactionTestCase):
    def test_old_fields_documents_classifications_and_calculations_survive_upgrade(self):
        self.setup_operational()
        self.lock_policy()
        self.choose(self.calculate())
        old = [('members', '0003_disabilitytype_member_disability_type'),
               ('membership', '0004_alter_membershipapplication_options_and_more'),
               ('documents', '0003_revised_seventy_workflow'),
               ('ewaf', '0008_operational_four'), ('auth', '0012_alter_user_first_name_max_length')]
        retained = (OperationalConfiguration, OperationalRun, OperationalDecision,
                    MembershipApplicationDocument, DocumentVerification, ProgramApplication)
        with migration_database(old) as database:
            historical = historical_apps(database, old)
            # Copy fictional history with historical fields, including foreign
            # keys. Check circular photo links after all rows have been inserted.
            copied = set()

            def copy_row(row):
                key = row._meta.label_lower, row.pk
                if key in copied:
                    return
                copied.add(key)
                Model = historical.get_model(row._meta.app_label, row._meta.model_name)
                values = {}
                for field in Model._meta.local_fields:
                    if not hasattr(row, field.attname):
                        continue
                    values[field.attname] = getattr(row, field.attname)
                    if field.many_to_one or field.one_to_one:
                        related = getattr(row, field.name)
                        if related is not None:
                            copy_row(related)
                Model.objects.using(database.alias).update_or_create(pk=row.pk, defaults=values)

            with transaction.atomic(using=database.alias), database.constraint_checks_disabled():
                for model in retained:
                    for row in model.objects.all():
                        copy_row(row)
                database.check_constraints()
            Member = historical.get_model('members', 'Member')
            Application = historical.get_model('membership', 'MembershipApplication')
            Requirement = historical.get_model('documents', 'MembershipDocumentRequirement')

            def records(registry):
                result = {}
                for model in retained:
                    OldModel = historical.get_model(model._meta.app_label, model._meta.model_name)
                    fields = [field.attname for field in OldModel._meta.local_fields]
                    Current = registry.get_model(model._meta.app_label, model._meta.model_name)
                    result[model._meta.label] = list(Current.objects.using(database.alias).order_by('pk').values(*fields))
                return result

            before_member = Member.objects.using(database.alias).values().get(pk=self.member.pk)
            before_intake = Application.objects.using(database.alias).values().get(pk=self.member.application_id)
            before_requirements = list(Requirement.objects.using(database.alias).order_by('pk').values())
            before_history = records(historical)
            self.assertIsNotNone(before_member['disability_type_id'])
            targets = [('membership', '0005_onsite_profile_capture'),
                       ('members', '0004_onsite_profile_capture'),
                       ('documents', '0004_onsite_profile_capture'),
                       ('ewaf', '0008_operational_four'), ('auth', '0012_alter_user_first_name_max_length')]
            MigrationExecutor(database).migrate(targets)
            updated_apps = historical_apps(database, targets)
            UpdatedMember = updated_apps.get_model('members', 'Member')
            UpdatedApplication = updated_apps.get_model('membership', 'MembershipApplication')
            UpdatedRequirement = updated_apps.get_model('documents', 'MembershipDocumentRequirement')
            for model, original in ((UpdatedMember, before_member), (UpdatedApplication, before_intake)):
                updated = model.objects.using(database.alias).values(*original).get(pk=original['id'])
                self.assertEqual(updated, original)
                row = model.objects.using(database.alias).get(pk=original['id'])
                self.assertEqual(list(row.disability_types.values_list('pk', flat=True)), [original['disability_type_id']])
                self.assertEqual(row.first_name, '')
                self.assertEqual(row.municipality, '')
                self.assertEqual(row.income_category, '')
            self.assertEqual(records(updated_apps), before_history)
            for original in before_requirements:
                self.assertEqual(UpdatedRequirement.objects.using(database.alias).values(*original).get(pk=original['id']), original)
            slots = UpdatedRequirement.objects.using(database.alias).filter(capture_key__isnull=False)
            self.assertEqual(slots.count(), 5)
            self.assertFalse(slots.filter(is_required=True).exists())
        for row in OperationalRun.objects.all():
            row.clean()
