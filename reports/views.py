from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from accounts.decorators import dashboard_required
from assistance.services import VIEW_PERMISSIONS
from core.permissions import require_workspace_permissions
from core.pdf import render_pdf
from .forms import ReportFilterForm
from .presentation import member_rows, report_rows
from .services import PERMISSIONS, TITLES, report_data, report_row, record_access, csv_bytes, xlsx_bytes


@never_cache
@dashboard_required
@require_safe
def report(request, kind):
    require_workspace_permissions(request.user, *PERMISSIONS[kind])
    format = request.GET.get('format', '')
    if format not in ('', 'csv', 'pdf', 'xlsx'):
        return HttpResponseBadRequest('Choose CSV, Excel or PDF.')
    form = ReportFilterForm(request.GET, kind=kind)
    reveal_assistance = request.user.has_perms(VIEW_PERMISSIONS)
    rows, columns, page = [], [], None
    if form.is_valid():
        records, columns = report_data(kind, form.cleaned_data)
        count = records.count()
        record_access(request.user, kind, format or 'view', form.cleaned_data, count)
        if format:
            rows = (report_row(kind, item, reveal_assistance=reveal_assistance) for item in records.iterator(chunk_size=500))
            data = csv_bytes(columns, rows) if format == 'csv' else xlsx_bytes(columns, rows) if format == 'xlsx' else render_pdf(
                TITLES[kind] + ' report', columns=columns, rows=rows,
                subtitle=f'{count} matching records | {form.cleaned_data.get("start") or "All dates"} to {form.cleaned_data.get("end") or "present"}')
            response = HttpResponse(data, content_type={'csv': 'text/csv; charset=utf-8',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'pdf': 'application/pdf'}[format])
            response['Content-Disposition'] = f'attachment; filename="{kind}-report.{format}"'
            response['Cache-Control'] = 'no-store, private'
            response['X-Content-Type-Options'] = 'nosniff'
            return response
        page = Paginator(records, 30).get_page(request.GET.get('page'))
        rows = [report_row(kind, item, reveal_assistance=reveal_assistance) for item in page]
    query = request.GET.copy()
    query.pop('format', None)
    query.pop('page', None)
    response = render(request, 'reports/report.html', {'heading': TITLES[kind], 'kind': kind,
        'form': form, 'columns': columns, 'rows': rows, 'page_obj': page, 'filter_query': query.urlencode(),
        'member_rows': member_rows(rows) if kind == 'members' else [],
        'report_rows': report_rows(kind, rows) if kind != 'members' else [],
        'page_numbers': list(page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1))
            if page is not None else []},
        status=200 if form.is_valid() else 400)
    response['Cache-Control'] = 'no-store, private'
    return response
