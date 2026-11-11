"""In-process capability for fictional durable tests, never an application setting.

Must be launched by g12_test_runner.py against its freshly initialized MySQL.
The capability dies with this test process. No request/DB label grants access.
"""
import os
from pathlib import Path
import tempfile

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.runner import DiscoverRunner

_identity = None


def identity():
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_setting('data_directory'),"
                           "current_setting('port'),system_identifier::text,version(),"
                           "current_setting('transaction_isolation') FROM pg_control_system()")
            return cursor.fetchone()
    if connection.vendor != 'mysql':
        raise PermissionDenied('Disposable MySQL required.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE(), @@datadir, @@port, @@server_uuid, VERSION(), @@transaction_isolation')
        return cursor.fetchone()


def require_disposable():
    if _identity is None:
        raise PermissionDenied('Durable numerical development requires the isolated test runner.')
    actual = identity()
    expected = 'test_pg_disposable' if connection.vendor == 'postgresql' else 'test_g12_disposable'
    if actual[:4] != _identity[:4] or actual[0] != expected:
        raise PermissionDenied('Disposable database identity changed.')
    # Tests may override media only to their own newly created temporary fixtures.
    from django.conf import settings
    media = Path(settings.MEDIA_ROOT).resolve()
    if not media.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise PermissionDenied('Fictional temporary media required.')


class DurableTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        global _identity
        # Check before migrations as well as after Django creates its test database.
        actual = identity()
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or
                not directory.name.startswith('santolan-g12-tests-') or
                directory.parent != Path(tempfile.gettempdir()).resolve() or
                Path(actual[1]).resolve() != directory / 'data' or actual[0] != 'g12_empty' or
                connection.settings_dict['HOST'] != '127.0.0.1' or
                connection.settings_dict['TEST']['NAME'] != 'test_g12_disposable'):
            raise PermissionDenied('Not the isolated fresh-instance harness.')
        with connection.cursor() as cursor:
            cursor.execute('SHOW TABLES')
            if cursor.fetchall():
                raise PermissionDenied('Harness base database must be empty.')
        result = super().setup_databases(**kwargs)
        test_identity = identity()
        if test_identity[1:4] != actual[1:4] or test_identity[0] != 'test_g12_disposable':
            raise PermissionDenied('Test database identity mismatch.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
            if set(row[0] for row in cursor.fetchall()) != {'InnoDB'}:
                raise PermissionDenied('All test tables must be transactional InnoDB.')
        _identity = test_identity
        print('Durable isolated test identity:', test_identity, 'all tables InnoDB', flush=True)
        return result

    def teardown_databases(self, old_config, **kwargs):
        global _identity
        _identity = None
        return super().teardown_databases(old_config, **kwargs)


class DurablePostgresTestRunner(DiscoverRunner):
    """Equivalent capability for a newly initialized loopback PostgreSQL cluster."""
    def setup_databases(self, **kwargs):
        global _identity
        directory = Path(os.environ.get('PG_TEST_ARTIFACT_DIR', '')).resolve()
        actual = identity()
        if (connection.vendor != 'postgresql' or os.environ.get('PYTHON_DOTENV_DISABLED') != '1'
                or not directory.name.startswith('santolan-pg-tests-')
                or directory.parent != Path(tempfile.gettempdir()).resolve()
                or Path(actual[1]).resolve() != directory / 'data'
                or actual[0] != 'pg_empty' or connection.settings_dict['HOST'] != '127.0.0.1'
                or connection.settings_dict['TEST']['NAME'] != 'test_pg_disposable'):
            raise PermissionDenied('Not the isolated PostgreSQL harness.')
        with connection.cursor() as cursor:
            if connection.introspection.table_names(cursor):
                raise PermissionDenied('Harness base database must be empty.')
        result = super().setup_databases(**kwargs)
        test_identity = identity()
        if test_identity[1:4] != actual[1:4] or test_identity[0] != 'test_pg_disposable':
            raise PermissionDenied('Test database identity mismatch.')
        _identity = test_identity
        return result

    def teardown_databases(self, old_config, **kwargs):
        global _identity
        _identity = None
        return super().teardown_databases(old_config, **kwargs)
