"""Phase 1 test isolation only; never imported by application settings.

Use only through the existing g12_test_runner.py fresh-instance launcher.
Existing migrations may build the synthetic test schema; no new migration is
generated and ordinary settings/startup guards remain unchanged.
"""
import os
from pathlib import Path
import tempfile

from django.core.exceptions import PermissionDenied
from django.test.utils import override_settings

from scripts.durable_test_runner import DurableTestRunner


class PhaseOneTestRunner(DurableTestRunner):
    def run_tests(self, test_labels, **kwargs):
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or
                directory.parent != Path(tempfile.gettempdir()).resolve() or
                not directory.name.startswith('santolan-g12-tests-')):
            raise PermissionDenied('Use the verified fresh-instance G12 launcher only.')
        with tempfile.TemporaryDirectory(prefix='phase1-private-media-', dir=directory) as media:
            with override_settings(MEDIA_ROOT=media):
                print(f'Phase 1 synthetic private media: {media}', flush=True)
                return super().run_tests(test_labels, **kwargs)
