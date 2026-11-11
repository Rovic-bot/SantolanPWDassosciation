"""Reuse a pool inspection only within one locked, read-only workspace request.

Nothing survives the request. Decisions and generation always execute their
normal fresh validations. The surrounding terms lock prevents edits between
the workspace's preview, generation-readiness and saved-ranking inspections.
"""
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps

from django.utils import timezone

_inventory_reads = ContextVar('ewaf_workspace_inventory_reads', default=None)


def reuse_workspace_inventory(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != 'GET':
            return view(request, *args, **kwargs)
        from programs.terms import terms_lock
        with terms_lock():
            token = _inventory_reads.set({})
            try:
                return view(request, *args, **kwargs)
            finally:
                _inventory_reads.reset(token)
    return wrapped


def reuse_inventory(inspection):
    @wraps(inspection)
    def wrapped(program, applications, configuration=None):
        cache = _inventory_reads.get()
        if cache is None:
            return inspection(program, applications, configuration)
        # Rolling rankings may inspect different cutoffs in the same request;
        # their evidence periods must never share an inventory.
        key = (program.pk, program.version,
            tuple((app.pk, app.version, app.member_id, app.member.version) for app in applications),
            (configuration.pk, configuration.digest, configuration.assessment_cutoff)
                if configuration else None,
            timezone.localdate(), timezone.get_current_timezone_name())
        if key not in cache:
            cache[key] = inspection(program, applications, configuration)
        # The view adds display fields and capture canonicalizes these values.
        # Neither may change the next caller's retained source representation.
        return deepcopy(cache[key])
    return wrapped
