"""Audited program details/date corrections before scoring or final outcomes."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Min, Max
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.utils.formats import date_format
from core.permissions import require_workspace_permissions
from events.services import check_notes, check_version
from .models import Program
from .terms import terms_lock


DATE_FIELDS = frozenset(('registration_opens_at', 'registration_closes_at',
    'starts_at', 'ends_at', 'resubmission_closes_at'))
EDITABLE_FIELDS = DATE_FIELDS | {'name', 'description', 'assistance_type', 'benefit', 'slots'}


def eligibility_schedule_witness(application, case):
    """Retain an existing review across proven date-only configuration changes.

    No eligibility review, program version or audit is rewritten. Unexplained
    version changes and any changed non-date term still require renewed review.
    """
    from copy import deepcopy
    from ewaf.evidence import digest
    from ewaf.operational_models import OperationalConfiguration
    from .models import ProgramLog
    program = application.program
    if not case or not case.reviewed_at or not 0 < program.version - case.program_version <= 100:
        return {}
    logs = list(ProgramLog.objects.filter(program=program, application__isnull=True,
        action='updated', occurred_at__gt=case.reviewed_at).order_by('occurred_at', 'pk'))
    if len(logs) != program.version - case.program_version:
        return {}
    dates = {key: getattr(program, key) for key in DATE_FIELDS}
    from django.db.models import Q
    bindings = list(OperationalConfiguration.objects.filter(
        Q(dataset_policy__isnull=False) | Q(policy__has_key='fixed_scoring_version'), program=program,
        recorded_at__gte=case.reviewed_at,
        reason__startswith='Retained the same approved scoring policy after an authorized schedule correction.')
        .select_related('previous', 'audit_entry'))
    witnesses, used = [], set()
    for log in reversed(logs):
        if not log.actor_id or not log.changes or not set(log.changes) <= DATE_FIELDS:
            return {}
        parsed = {}
        try:
            for key, change in log.changes.items():
                if set(change) != {'before', 'after'}:
                    return {}
                before, after = (None if change[side] in (None, 'None') else parse_datetime(change[side])
                                 for side in ('before', 'after'))
                if any(change[side] not in (None, 'None') and value is None
                       for side, value in (('before', before), ('after', after))):
                    return {}
                if any(value is not None and timezone.is_naive(value) for value in (before, after)):
                    return {}
                if before == after or dates[key] != after:
                    return {}
                parsed[key] = (before, after)
        except (TypeError, ValueError):
            return {}
        match = None
        for row in bindings:
            if (row.pk in used or not row.previous_id or row.actor_id != log.actor_id
                    or row.recorded_at > log.occurred_at or row.dataset_policy_id != row.previous.dataset_policy_id):
                continue
            if row.policy.get('fixed_scoring_version') and (row.policy != row.previous.policy
                    or row.validation != row.previous.validation):
                continue
            try:
                row.clean(); row.previous.clean()
                old, new = deepcopy(row.previous.source), deepcopy(row.source)
                from .terms import terms_digest
                for source in (old, new):
                    retained_digest = terms_digest(source['terms'])
                    if (source.pop('program_terms_digest') != retained_digest or
                            source['approval'].pop('actual_terms_digest') != retained_digest):
                        raise ValidationError('The signed program terms need review.')
                old_program, new_program = old['terms']['program'], new['terms']['program']
                for key, (before, after) in parsed.items():
                    old_value, new_value = old_program.pop(key), new_program.pop(key)
                    if (parse_datetime(old_value) if old_value else None) != before or (parse_datetime(new_value) if new_value else None) != after:
                        break
                else:
                    if old == new:
                        match = row
                        break
            except (ValidationError, KeyError, TypeError, ValueError):
                continue
        if match is None:
            return {}
        used.add(match.pk)
        witnesses.append({'log': log.pk, 'changes_digest': digest(log.changes),
                          'configuration': match.pk, 'configuration_digest': match.digest})
        dates.update({key: before for key, (before, _) in parsed.items()})
    return {'contract': 'eligibility-date-only-revision-v1', 'review_program_version': case.program_version,
            'current_program_version': program.version, 'witnesses': list(reversed(witnesses))}


def validate_schedule(program, values):
    """Read-only preflight, repeated under the writer's terms/program locks."""
    from ewaf.models import RankingRun, CalculationDiagnosticRun
    from ewaf.operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
    from ewaf.revised.live_models import DatasetInputReview
    from ewaf.vault_models import RegisteredInputReview
    if (settings.PDAO_ENFORCEMENT_ENABLED or program.pdao_approval_records.exists()
            or program.approval_bindings.exists()):
        raise ValidationError('These program details are protected by external approval. A renewed approval is required before changing them.')
    if program.status not in ('draft', 'published'):
        raise ValidationError('Program details cannot be updated while this program is cancelled or archived.')
    if (OperationalRun.objects.filter(program=program).exists()
            or RankingRun.objects.filter(program=program).exists()
            or CalculationDiagnosticRun.objects.filter(program=program).exists()
            or OperationalDecision.objects.filter(program=program).exists()
            or program.applications.filter(status__in=('EWAF_PROCESSED', 'RANKED', 'SELECTED',
                'WAITLISTED', 'NOT_SELECTED', 'COMPLETED')).exists()
            or program.applications.filter(assistance_case__decision__in=('approved', 'rejected')).exists()
            or program.applications.filter(assistance_releases__isnull=False).exists()):
        raise ValidationError('This program already has scoring or final outcome records. Its approved details must be preserved.')
    if (DatasetInputReview.objects.filter(program=program, state='ACCEPTED').exists()
            or RegisteredInputReview.objects.filter(program=program).exists()):
        raise ValidationError('Scoring inputs have already been accepted for this schedule. Their assessment period must be preserved.')
    submitted = program.applications.aggregate(first=Min('submitted_at'), last=Max('submitted_at'))
    opens = values.get('registration_opens_at', program.registration_opens_at)
    closes = values.get('registration_closes_at', program.registration_closes_at)
    if submitted['first'] and opens and opens > submitted['first']:
        raise ValidationError({'registration_opens_at': 'Registration must open no later than the first existing application.'})
    if submitted['last'] and closes and closes < submitted['last']:
        earliest = submitted['last'].replace(second=0, microsecond=0)
        if earliest < submitted['last']:
            earliest += timedelta(minutes=1)
        earliest = timezone.localtime(earliest, timezone.get_fixed_timezone(480))
        raise ValidationError({'registration_closes_at':
            'Registration cannot close before an existing application was submitted. '
            f'Choose {date_format(earliest, "M j, Y, g:i A")} or later (Philippine time).'})
    configuration = OperationalConfiguration.objects.filter(program=program).first()
    cutoff = None
    if configuration and configuration.uses_dataset_scoring:
        from ewaf.revised.live_services import require_binding
        require_binding(configuration)
        cutoff = (closes if configuration.assessment_cutoff == program.registration_closes_at
                  else configuration.assessment_cutoff)
        if closes and cutoff and cutoff < closes:
            raise ValidationError({'registration_closes_at': 'Registration must close by the separately approved assessment cutoff.'})
        if cutoff and cutoff >= parse_datetime(configuration.policy['effective_until']):
            raise ValidationError({'registration_closes_at': 'The closing time must fall within the approved scoring policy period.'})
    elif configuration:
        from ewaf.vault_policy import scoring_pending
        if not scoring_pending(configuration.policy):
            raise ValidationError('This retained scoring method requires its original schedule and configuration.')
        from ewaf.intake_policy import require_configuration
        require_configuration(program)
    return configuration, cutoff


@terms_lock()
@transaction.atomic
def update_program_schedule(pk, *, user, values, address=None):
    from .services import record_log
    require_workspace_permissions(user, 'programs.view_program', 'programs.change_program', 'programs.publish_program')
    program = Program.objects.select_for_update().get(pk=pk)
    check_version(program, values['version'])
    check_notes(values['notes'])
    configuration, cutoff = validate_schedule(program, values)
    before = {name: getattr(program, name) for name in EDITABLE_FIELDS}
    for name in EDITABLE_FIELDS:
        if name in values:
            setattr(program, name, values[name])
    program.full_clean()
    changes = {name: {'before': str(value), 'after': str(getattr(program, name))}
               for name, value in before.items() if value != getattr(program, name)}
    if not changes:
        return program
    program.version += 1
    program.updated_by = user
    program.save(update_fields=[*EDITABLE_FIELDS, 'version', 'updated_by', 'updated_at'])
    if configuration and configuration.policy.get('fixed_scoring_version'):
        from ewaf.fixed_scoring import bind
        bind(program, user=user, rebind=True, reason=(
            ('Retained the same approved scoring policy after an authorized schedule correction. '
             if set(changes) <= DATE_FIELDS else
             'Retained the same approved scoring policy after an authorized program details correction. ')
            + values['notes'].strip())[:2000])
    elif configuration and configuration.dataset_policy_id:
        from ewaf.revised.live_services import store_binding
        store_binding(program, configuration, configuration.dataset_policy, cutoff, user=user,
            reason=(('Retained the same approved scoring policy after an authorized schedule correction. '
                    if set(changes) <= DATE_FIELDS else
                    'Retained the same approved scoring policy after an authorized program details correction. ')
                    + values['notes'].strip())[:2000])
    elif configuration:
        from ewaf.intake_policy import prepare
        prepare(program, configuration, user=user)
    record_log(program, 'updated', values['notes'].strip(), user=user, address=address, changes=changes)
    return program
