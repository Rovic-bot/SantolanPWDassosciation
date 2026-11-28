"""Full discovery with real migrations, isolated media and no external sockets.

Launch through scripts/quality_postgres_launch.py or the isolated g12 runner. JSON records individual results;
no test exclusions or assertion changes are applied.
"""
import json
import os
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings
from scripts.durable_test_runner import DurableTestRunner, DurablePostgresTestRunner


class AuditResult(DiscoverRunner.test_runner.resultclass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def stopTest(self, test):
        super().stopTest(test)
        folder = Path(os.environ['G12_ARTIFACT_DIR'])
        temporary = folder / 'audit-results.tmp'
        temporary.write_text(json.dumps(self.records, indent=2), encoding='utf-8')
        temporary.replace(folder / 'audit-results.json')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            if not any(row['id'] == test.id() for row in self.records):
                self.records.append({'id': test.id(), 'status': 'FAIL', 'kind': 'subtest'})
            self._save_error(subtest, err)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'id': test.id(), 'status': 'PASS'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        if not any(row['id'] == test.id() for row in self.records):
            self.records.append({'id': test.id(), 'status': 'FAIL'})
        self._save_error(test, err)

    def addError(self, test, err):
        super().addError(test, err)
        if not any(row['id'] == test.id() for row in self.records):
            self.records.append({'id': test.id(), 'status': 'FAIL', 'kind': 'error'})
        self._save_error(test, err)

    def _save_error(self, test, err):
        with Path(os.environ['G12_ARTIFACT_DIR'], 'audit-errors.txt').open('a', encoding='utf-8') as log:
            log.write(test.id() + '\n' + self._exc_info_to_string(err, test) + '\n')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({'id': test.id(), 'status': 'NOT RUN', 'reason': reason})


class QualityAuditRunner(DurableTestRunner):
    def get_resultclass(self):
        return AuditResult

    def run_suite(self, suite, **kwargs):
        result = super().run_suite(suite, **kwargs)
        Path(os.environ['G12_ARTIFACT_DIR'], 'audit-results.json').write_text(
            json.dumps(result.records, indent=2), encoding='utf-8')
        return result

    def run_tests(self, test_labels, **kwargs):
        connect, connect_ex, lookup = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

        def check(host):
            if host not in ('127.0.0.1', 'localhost', '::1', b'127.0.0.1', b'localhost', b'::1'):
                raise AssertionError('Audit prohibits external network connections.')

        def local_connect(sock, address):
            check(address[0])
            return connect(sock, address)

        def local_connect_ex(sock, address):
            check(address[0])
            return connect_ex(sock, address)

        def local_lookup(host, *args, **options):
            check(host)
            return lookup(host, *args, **options)

        with tempfile.TemporaryDirectory(prefix='santolan-audit-media-') as media:
            with override_settings(MEDIA_ROOT=media, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', *settings.PASSWORD_HASHERS]), \
                    patch('socket.socket.connect', local_connect), \
                    patch('socket.socket.connect_ex', local_connect_ex), \
                    patch('socket.getaddrinfo', local_lookup):
                return super().run_tests(test_labels, **kwargs)


class QualityPostgresAuditRunner(QualityAuditRunner, DurablePostgresTestRunner):
    setup_databases = DurablePostgresTestRunner.setup_databases
    teardown_databases = DurablePostgresTestRunner.teardown_databases
