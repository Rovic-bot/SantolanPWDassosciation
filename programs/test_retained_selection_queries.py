"""Batched reads must preserve the original adoption and approval boundaries."""
from datetime import timedelta
from time import perf_counter

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from assistance.models import AssistanceCase, EligibilityStatus
from members.tests import create_member
from programs.mandatory_ewaf import ACTION, CONTRACT, adoption, retained_selections
from programs.models import Program, ProgramApplication, ProgramLog


class RetainedSelectionQueryTests(TestCase):
    def setUp(self):
        self.member = create_member('SYNTHETIC-QUERY-AUDIT')
        self.status, _ = EligibilityStatus.objects.get_or_create(code='eligible', defaults={'label': 'Eligible'})

    def fixture(self, index):
        program = Program.objects.create(name=f'Synthetic retained program {index}')
        application = ProgramApplication.objects.create(program=program, member=self.member,
            public_reference=f'SYNTHETIC-RETAINED-{index}', status='SELECTED')
        case = AssistanceCase.objects.create(application=application, eligibility=self.status,
            eligibility_label='Eligible', reviewed_at=timezone.now(), member_version=0,
            program_version=0, decision='approved', decided_at=timezone.now()-timedelta(days=1))
        witness = ProgramLog.objects.create(program=program, action=ACTION, changes={
            'contract': CONTRACT, 'ewaf_applicable': {'before': False, 'after': True},
            'retained_selection_ids': [str(application.pk)]})
        return program, application, case, witness

    def test_batched_witnesses_match_original_projection_with_bounded_queries(self):
        fixtures = [self.fixture(index) for index in range(12)]
        programs = [row[0] for row in fixtures]
        original = {}
        with CaptureQueriesContext(connection) as before:
            started = perf_counter()
            for program in programs:
                row = adoption(program)
                original[program.pk] = set(program.applications.filter(
                    pk__in=row.changes['retained_selection_ids'], status__in=('SELECTED', 'COMPLETED'),
                    assistance_case__decision='approved', assistance_case__decided_at__lte=row.occurred_at
                ).values_list('pk', flat=True))
            before_ms = (perf_counter() - started) * 1000
        with CaptureQueriesContext(connection) as after:
            started = perf_counter()
            actual = retained_selections(programs)
            after_ms = (perf_counter() - started) * 1000
        self.assertEqual(actual, original)
        self.assertEqual(len(after), 2)
        print(f'Retained selections, 12 programs: {len(before)} -> {len(after)} queries; '
              f'{before_ms:.1f} -> {after_ms:.1f} ms', flush=True)

    def test_foreign_application_ids_and_later_approvals_are_excluded(self):
        first, second = self.fixture(1), self.fixture(2)
        first[3].changes['retained_selection_ids'].append(str(second[1].pk))
        first[3].save(update_fields=['changes'])
        second[2].decided_at = timezone.now() + timedelta(days=1)
        second[2].save(update_fields=['decided_at'])
        self.assertEqual(retained_selections([first[0], second[0]]),
                         {first[0].pk: {first[1].pk}, second[0].pk: set()})
        first[2].decision = 'rejected'
        first[2].save(update_fields=['decision'])
        self.assertEqual(retained_selections([first[0]])[first[0].pk], set())

    def test_later_valid_event_cannot_replace_invalid_first_witness(self):
        program, application, _, witness = self.fixture(1)
        valid = witness.changes.copy()
        witness.changes = {**valid, 'contract': 'invalid'}
        witness.save(update_fields=['changes'])
        ProgramLog.objects.create(program=program, action=ACTION, changes=valid)
        self.assertEqual(retained_selections([program])[program.pk], set())

    def test_empty_or_unsaved_programs_need_no_database_queries(self):
        with self.assertNumQueries(0):
            self.assertEqual(retained_selections([]), {})
            self.assertEqual(retained_selections([Program()]), {})
