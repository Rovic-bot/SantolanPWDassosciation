"""Opt-in adapter for the separately installed historical intake laboratory.

Production does not install or enable this app. Its distinct evidence contract
must never relax the current dataset workflow or the legacy PR requirements.
"""
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

CONTRACT = 'verified_program_intake_v1'


def source_adapter(policy=None):
    if not getattr(settings, 'PROGRAM_INTAKE_ENABLED', False):
        return None
    if policy is not None and policy.get('source_contract') != CONTRACT:
        return None
    if not apps.is_installed('program_intake'):
        raise ImproperlyConfigured('PROGRAM_INTAKE_ENABLED requires the program_intake app.')
    from program_intake import sources
    return sources
