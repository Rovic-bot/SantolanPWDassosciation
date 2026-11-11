"""Read-only navigation into existing per-program application reviews."""
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from accounts.decorators import dashboard_required
from programs.models import Program
from .permissions import require_workspace_permissions


@never_cache
@dashboard_required
@require_safe
def application_programs(request):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.view_programapplication')
    from programs.review_workspace import application_workspace_context
    return render(request, 'programs/application_workspace/page.html', application_workspace_context(request))
