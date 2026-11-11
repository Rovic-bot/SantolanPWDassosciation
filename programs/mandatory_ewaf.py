"""Mandatory EWAF and read-only witnesses for outcomes issued before adoption."""
from copy import copy
import hashlib
import json

CONTRACT = 'mandatory-ewaf-2026-11-10'
ACTION = 'ewaf_required'


def approval_fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def adoption(program):
    if program._state.adding:
        return None
    row = program.history.filter(action=ACTION).order_by('occurred_at', 'pk').first()
    return row if row and row.changes.get('contract') == CONTRACT else None


def retained_all_types(program):
    if program._state.adding or program.eligible_disability_types.exists():
        return False
    row = adoption(program)
    return bool(row and row.changes.get('previously_all_disability_types'))


def has_required_types(program):
    return program.eligible_disability_types.exists() or retained_all_types(program)


def retained_selected_ids(program):
    row = adoption(program)
    if not row or row.changes.get('ewaf_applicable', {}).get('before') is not False:
        return set()
    return set(program.applications.filter(pk__in=row.changes.get('retained_selection_ids', []),
        status__in=('SELECTED', 'COMPLETED'), assistance_case__decision='approved',
        assistance_case__decided_at__lte=row.occurred_at).values_list('pk', flat=True))


def retained_receipt(receipt):
    row = adoption(receipt.application.program)
    return bool(row and row.changes.get('ewaf_applicable', {}).get('before') is False
        and receipt.recorded_at <= row.occurred_at
        and row.changes.get('retained_receipts', {}).get(str(receipt.pk))
            == approval_fingerprint(receipt.approval_snapshot))


def publication_source_program(program, revision):
    """Ignore only the adoption version bump for an already-issued publication."""
    row = adoption(program)
    if (row and row.changes.get('ewaf_applicable', {}).get('before') is False
            and program.version == row.changes['version']['after']
            and revision.pk in row.changes.get('retained_result_revisions', [])
            and revision.created_at <= row.occurred_at):
        prior = copy(program)
        prior.version = row.changes['version']['before']
        prior.ewaf_applicable = False
        return prior
    return program


def adopt_existing_programs(apps, schema_editor):
    """One-time, auditable conversion; never recalculate or rewrite outcomes."""
    from django.db import transaction
    Program = apps.get_model('programs', 'Program')
    Log = apps.get_model('programs', 'ProgramLog')
    Release = apps.get_model('assistance', 'AssistanceRelease')
    Revision = apps.get_model('announcements', 'ProgramResultRevision')
    TermsLock = apps.get_model('programs', 'ProgramTermsLock')
    alias = schema_editor.connection.alias
    with transaction.atomic(using=alias):
        TermsLock.objects.using(alias).get_or_create(pk=1)
        TermsLock.objects.using(alias).select_for_update().get(pk=1)
        for program in Program.objects.using(alias).select_for_update().order_by('pk'):
            if Log.objects.using(alias).filter(program_id=program.pk, action=ACTION).exists():
                continue
            all_types = not program.eligible_disability_types.exists()
            if program.ewaf_applicable and not all_types:
                continue
            before, version = program.ewaf_applicable, program.version
            selections = list(program.applications.filter(status__in=('SELECTED', 'COMPLETED'),
                assistance_case__decision='approved').values_list('pk', flat=True)) if not before else []
            receipts = {str(row.pk): approval_fingerprint(row.approval_snapshot)
                for row in Release.objects.using(alias).filter(application__program_id=program.pk)} if not before else {}
            revisions = list(Revision.objects.using(alias).filter(announcement__program_id=program.pk)
                .values_list('pk', flat=True)) if not before else []
            if not before:
                program.ewaf_applicable = True
                program.version += 1
                program.save(using=alias, update_fields=['ewaf_applicable', 'version'])
            Log.objects.using(alias).create(program_id=program.pk, action=ACTION,
                actor_label='System maintenance',
                notes='Owner required EWAF for every program. Existing capacities, qualifications, decisions, '
                      'publications and actual receipts are retained. Future selection requires EWAF.',
                changes={'contract': CONTRACT, 'ewaf_applicable': {'before': before, 'after': True},
                    'version': {'before': version, 'after': program.version},
                    'previously_all_disability_types': all_types,
                    'retained_selection_ids': [str(pk) for pk in selections],
                    'retained_receipts': receipts, 'retained_result_revisions': revisions})
