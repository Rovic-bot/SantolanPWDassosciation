"""Recheck existing dashboard assertions with the saved pre-redesign login.

Run only via g12_test_runner.py against its disposable database. This overlays
the original template in memory without reverting files or touching live data.
"""
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.test import override_settings
from django.test.runner import DiscoverRunner


class BaselineLoginRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        original = Path(settings.BASE_DIR) / '.local/admin-sign-in-20261105/before/login.html'
        templates = deepcopy(settings.TEMPLATES)
        templates[0]['APP_DIRS'] = False
        templates[0]['OPTIONS']['loaders'] = [
            ('django.template.loaders.locmem.Loader', {
                'accounts/login.html': original.read_text(encoding='utf-8'),
            }),
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]
        self.baseline_templates = override_settings(TEMPLATES=templates)
        self.baseline_templates.enable()

    def teardown_test_environment(self, **kwargs):
        self.baseline_templates.disable()
        super().teardown_test_environment(**kwargs)
