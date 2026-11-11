from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from .models import ProgramApplication
from .information_forms import information_update_form
from . import information_confirmation as service


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def review(request, reference):
    require_workspace_permissions(request.user, *service.UPDATE)
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member__application'), pk=reference)
    form = information_update_form(request.POST if request.method == 'POST' else None, application=application)
    if request.method == 'POST' and form.is_valid():
        try:
            if request.FILES or getattr(request, 'upload_limit_exceeded', False):
                raise ValidationError('Use the application document controls to add or correct files.')
            service.update_reported_information(reference, user=request.user, data=request.POST,
                address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Member information saved and reported changes reviewed. You can now review eligibility.')
            return redirect('programs:application_detail', pk=application.program_id, reference=application.pk)
    from .review_services import DIRECT_REVIEW_STATUSES
    return render(request, 'programs/workflow/information_review.html', {'application': application,
        'declaration': service.declaration(application), 'form': form,
        'can_update_information': application.status in DIRECT_REVIEW_STATUSES,
        'confirmation_status': service.confirmation_context(application)})
