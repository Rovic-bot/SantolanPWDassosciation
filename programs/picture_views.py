from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from accounts.decorators import dashboard_required
from announcements.views import image_response
from core.permissions import require_workspace_permissions
from .models import Program, ProgramPicture


@never_cache
@require_safe
def public(request, pk):
    get_object_or_404(Program.objects.public(), pk=pk)
    return image_response(get_object_or_404(ProgramPicture, program_id=pk))


@never_cache
@dashboard_required
@require_safe
def preview(request, pk):
    require_workspace_permissions(request.user, 'programs.view_program')
    return image_response(get_object_or_404(ProgramPicture, program_id=pk))
