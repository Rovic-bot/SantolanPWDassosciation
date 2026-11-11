import ast
import json
import os
from pathlib import Path
import subprocess
import sys

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TransactionTestCase
from django.urls import get_resolver

from programs.test_approved_terms import TermsHelpers
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .recalculation_diagnostics import simulate_fixture
from .recalculation_fixtures import SCENARIOS

ROOT = Path(__file__).resolve().parent.parent


class RecalculationIsolationTests(SimpleTestCase):
    def test_subprocess_replay_forbids_settings_database_network_and_writes(self):
        code = """import sys, os
class Block:
    def find_spec(self, fullname, *args):
        if fullname in ('django.db', 'django.conf', 'config', 'dotenv', 'MySQLdb',
                        'ewaf.models', 'ewaf.services', 'ewaf.scoring_inputs', 'programs', 'members'):
            raise RuntimeError('Forbidden runtime import: ' + fullname)
sys.meta_path.insert(0, Block())
def audit(event, args):
    if event.startswith(('socket.', 'subprocess.')):
        raise RuntimeError('Forbidden runtime IO')
    if event == 'open':
        path, mode, flags = args
        if isinstance(mode, str) and any(char in mode for char in 'wax+') or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            raise RuntimeError('Forbidden file write')
sys.addaudithook(audit)
from ewaf.recalculation_fixtures import SCENARIOS
from ewaf.recalculation_diagnostics import simulate_fixture
for name in SCENARIOS:
    result = simulate_fixture(name)
    assert result['effective_authorization'] is False
assert simulate_fixture('history-v1')['complete']
print('All fixture replays isolated from settings, DB, network and file writes.')
"""
        env = {key: value for key, value in os.environ.items() if key.upper() in
               {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP'}}
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_has_fixed_names_and_expected_exit_codes(self):
        for name, expected in (('history-v1', 0), ('precision-v1', 0), ('incomplete-v1', 2),
                               ('stale-v1', 2), ('unresolved-v1', 2), ('unauthorized-v1', 2), ('../other', 2)):
            result = subprocess.run([sys.executable, '-B', 'scripts/g17_synthetic_diagnostics.py', name],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, expected, result.stderr)
            if name != '../other':
                data = json.loads(result.stdout)
                self.assertFalse(data['effective_authorization'])
                self.assertFalse(data['operational_ready'])
            else:
                self.assertIn('invalid choice', result.stderr)

    def test_new_engine_has_no_runtime_registration_or_side_effect_imports(self):
        allowed = {'hashlib', 'json', 're', 'datetime', 'normalization', 'ranking_diagnostics',
                   'recalculation_fixtures', 'pathlib', 'types'}
        for name in ('recalculation_diagnostics.py', 'recalculation_fixtures.py'):
            tree = ast.parse((ROOT / 'ewaf' / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue({alias.name for alias in node.names} <= allowed)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed)
        # The existing runtime app entry points must not import the new simulation.
        for folder in ('ewaf', 'programs', 'assistance', 'announcements', 'core', 'config'):
            for path in (ROOT / folder).glob('*.py'):
                if path.name.startswith(('test', 'recalculation_')):
                    continue
                self.assertNotIn('recalculation_diagnostics', path.read_text(encoding='utf-8'))


class RecalculationPreservationTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers,
                                    TermsHelpers, TransactionTestCase):
    def setUp(self):
        from .test_ranking_preservation import RankingPreservationTests
        RankingPreservationTests.setUp(self)

    def all_rows(self):
        return {model._meta.label_lower: list(model.objects.order_by('pk').values())
                for model in apps.get_models()}

    def test_every_existing_row_and_audit_preserved_with_zero_simulation_queries(self):
        before = self.all_rows()

        def forbid(execute, sql, params, many, context):
            self.fail('The synthetic simulation attempted a database query.')

        with connection.execute_wrapper(forbid):
            for name in SCENARIOS:
                simulate_fixture(name)
        self.assertEqual(self.all_rows(), before)

    def test_no_new_models_schema_permissions_or_routes(self):
        from django.contrib.auth.models import Permission
        before_tables = set(connection.introspection.table_names())
        before_models = set(apps.get_models())
        before_routes = repr(get_resolver().url_patterns)
        simulate_fixture('history-v1')
        self.assertEqual(set(connection.introspection.table_names()), before_tables)
        self.assertEqual(set(apps.get_models()), before_models)
        self.assertEqual(repr(get_resolver().url_patterns), before_routes)
        self.assertEqual(MigrationLoader(connection).graph.leaf_nodes('ewaf'), [('ewaf', '0008_operational_four')])
        self.assertFalse(Permission.objects.filter(codename__icontains='recalculation').exists())
        self.assertFalse(any('recalculation' in table for table in before_tables))

    def test_operational_guards_and_score_free_readiness_remain_closed(self):
        from . import services
        from .readiness import require_operational_evidence
        from .configuration_services import require_configuration_authorization
        from .scoring_readiness import require_operational_scoring
        from .ranking_readiness import require_operational_ranking, ranking_readiness
        simulate_fixture('history-v1')
        for guard in (require_operational_evidence, require_configuration_authorization,
                      require_operational_scoring, require_operational_ranking):
            with self.assertRaises(ValidationError):
                guard(approved=True, user=self.officer, complete=True)
        for call in (
            lambda: services.save_configuration(user=self.officer, data={}),
            lambda: services.save_input(self.application.pk, user=self.officer, data={}),
            lambda: services.generate_ranking(self.program.pk, user=self.officer, configuration=None, version=1),
            lambda: services.current_ranking(self.program),
            lambda: services.require_ranked(self.application, self.program),
        ):
            with self.assertRaises(ValidationError):
                call()
        readiness = ranking_readiness(self.application.pk, user=self.officer, program_id=self.program.pk)
        self.assertFalse(readiness['operational_ready'])
        self.assertEqual(readiness['readiness']['mathematical_readiness'], 'UNAVAILABLE_FOR_APPLICANTS')
        for key in ('"score_0_1"', '"score_0_100"', '"groups"', '"rank"'):
            self.assertNotIn(key, json.dumps(readiness))
