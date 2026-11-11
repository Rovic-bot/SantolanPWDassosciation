"""Only add the reviewed 0007 to the existing fresh-disposable allowlist."""
from unittest.mock import patch
from scripts.remaining_phases_test_runner import RemainingPhasesTestRunner, REVIEWED_MIGRATIONS

HANDOFF_MIGRATION = ('membership', '0007_registration_membership_handoff')
HANDOFF_SHA256 = '8d400ddcc416c0081518dd45a5cbc2097e7b36103d391260174347c0e4c2ddb8'


class RegistrationHandoffTestRunner(RemainingPhasesTestRunner):
    def run_tests(self, test_labels, **kwargs):
        with patch.dict(REVIEWED_MIGRATIONS, {HANDOFF_MIGRATION: HANDOFF_SHA256}):
            return super().run_tests(test_labels, **kwargs)
