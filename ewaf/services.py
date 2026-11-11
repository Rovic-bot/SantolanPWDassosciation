"""Retired mutation entry points, kept fail-closed until revised stage eight.

Historical Configuration/RankingRun/Snapshot rows and pure calculation code remain
available for audit. Do not reactivate the old fixed-criterion workflow.
"""
from django.core.exceptions import ValidationError
from core.permissions import require_workspace_permissions

VIEW = ('programs.view_program', 'programs.view_programapplication', 'assistance.view_assistancecase', 'ewaf.view_rankingrun')

def require_current_ewaf_workflow():
    raise ValidationError('EWAF configuration and computation are awaiting stage-eight alignment and acceptance. Historical calculations are preserved; new EWAF-dependent final decisions remain unavailable.')

def save_configuration(*, user, data):
    require_workspace_permissions(user, 'ewaf.add_configuration')
    require_current_ewaf_workflow()

def save_input(reference, *, user, data, address=None):
    require_workspace_permissions(user, *VIEW, 'ewaf.change_applicationinput')
    require_current_ewaf_workflow()

def generate_ranking(pk, *, user, configuration, version, address=None):
    require_workspace_permissions(user, *VIEW, 'ewaf.generate_ranking')
    require_current_ewaf_workflow()

def current_ranking(program):
    require_current_ewaf_workflow()

def require_ranked(application, program):
    from programs.workflow import require_verified_photo
    require_verified_photo(application)
    require_current_ewaf_workflow()


# G12 is isolated from all retired scoring/configuration entry points above.
from .evidence_services import record_policy, record_assessment, record_readiness
