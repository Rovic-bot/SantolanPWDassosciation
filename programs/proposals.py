from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from core.pdf import render_pdf
from .models import Program
from .terms import terms_lock
from django.shortcuts import get_object_or_404


@never_cache
@dashboard_required
@require_safe
def proposal(request, pk):
    require_workspace_permissions(request.user, 'programs.view_program')
    with terms_lock(), transaction.atomic():
        program = get_object_or_404(Program.objects.select_for_update(), pk=pk)
        def date(value):
            return timezone.localtime(value).strftime('%B %d, %Y, %I:%M %p') if value else 'Not specified'
        sections = [
            ('Program', program.name), ('Description', program.description),
            ('Assistance type', program.assistance_type),
            ('Registration period', f'{date(program.registration_opens_at)} to {date(program.registration_closes_at)}'),
            ('Program schedule', f'{date(program.starts_at)} to {date(program.ends_at)}'),
            ('Beneficiary slots', program.capacity_label),
            ('Requirements and instructions', program.requirements or 'No additional instructions.'),
            ('Disability-specific qualification', ', '.join(program.eligibility_profile_types.values_list('name', flat=True)) or 'Eligibility profile is not configured.'),
        ]
        for item in program.configured_requirements.filter(is_active=True):
            sections.append((item.label + (' (required)' if item.is_required else ' (optional)'), item.instructions or item.get_kind_display()))
        if program.benefit:
            sections.insert(2, ('Purpose and intended benefit', program.benefit))
        content = render_pdf('Program proposal for PDAO', sections,
            subtitle=f'Barangay Santolan PWD Association | Saved program version {program.version}\n'
                     f'Prepared {timezone.localtime():%B %d, %Y}. All schedules in Asia/Manila.\nFor review; this proposal does not establish PDAO approval.')
    response = HttpResponse(content, content_type='application/pdf')
    disposition = 'attachment' if request.GET.get('download') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="program-proposal-{program.pk}-v{program.version}.pdf"'
    response['Cache-Control'] = 'no-store, private'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
