"""Audited eligibility/decision sources and complete cross-program receipt scope."""
from functools import wraps
from inspect import signature

from django.core.exceptions import PermissionDenied, ValidationError


def assistance_writer(operation):
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            expected = kwargs.pop('source_expected', None)
            if not enlisted():
                if expected is not None:
                    raise PermissionDenied('Source tokens require a registered disposable session.')
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from django.db.models import Q
            from assistance.models import AssistanceCase, AssistanceLog, AssistanceRelease, EligibilityStatus
            from assistance.services import case_snapshot
            from members.models import Member
            from programs.models import (ProgramApplication, ProgramDocument, ApplicationPhoto, PhotoVerification)
            from documents.models import MembershipApplicationDocument, DocumentVerification
            from .member_invalidation import member_programs
            from .shared_invalidation import source_fence, finish, audit_history, audit_delta

            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            reference = arguments['reference']
            def resolve():
                app = ProgramApplication.objects.get(pk=reference)
                return member_programs(app.member_id) if operation in ('release', 'void') else [app.program_id]
            with source_fence(arguments['user'], expected, resolve) as (actor, authority, states):
                arguments['user'] = actor
                app = ProgramApplication.objects.get(pk=reference)
                scope = (Q(member_id=app.member_id) if operation in ('release', 'void') else
                         Q(program_id=app.program_id) if operation == 'decision' else Q(pk=app.pk))
                applications = list(ProgramApplication.objects.select_for_update().filter(scope).order_by('pk'))
                member_ids = sorted({row.member_id for row in applications})
                members = [Member.objects.select_for_update().get(pk=pk) for pk in member_ids]
                app = next(row for row in applications if row.pk == app.pk)
                member = next(row for row in members if row.pk == app.member_id)
                # Take ordered leaves before invoking existing helpers that revisit them.
                list(EligibilityStatus.objects.select_for_update().order_by('pk'))
                document_ids = list(MembershipApplicationDocument.objects.filter(
                    application_id=member.application_id).values_list('pk', flat=True))
                list(MembershipApplicationDocument.objects.select_for_update().filter(pk__in=document_ids).order_by('pk'))
                list(DocumentVerification.objects.select_for_update().filter(document_id__in=document_ids).order_by('pk'))
                list(ProgramDocument.objects.select_for_update().filter(application=app).order_by('pk'))
                photos = list(ApplicationPhoto.objects.select_for_update().filter(application=app).order_by('pk'))
                list(PhotoVerification.objects.select_for_update().filter(photo_id__in=[p.pk for p in photos]).order_by('pk'))
                case = AssistanceCase.objects.select_for_update().filter(application=app).first()
                list(AssistanceRelease.objects.select_for_update().filter(application=app).order_by('pk'))
                before_case = case_snapshot(case) if case else None
                before_releases = {str(row['id']): row for row in AssistanceRelease.objects.order_by('pk').values()}
                history = audit_history(AssistanceLog)
                result = function(*bound.args, **bound.kwargs)
                current = ProgramApplication.objects.get(pk=app.pk)
                case = AssistanceCase.objects.get(application=app)
                logs = audit_delta(AssistanceLog, history)
                if (len(logs) != 1 or current.member_id != member.pk or current.program_id != app.program_id or
                        current.version != app.version + 1 or result.application_id != app.pk):
                    raise ValidationError('ASSISTANCE_MUTATION_SCOPE')
                after_case = case_snapshot(case)
                notes = arguments['data']['notes'].strip()
                if operation in ('eligibility', 'decision'):
                    if result.pk != case.pk:
                        raise ValidationError('ASSISTANCE_CASE_RESULT')
                    action = 'eligibility_reviewed' if operation == 'eligibility' else 'decision_recorded'
                    snapshot = {'before': before_case, 'after': after_case}
                    if operation == 'eligibility':
                        expected_status = {'eligible': 'ELIGIBLE', 'ineligible': 'INELIGIBLE',
                            'review': 'NEEDS_INFORMATION', 'pending': 'ELIGIBILITY_REVIEW'}[case.eligibility_id]
                        if arguments.get('direct_review') and app.status == 'COMPLETED':
                            from assistance.reassessment import completed_receipt, review_witness
                            _, witness = completed_receipt(current)
                            snapshot['completed_reassessment'] = review_witness(current, witness)
                            expected_status = 'COMPLETED'
                        if (case.reviewed_by_id != actor.pk or case.decision != 'pending' or
                                case.eligibility_id != arguments['data']['eligibility'] or
                                current.status != expected_status):
                            raise ValidationError('ASSISTANCE_ELIGIBILITY_RESULT')
                    else:
                        program = app.program
                        if (case.decided_by_id != actor.pk or case.decision != arguments['data']['decision'] or
                                current.status != {'approved': 'SELECTED', 'rejected': 'NOT_SELECTED',
                                    'pending': 'ELIGIBILITY_REVIEW'}[case.decision]):
                            raise ValidationError('ASSISTANCE_DECISION_RESULT')
                        snapshot.update(ranking_run=None, selection_method=program.selection_method,
                            policy_authorized_at=program.policy_authorized_at.isoformat() if program.policy_authorized_at else None)
                    if before_releases != {str(row['id']): row for row in AssistanceRelease.objects.order_by('pk').values()}:
                        raise ValidationError('ASSISTANCE_UNEXPECTED_RECEIPT_CHANGE')
                else:
                    release = AssistanceRelease.objects.get(pk=result.pk, application=app)
                    after_releases = {str(row['id']): row for row in AssistanceRelease.objects.order_by('pk').values()}
                    if any(after_releases.get(key) != row for key, row in before_releases.items()
                           if operation != 'void' or key != str(release.pk)):
                        raise ValidationError('ASSISTANCE_RECEIPT_HISTORY_CHANGED')
                    if operation == 'release':
                        if (set(after_releases) - set(before_releases) != {str(release.pk)} or
                                release.active_application_id != app.pk or release.recorded_by_id != actor.pk or
                                release.voided_at is not None or current.status != 'COMPLETED' or after_case != before_case):
                            raise ValidationError('ASSISTANCE_RELEASE_RESULT')
                        action = 'assistance_released'
                        snapshot = {'release': str(release.pk), 'assistance_type': release.assistance_type,
                            'benefit': release.benefit, 'amount': str(release.amount) if release.amount is not None else None,
                            'estimated_value': str(release.estimated_value) if release.estimated_value is not None else None,
                            'released_on': str(release.released_on), 'reference': release.reference, 'approval': release.approval_snapshot}
                    else:
                        old_release = before_releases.get(str(release.pk))
                        if (not old_release or old_release['voided_at'] is not None or
                                set(after_releases) != set(before_releases) or release.active_application_id is not None or
                                not release.voided_at or release.voided_by_id != actor.pk or release.void_reason != notes or
                                current.status != 'NEEDS_INFORMATION' or case.decision != 'pending' or case.eligibility_id != 'review'):
                            raise ValidationError('ASSISTANCE_VOID_RESULT')
                        mutable = {'voided_at', 'voided_by_id', 'void_reason', 'active_application_id'}
                        if any(after_releases[str(release.pk)][key] != value for key, value in old_release.items() if key not in mutable):
                            raise ValidationError('ASSISTANCE_VOID_CHANGED_RECEIPT')
                        action, snapshot = 'release_voided', {'release': str(release.pk), 'after': after_case}
                log = logs[0]
                address = AssistanceLog._meta.get_field('address').get_prep_value(arguments['address'] or None)
                if (log.application_id, log.actor_id, log.actor_label, log.action, log.notes, log.snapshot, log.address) != (
                        app.pk, actor.pk, actor.get_username(), action, notes, snapshot, address):
                    raise ValidationError('ASSISTANCE_NATIVE_AUDIT_INVALID')
                finish(states, authority, expected, actor=actor, kind='assistance', source_id=app.pk, audits=logs)
                return result
        return wrapped
    return decorate
