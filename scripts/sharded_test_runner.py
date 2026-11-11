"""Partition full discovery across independent, fully guarded MySQL instances."""
import hashlib
import json
import os
from pathlib import Path
from .durable_test_runner import DurableTestRunner


class ShardedDurableTestRunner(DurableTestRunner):
    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument('--shard-index', type=int, required=True)
        parser.add_argument('--shard-count', type=int, required=True)

    def __init__(self, *args, shard_index, shard_count, **kwargs):
        super().__init__(*args, **kwargs)
        if not 0 <= shard_index < shard_count <= 8:
            raise ValueError('Choose a valid bounded test partition.')
        self.shard_index, self.shard_count = shard_index, shard_count

    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)
        def flatten(node):
            for test in node:
                if hasattr(test, '__iter__'):
                    yield from flatten(test)
                else:
                    yield test
        all_tests = list(flatten(suite))
        # Keep whole test classes together, preserving Django's original ordering.
        selected = [test for test in all_tests if
            int(hashlib.sha256(test.id().rsplit('.', 1)[0].encode()).hexdigest(), 16) % self.shard_count == self.shard_index]
        evidence = {'shard': self.shard_index, 'shards': self.shard_count,
                    'discovered': [test.id() for test in all_tests], 'selected': [test.id() for test in selected]}
        directory = Path(os.environ['G12_ARTIFACT_DIR'])
        (directory / 'test-partition.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(f'Full regression partition {self.shard_index + 1}/{self.shard_count}: '
              f'{len(selected)} of {len(all_tests)} discovered tests.', flush=True)
        return self.test_suite(selected)
