"""Compare legacy assertions with the saved application-review templates.

Use only through g12_test_runner.py. The overlay never reverts working files.
"""
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.test import override_settings

from .registration_intake_test_runner import RegistrationIntakeTestRunner


class ApplicationReviewBaselineRunner(RegistrationIntakeTestRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        before = Path(settings.BASE_DIR) / '.local/application-review-layout-20261106/before/templates'
        originals = {str(path.relative_to(before)).replace('\\', '/'): path.read_text(encoding='utf-8')
                     for path in before.rglob('*.html')}
        if len(originals) != 4:
            raise RuntimeError('The four saved pre-layout templates are required.')
        templates = deepcopy(settings.TEMPLATES)
        templates[0]['APP_DIRS'] = False
        templates[0]['OPTIONS']['loaders'] = [
            ('django.template.loaders.locmem.Loader', originals),
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]
        self.baseline_templates = override_settings(TEMPLATES=templates)
        self.baseline_templates.enable()

    def teardown_test_environment(self, **kwargs):
        self.baseline_templates.disable()
        super().teardown_test_environment(**kwargs)
