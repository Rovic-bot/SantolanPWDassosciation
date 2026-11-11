"""Read reuse cannot cross a request, evidence period or mutation boundary."""
from contextlib import nullcontext
from copy import copy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from .workspace_read_cache import reuse_inventory, reuse_workspace_inventory


class WorkspaceReadCacheTests(SimpleTestCase):
    def test_distinct_cutoffs_and_versions_do_not_share_and_results_are_isolated(self):
        calls = []
        program = SimpleNamespace(pk=1, version=1)
        application = SimpleNamespace(pk=1, version=1, member_id=1, member=SimpleNamespace(version=1))
        configuration = SimpleNamespace(pk=1, digest='approved', assessment_cutoff=timezone.now())

        @reuse_inventory
        def inspect(program, applications, configuration):
            calls.append(configuration.assessment_cutoff)
            return [{'errors': [], 'source': {'version': applications[0].member.version}}], {}, []

        @reuse_workspace_inventory
        def view(request):
            original = inspect(program, [application], configuration)
            original[0][0]['source']['version'] = 'display-only edit'
            self.assertEqual(inspect(program, [application], configuration)[0][0]['source']['version'], 1)
            earlier = copy(configuration)
            earlier.assessment_cutoff -= timedelta(days=1)
            inspect(program, [application], earlier)
            application.member.version += 1
            self.assertEqual(inspect(program, [application], configuration)[0][0]['source']['version'], 2)

        with patch('programs.terms.terms_lock', nullcontext):
            view(SimpleNamespace(method='GET'))
        self.assertEqual(len(calls), 3)
        inspect(program, [application], configuration)
        self.assertEqual(len(calls), 4)

    def test_post_and_failed_requests_leave_no_reusable_inventory(self):
        calls = []
        program = SimpleNamespace(pk=1, version=1)

        @reuse_inventory
        def inspect(*args):
            calls.append(1)
            return [], {}, []

        @reuse_workspace_inventory
        def view(request):
            inspect(program, [], None)
            inspect(program, [], None)
            if getattr(request, 'fail', False):
                raise ValueError('Synthetic render failure')

        with patch('programs.terms.terms_lock', nullcontext):
            view(SimpleNamespace(method='GET'))
            self.assertEqual(len(calls), 1)
            view(SimpleNamespace(method='GET'))
            self.assertEqual(len(calls), 2)
            view(SimpleNamespace(method='POST'))
            self.assertEqual(len(calls), 4)
            with self.assertRaises(ValueError):
                view(SimpleNamespace(method='GET', fail=True))
            inspect(program, [], None)
            self.assertEqual(len(calls), 6)


class PolicyDefinitionReuseTests(SimpleTestCase):
    def test_reusing_definitions_preserves_every_policy_finding(self):
        from . import dataset_methods
        from .revised import contracts
        original = contracts.applicable
        for method in dataset_methods.SIGNATURES:
            content = contracts.initial_content(method)
            with self.subTest(method=method):
                # Compare full diagnostic results with the former per-choice
                # definition lookup, including unset and unsupported choices.
                with patch.object(contracts, 'applicable',
                        side_effect=lambda value, key, **kwargs: original(value, key)):
                    previous = contracts.findings(content, live=False)
                with patch.object(contracts, 'specifications', wraps=contracts.specifications) as specs:
                    current = contracts.findings(content, live=False)
                self.assertEqual(current, previous)
                self.assertLess(specs.call_count, 6)
