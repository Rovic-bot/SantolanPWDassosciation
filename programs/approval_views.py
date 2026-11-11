from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from .approval_forms import PDAOApprovalForm
from .approval_services import record_pdao_approval
from .models import Program
from .views import page


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def approval_history(request, pk):
    require_workspace_permissions(request.user, 'programs.view_program', 'programs.view_pdaoapprovalrecord')
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'programs.record_pdaoapprovalrecord')
    program = get_object_or_404(Program, pk=pk)
    records = program.pdao_approval_records.all()
    latest = records.first()
    can_record = request.user.has_perm('programs.record_pdaoapprovalrecord')
    form = PDAOApprovalForm(request.POST if request.method == 'POST' else None, initial={
        'expected_version': latest.version if latest else 0, 'expected_program_version': program.version,
    }) if can_record else None
    if request.method == 'POST':
        if request.FILES:
            form.add_error(None, 'Approval letters are kept physically at the Association office. Uploads are not accepted.')
        elif form.is_valid():
            try:
                record_pdao_approval(pk, user=request.user, data=request.POST, address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'PDAO history entry recorded. Previous entries are preserved.')
                return redirect('programs:pdao_history', pk=pk)
    return render(request, 'programs/pdao_history.html', {
        'program': program, 'form': form, 'history': page(request, records),
    })
