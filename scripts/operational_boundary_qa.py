"""Actual 2,000/2,001-row inventory boundary; never a throughput/eligibility claim."""
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TransactionTestCase
from django.urls import reverse
from members.tests import create_member
from programs.models import Program, ProgramApplication
from programs.workflow import allocate_reference
from ewaf.operational_testsupport import OperationalHelpers
from ewaf import operational_services as service
from ewaf.operational_policy import MAX_POOL
from ewaf.operational_models import OperationalRun


class OperationalBoundaryTests(OperationalHelpers, TransactionTestCase):
    def test_actual_engineering_boundary_keeps_full_inventory_and_blocks_incomplete_pool(self):
        self.setup_operational()
        self.lock_policy()
        self.assertEqual(MAX_POOL, 2000)
        # These are explicit unresolved capacity fixtures. They have no invented
        # verification findings or scores. References use the existing allocator.
        with transaction.atomic(), patch('django.utils.timezone.now', return_value=self.fixture_time):
            program = Program.objects.select_for_update().get(pk=self.program.pk)
            for index in range(1, MAX_POOL):
                member = create_member(f'FICTIONAL-LIMIT-{index:04d}')
                ProgramApplication.objects.create(program=program, member=member,
                    public_reference=allocate_reference(program))
        with service.fence(self.program.pk, self.officer) as (actor, program, applications):
            self.assertEqual(len(applications), MAX_POOL)
            self.assertEqual(len({app.pk for app in applications}), MAX_POOL)
        with self.assertRaises(ValidationError):
            self.calculate()
        self.assertEqual(OperationalRun.objects.count(), 0, 'Never score only the one complete applicant.')
        with transaction.atomic(), patch('django.utils.timezone.now', return_value=self.fixture_time):
            program = Program.objects.select_for_update().get(pk=self.program.pk)
            member = create_member('FICTIONAL-LIMIT-OVER')
            overflow = ProgramApplication.objects.create(program=program, member=member,
                public_reference=allocate_reference(program))
        with self.assertRaisesMessage(ValidationError, 'WHOLE_POOL_UNSUPPORTED'):
            self.calculate()
        self.assertEqual(OperationalRun.objects.count(), 0)
        self.client.force_login(self.officer)
        response = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]),
                                   {'applicants_page': '41'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['inventory'].paginator.count, 2001)
        self.assertEqual(response.context['applicant_count'], 2001)
        self.assertEqual(len(response.context['inventory']), 1)
        self.assertFalse(response.context['ready'])
        response = self.client.get(reverse('programs:applications', args=[self.program.pk]), {'page': '101'})
        self.assertEqual(response.context['page_obj'].paginator.count, 2001)
        self.assertEqual(len(response.context['page_obj']), 1)
        print('PASS: actual 2,000-row locked inventory; unresolved complete pool blocked; '
              '2,001 rejected without partial scores; all 2,001 visible through both paginated workspaces.', flush=True)
