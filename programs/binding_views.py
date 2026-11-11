from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from zoneinfo import ZoneInfo

from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from .models import Program, ProgramTermsRevision
from .binding_services import VIEW, WRITE, capture_terms, bind_approval
from .binding_forms import TermsActionForm
from .terms import snapshot_terms, terms_digest
from .approval_policy import binding_condition
from .views import page


def display_rows(values, *, program=False):
    rows = []
    for key, value in values.items():
        if value and key.endswith('_at'):
            value = timezone.localtime(parse_datetime(value), ZoneInfo('Asia/Manila')).strftime('%B %d, %Y, %I:%M %p (Philippine time)')
        label = Program._meta.get_field(key).verbose_name if program else key.replace('_', ' ')
        rows.append((label, value))
    return rows


@never_cache
@dashboard_required
@require_safe
def readiness(request):
    require_workspace_permissions(request.user, *VIEW)
    valid = Program.objects.filter(pk=OuterRef('pk')).filter(binding_condition())
    records = Program.objects.annotate(explicit_binding=Exists(valid)).order_by('name', 'pk')
    return render(request, 'programs/approval_readiness.html', {'page_obj': page(request, records),
        'enforcement_enabled': settings.PDAO_ENFORCEMENT_ENABLED})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def terms_review(request, pk):
    require_workspace_permissions(request.user, *VIEW)
    if request.method == 'POST':
        require_workspace_permissions(request.user, *WRITE)
    program = get_object_or_404(Program, pk=pk)
    snapshot = snapshot_terms(program)
    control = getattr(program, 'approval_control', None)
    revision = control.current_revision if control else None
    latest = program.pdao_approval_records.first()
    # History is paginated; choosing older evidence requires that history page.
    approvals = page(request, program.pdao_approval_records.all())
    form = TermsActionForm(request.POST if request.method == 'POST' else None, approvals=approvals,
        initial={'version': control.version if control else 0, 'program_version': program.version,
                 'digest': terms_digest(snapshot), 'revision_id': revision.pk if revision else None,
                 'approval_version': latest.version if latest else 0})
    if request.method == 'POST':
        if request.FILES:
            form.add_error(None, 'Physical PDAO letters are kept at the office. Uploads are not accepted.')
        elif form.is_valid():
            values = form.cleaned_data
            common = {key: values[key] for key in ('version', 'program_version', 'reason', 'confirmed')}
            try:
                if values['action'] == 'capture':
                    capture_terms(pk, user=request.user, digest=values['digest'], **common)
                else:
                    bind_approval(pk, user=request.user, revision_id=values['revision_id'], approval_id=values['approval_id'],
                                  approval_version=values['approval_version'], **common)
            except ValidationError as error:
                form.add_error(None, error.messages)
            else:
                messages.success(request, 'Review recorded. Previous terms and approval history are preserved.')
                return redirect('programs:terms_review', pk=pk)
    program_rows = display_rows(snapshot['program'], program=True)
    return render(request, 'programs/terms_review.html', {'program': program, 'program_rows': program_rows,
        'event_rows': display_rows(snapshot['event'] or {}), 'revisions': page(request, program.terms_revisions.all()),
        'snapshot': snapshot, 'revision': revision, 'control': control, 'approvals': approvals,
        'history': page(request, program.approval_bindings.select_related('revision', 'approval_record')),
        'form': form if request.user.has_perms(WRITE) else None, 'enforcement_enabled': settings.PDAO_ENFORCEMENT_ENABLED})


@never_cache
@dashboard_required
@require_safe
def revision_detail(request, pk, revision_id):
    require_workspace_permissions(request.user, *VIEW)
    revision = get_object_or_404(ProgramTermsRevision.objects.select_related('program'), pk=revision_id, program_id=pk)
    return render(request, 'programs/terms_review.html', {
        'program': revision.program, 'revision': revision, 'historical': True, 'snapshot': revision.snapshot,
        'program_rows': display_rows(revision.snapshot['program'], program=True),
        'event_rows': display_rows(revision.snapshot['event'] or {}),
        'enforcement_enabled': settings.PDAO_ENFORCEMENT_ENABLED})
