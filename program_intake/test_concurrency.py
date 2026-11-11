from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from members.models import Member
from programs.models import ProgramApplication, ProgramDocument
from . import tests as intake_tests
from .models import ApplicationCode


@override_settings(ROOT_URLCONF='program_intake.test_urls', PROGRAM_INTAKE_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=True)
class MembershipMatchConcurrencyTests(TransactionTestCase):
    setUp = intake_tests.IntakeTests.setUp
    grant = intake_tests.IntakeTests.grant
    submit = intake_tests.IntakeTests.submit

    def test_concurrent_matching_and_submissions_reuse_the_same_member_application(self):
        barrier = Barrier(2)
        before = Member.objects.values().get(pk=self.member.pk)
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.submit().pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(ProgramApplication.objects.count(), 1)
        self.assertEqual(ProgramDocument.objects.count(), 1)
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertFalse(ApplicationCode.objects.exists())
