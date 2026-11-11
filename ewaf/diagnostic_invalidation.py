"""Conservative Gate 1 audit-dependency integration for retained diagnostics."""
from functools import wraps
from inspect import signature

from django.core.exceptions import PermissionDenied, ValidationError


def diagnostic_writer(argument):
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
            from members.models import Member
            from programs.models import ProgramApplication, ProgramLog
            from .models import CriterionAssessment, CalculationDiagnosticRun
            from .shared_invalidation import source_fence, finish, audit_history, audit_delta
            from .scoring_services import validate_run

            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            reference = arguments[argument]
            resolve = lambda: [ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)]
            with source_fence(arguments['user'], expected, resolve) as (actor, authority, states):
                arguments['user'] = actor
                app = ProgramApplication.objects.select_for_update().get(pk=reference)
                Member.objects.select_for_update().get(pk=app.member_id)
                list(CriterionAssessment.objects.select_for_update().filter(application=app).order_by('pk'))
                history = audit_history(ProgramLog)
                result = function(*bound.args, **bound.kwargs)
                result.clean()
                artifacts = [result]
                if isinstance(result, CalculationDiagnosticRun):
                    validate_run(result)
                    artifacts += list(result.items.all())
                    artifacts += [trace for item in result.items.all() for trace in item.traces.all()]
                logs = audit_delta(ProgramLog, history)
                if ({row.pk for row in logs} != {row.audit_entry_id for row in artifacts} or
                        len(logs) != len(artifacts) or any(row.program_id != app.program_id or row.actor_id != actor.pk
                                                         for row in artifacts)):
                    raise ValidationError('DIAGNOSTIC_NATIVE_AUDIT_SCOPE')
                for row in artifacts:
                    row.clean()
                finish(states, authority, expected, actor=actor, kind='diagnostic', source_id=result.pk, audits=logs)
                return result
        return wrapped
    return decorate
