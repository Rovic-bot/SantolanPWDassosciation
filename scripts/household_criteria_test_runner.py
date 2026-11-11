"""Exact reviewed household migrations, within the disposable test harness only."""
from unittest.mock import patch
from .registration_handoff_test_runner import RegistrationHandoffTestRunner
from .remaining_phases_test_runner import REVIEWED_MIGRATIONS

HOUSEHOLD_MIGRATIONS = {('members', '0007_household_registration_criteria'): '8f416a1b134c0257eb8b24edfe2571fe382c4931e256a3a4b33b7bdfc55069cf', ('membership', '0008_household_registration_criteria'): '1d86e01aad4522159aaa085040e91e2f8b53263004a6bf4b55eb3f606afbb0f5', ('ewaf', '0009_household_registration_criteria'): '8dfcd9fee5c1fd515225185db78ff164b8ba466f8acda7d686ffec6ecd93b50d'}

class HouseholdCriteriaTestRunner(RegistrationHandoffTestRunner):
    def run_tests(self, test_labels, **kwargs):
        with patch.dict(REVIEWED_MIGRATIONS, HOUSEHOLD_MIGRATIONS):
            return super().run_tests(test_labels, **kwargs)
