"""Use only with the fresh-instance G12 launcher; never an application runner."""
from django.test import override_settings

from scripts.registration_intake_test_runner import RegistrationIntakeTestRunner


class SyntheticTwelveRunner(RegistrationIntakeTestRunner):
    def run_tests(self, test_labels, **kwargs):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                               REFERRAL_ENABLED=False):
            return super().run_tests(test_labels, **kwargs)
