"""Read-only historical analytics until the revised stage-eight workflow is accepted."""
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from .services import VIEW

NOTICE = 'This is the historical five-criterion workflow. Its calculations remain read-only and cannot create new selections. Use Program EWAF & beneficiary decisions for current four-criterion configuration, calculation and human review.'

@never_cache
@dashboard_required
@require_safe
def configuration(request):
    require_workspace_permissions(request.user, 'ewaf.add_configuration')
    return render(request, 'ewaf/unavailable.html', {'notice': NOTICE})

@never_cache
@dashboard_required
@require_safe
def assessment(request, reference):
    require_workspace_permissions(request.user, *VIEW, 'ewaf.change_applicationinput')
    get_object_or_404(ProgramApplication, pk=reference)
    return render(request, 'ewaf/unavailable.html', {'notice': NOTICE})

@never_cache
@dashboard_required
@require_safe
def ranking(request, pk):
    require_workspace_permissions(request.user, *VIEW)
    program = get_object_or_404(Program, pk=pk)
    return render(request, 'ewaf/ranking.html', {'program': program, 'notice': NOTICE,
        'runs': program.ranking_runs.prefetch_related('snapshots__application__member').all()})
