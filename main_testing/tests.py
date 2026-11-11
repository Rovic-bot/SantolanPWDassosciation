from copy import deepcopy
import tempfile
from importlib import import_module
from django.apps import apps
from django.db import connection
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.core.exceptions import ValidationError
from membership.models import MembershipSettings, MembershipApplication
from members.models import DisabilityType
from members.disability_catalog import NAMES
from .seed import Builder


class TestingDatasetTests(TransactionTestCase):
    def test_synthetic_services_create_verified_pool_and_real_weight_revision(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            actor = get_user_model().objects.create_superuser('fictional_lab_builder')
            MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://example.invalid/simulation'})
            # TransactionTestCase flushes reference rows left by data migrations.
            with connection.schema_editor() as editor:
                import_module('documents.migrations.0004_onsite_profile_capture').capture_slots(apps, editor)
            from assistance.models import EligibilityStatus
            for code, label in [('pending', 'Pending'), ('eligible', 'Eligible'), ('review', 'Needs Information'), ('ineligible', 'Ineligible')]:
                EligibilityStatus.objects.get_or_create(code=code, defaults={'label': label})
            for name in NAMES:
                DisabilityType.objects.get_or_create(name=name)
            builder = Builder(actor)
            builder.register_members(count=6, pending=2)
            self.assertEqual(MembershipApplication.objects.filter(status='pending').count(), 2)
            program = builder.make_program('EWAF Lab — Service regression', slots=3)
            for member in builder.members:
                builder.apply(program, member)
            config = builder.configure(program, 'SI')
            for app in builder.applications[str(program.pk)]:
                builder.assess(app)
            run = builder.calculate(program)
            before = deepcopy(run.payload())
            from ewaf import operational_services as service
            from ewaf.weight_input import project
            policy = deepcopy(config.policy)
            judgments, _, provenance = project(builder.proposal('ND'))
            policy['weight_input'] = provenance
            service.record_configuration(program.pk, user=actor, expected=service.configuration_token(program),
                proposed=policy, judgments=judgments, status='LOCKED', reason='Fictional experiment', attested=True)
            with self.assertRaises(ValidationError):
                with service.fence(program.pk, actor) as (user, current, applications):
                    service._current(current, applications, user, run.pk)
            revised = builder.calculate(program)
            run.refresh_from_db()
            self.assertEqual(run.payload(), before)
            self.assertEqual(revised.previous_id, run.pk)
            self.assertNotEqual(service.ordered(run)[0]['application'], service.ordered(revised)[0]['application'])
            builder.observances()
