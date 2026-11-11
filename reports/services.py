"""Permission-scoped report projections shared by screen, CSV and PDF."""
import csv
from io import StringIO
from django.contrib.admin.models import LogEntry, CHANGE
from django.utils import timezone
from members.models import Member
from programs.models import Program, ProgramApplication
from assistance.models import AssistanceRelease
from assistance.services import VIEW_PERMISSIONS

PERMISSIONS = {
    'members': ('members.view_member',),
    'applications': ('programs.view_program', 'programs.view_programapplication'),
    'programs': ('programs.view_program',),
    'assistance': (*VIEW_PERMISSIONS, 'assistance.view_assistancerelease'),
}
TITLES = {'members': 'Members', 'applications': 'Applications', 'programs': 'Programs', 'assistance': 'Assistance'}


def report_data(kind, values):
    sources = {
        'members': (Member.objects.all(), 'joined_at__date',
                    ['Control number', 'Member', 'Joined', 'Status']),
        'applications': (ProgramApplication.objects.select_related('member', 'program', 'assistance_case'), 'submitted_at__date',
                         ['Reference', 'Member', 'Program', 'Submitted', 'Application status',
                          'Eligibility', 'Beneficiary selection', 'Release approval', 'Actually assisted']),
        'programs': (Program.objects.all(), 'created_at__date',
                     ['Program', 'Assistance type', 'Created', 'Registration closes', 'Slots', 'Status']),
        'assistance': (AssistanceRelease.objects.select_related('application__member', 'application__program'), 'released_on',
                       ['Member', 'Program', 'Assistance', 'Received on', 'Reference', 'Status']),
    }
    records, date_field, columns = sources[kind]
    if values.get('assistance_type') and kind != 'members':
        records = records.filter(**{('program__assistance_type' if kind == 'applications' else 'assistance_type'):
                                    values['assistance_type']})
    if kind == 'applications':
        from django.db.models import OuterRef, Subquery, Exists, Value, CharField
        from ewaf.operational_services import available
        from ewaf.operational_models import OperationalDecision
        records = records.annotate(received=Exists(AssistanceRelease.objects.successful().filter(application_id=OuterRef('pk'))))
        records = records.annotate(selection=Subquery(OperationalDecision.objects.filter(
            application_id=OuterRef('pk')).order_by('-revision').values('outcome')[:1])) if available() else records.annotate(
                selection=Value('', output_field=CharField()))
    for name, suffix in (('start', '__gte'), ('end', '__lte')):
        if values.get(name):
            records = records.filter(**{date_field + suffix: values[name]})
    if values.get('program'):
        lookup = 'pk' if kind == 'programs' else 'application__program' if kind == 'assistance' else 'program'
        records = records.filter(**{lookup: values['program'].pk})
    status = values.get('status')
    if kind == 'members' and status:
        records = records.filter(archived_at__isnull=status != 'archived')
        if status != 'archived':
            records = records.filter(is_active=status == 'active')
    elif kind == 'assistance':
        records = records.filter(voided_at__isnull=status != 'voided')
    elif status:
        records = records.filter(status=status)
    return records.order_by('-' + date_field.replace('__date', ''), 'pk'), columns


def display_date(value):
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M') if hasattr(value, 'hour') else value.isoformat()


def report_row(kind, item, *, reveal_assistance=False):
    if kind == 'members':
        return [item.control_number, item.full_name, display_date(item.joined_at), item.status.title()]
    if kind == 'applications':
        case = getattr(item, 'assistance_case', None)
        from programs.mandatory_ewaf import retained_selected_ids
        retained = item.pk in retained_selected_ids(item.program)
        selected = item.selection == 'SELECTED' if item.program.ewaf_applicable else bool(case and case.decision == 'approved')
        selected = selected or retained
        return [item.public_reference, item.member.full_name, item.program.name,
                display_date(item.submitted_at), item.get_status_display(),
                *(([
                    case.eligibility_label if case else 'Pending review',
                    ('Selected (previous approval)' if retained else (item.selection or 'Pending')) if item.program.ewaf_applicable else case.get_decision_display() if case else 'Pending',
                    'Recorded approval (current evidence required)' if selected else 'Not approved',
                    'Received' if item.received else 'Not received',
                ]) if reveal_assistance else ['Restricted'] * 4)]
    if kind == 'programs':
        return [item.name, item.assistance_type, display_date(item.created_at),
                display_date(item.registration_closes_at), item.slots if item.slots is not None else 'Not specified', item.get_status_display()]
    return [item.application.member.full_name, item.application.program.name, item.assistance_type,
            display_date(item.released_on), item.reference, 'Voided' if item.voided_at else 'Received']


def record_access(user, kind, format, values, count):
    # Audit filter scope and count, never export private row values into the log.
    LogEntry.objects.create(user=user, object_repr=f'{TITLES[kind]} report', action_flag=CHANGE,
        change_message=f'Report {format}; rows={count}; start={values.get("start") or ""}; '
                       f'end={values.get("end") or ""}; program={getattr(values.get("program"), "pk", "")}; '
                       f'status={values.get("status") or ""}; assistance_type={values.get("assistance_type") or ""}.')


def csv_bytes(columns, rows):
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        cells = [str(value if value is not None else '') for value in row]
        writer.writerow(["'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value for value in cells])
    return output.getvalue().encode('utf-8-sig')


def xlsx_bytes(columns, rows):
    """Literal text cells prevent names/references from becoming Excel formulas."""
    from io import BytesIO
    from itertools import chain
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('Report')
    sheet.freeze_panes = 'A2'
    for index in range(1, len(columns) + 1):
        sheet.column_dimensions[get_column_letter(index)].width = 28
    row_count = 0
    for row_count, values in enumerate(chain([columns], rows), 1):
        cells = []
        for value in values:
            cell = WriteOnlyCell(sheet, value=ILLEGAL_CHARACTERS_RE.sub('', str(value if value is not None else '')))
            cell.data_type = 's'
            if row_count == 1:
                cell.font = Font(bold=True, color='164E43')
                cell.fill = PatternFill('solid', fgColor='E8EFED')
            cells.append(cell)
        sheet.append(cells)
    sheet.auto_filter.ref = f'A1:{get_column_letter(len(columns))}{row_count}'
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
