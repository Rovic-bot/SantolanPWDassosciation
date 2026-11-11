"""Compare historical assertions with the preserved pre-redesign public templates.

Used only with g12_test_runner.py's disposable database. No source file rollback
or application database access is needed to establish the existing failures.
"""
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.test import override_settings
from django.test.runner import DiscoverRunner


class BaselineTemplateRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        before = Path(settings.BASE_DIR) / '.local/public-make-20261104/before/templates'
        if not (before / 'public/base.html').is_file():
            raise RuntimeError('The pre-redesign template snapshot is required.')
        templates = deepcopy(settings.TEMPLATES)
        templates[0]['DIRS'].insert(0, before)
        self.baseline_templates = override_settings(TEMPLATES=templates)
        self.baseline_templates.enable()

    def teardown_test_environment(self, **kwargs):
        self.baseline_templates.disable()
        super().teardown_test_environment(**kwargs)
