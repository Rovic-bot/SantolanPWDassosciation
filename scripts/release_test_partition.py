"""Discover every test and run one reproducible partition in an isolated harness.

Use with quality_postgres_launch.py or a loopback-only disposable Linux database.
Browser cases run separately with the installed browser toolchain. No assertion
is removed and the manifest accounts for every discovered test ID.
"""
import hashlib
import json
import os
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from .quality_audit_runner import QualityPostgresAuditRunner


class ReleaseTestRunner(QualityPostgresAuditRunner):
    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument('--partition', type=int, default=0)
        parser.add_argument('--partitions', type=int, default=1)
        parser.add_argument('--browser-only', action='store_true')

    def __init__(self, *args, partition=0, partitions=1, browser_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not 0 <= partition < partitions <= 16:
            raise ValueError('Choose a valid partition in a maximum of 16 partitions.')
        self.partition, self.partitions = partition, partitions
        self.browser_only = browser_only

    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)

        def flatten(node):
            for case in node:
                if hasattr(case, '_testMethodName'):
                    yield case
                else:
                    yield from flatten(case)

        all_cases = list(flatten(suite))
        selected, browser_ids = [], []
        for case in all_cases:
            browser = isinstance(case, StaticLiveServerTestCase)
            if browser:
                browser_ids.append(case.id())
            # Keep whole classes together. SHA256 makes membership independent
            # of Python hash randomization and discovery ordering.
            shard = int(hashlib.sha256(case.id().rsplit('.', 1)[0].encode()).hexdigest(), 16) % self.partitions
            if browser == self.browser_only and shard == self.partition:
                selected.append(case)
        manifest = {
            'discovered': [case.id() for case in all_cases],
            'selected': [case.id() for case in selected],
            'browser_cases': browser_ids, 'browser_only': self.browser_only,
            'partition': self.partition, 'partitions': self.partitions,
        }
        Path(os.environ['G12_ARTIFACT_DIR'], 'test-partition.json').write_text(
            json.dumps(manifest, indent=2), encoding='utf-8')
        print(f'Release partition {self.partition + 1}/{self.partitions}: '
              f'{len(selected)} of {len(all_cases)} cases; browser_only={self.browser_only}', flush=True)
        return self.test_suite(selected)
