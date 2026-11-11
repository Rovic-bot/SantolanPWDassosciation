"""Read-only guidance before staff enter claimant details; the writer rechecks."""
from .models import AssistanceCase


def receipt_blocker(application):
    program = application.program
    if application.assistance_releases.successful().exists():
        return 'Actual receipt has already been recorded for this beneficiary. Review the saved receipt details.'
    if program.ewaf_applicable:
        from ewaf.operational_models import OperationalRun, OperationalDecision
        from ewaf.operational_services import available, delivery_decision_problem
        if not available():
            return 'Complete EWAF calculation and beneficiary selection before recording receipt.'
        run = OperationalRun.objects.filter(program=program).first()
        decision = OperationalDecision.objects.filter(application=application).first()
        problem = delivery_decision_problem(run, decision)
        if problem:
            return problem
    elif not AssistanceCase.objects.filter(application=application, decision='approved').exists():
        return 'Record an approved beneficiary decision before recording receipt.'
    from announcements.release_publication import published_selection, MESSAGE
    if application.public_reference not in published_selection(program)[0]:
        return MESSAGE
    return ''
