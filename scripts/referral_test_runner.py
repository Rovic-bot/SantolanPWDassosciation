"""Exact referral migration scope within the isolated test database only."""
from unittest.mock import patch
from .household_criteria_test_runner import HouseholdCriteriaTestRunner
from .remaining_phases_test_runner import REVIEWED_MIGRATIONS

REFERRAL_MIGRATIONS = {('assistance', '0004_referralwindow_referralaction_referralgrant_and_more'): 'ad032a67a7339cb45fe09882192e394e8ea8a6c088120f72746114be78a6a394'}

REFERRAL_MIGRATIONS[('assistance', '0005_referral_ticket_subject')] = '90e3554465ca48977d277e20d3072fff0ce556c54b1c99a83275231f0f7879b5'

class ReferralTestRunner(HouseholdCriteriaTestRunner):
    def run_tests(self, test_labels, **kwargs):
        with patch.dict(REVIEWED_MIGRATIONS, REFERRAL_MIGRATIONS):
            return super().run_tests(test_labels, **kwargs)
