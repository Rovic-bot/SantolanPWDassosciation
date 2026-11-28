"""Historical receipt fixtures, restricted to a verified disposable database."""
from django.utils import timezone
from scripts.durable_test_runner import require_disposable
from .models import AssistanceCase, AssistanceLog, AssistanceRelease
from .services import case_snapshot


def historical_selection(application, user, *, selected=True):
    """Fictional pre-adoption decision for retained-record tests only."""
    require_disposable()
    assert user.is_superuser and not application.program.ewaf_applicable
    case, _ = AssistanceCase.objects.update_or_create(
        application=application, defaults=dict(eligibility_id='eligible', eligibility_label='Eligible',
        checklist=[{'key': 'membership', 'label': 'Active membership', 'required': True, 'result': 'pass'},
                   {'key': 'other_requirements', 'label': 'Program requirements', 'required': True, 'result': 'pass'}],
        reviewed_at=timezone.now(), reviewed_by=user,
        review_notes='SYNTHETIC retained assessment before mandatory EWAF.',
        member_version=application.member.version, program_version=application.program.version,
        decision='approved' if selected else 'rejected', decision_notes='SYNTHETIC retained human decision.',
        decided_at=timezone.now(), decided_by=user))
    application.status = 'SELECTED' if selected else 'NOT_SELECTED'
    application.save(update_fields=['status'])
    AssistanceLog.objects.create(application=application, actor=user, actor_label=user.username,
        action='historical_selection', notes=case.decision_notes, snapshot=case_snapshot(case))
    return case


def historical_receipt(application, user):
    """Represent an already-issued receipt; never replay a retired approval flow."""
    require_disposable()
    assert user.is_superuser and not application.program.ewaf_applicable
    assert not AssistanceRelease.objects.filter(active_application=application).exists()
    case, _ = AssistanceCase.objects.update_or_create(application=application, defaults={
        'eligibility_id': 'eligible', 'eligibility_label': 'Eligible',
        'reviewed_at': timezone.now(), 'reviewed_by': user,
        'review_notes': 'SYNTHETIC retained assessment before mandatory EWAF.',
        'member_version': application.member.version, 'program_version': application.program.version,
        'decision': 'approved', 'decision_notes': 'SYNTHETIC retained human decision.',
        'decided_at': timezone.now(), 'decided_by': user})
    snapshot = case_snapshot(case)
    release = AssistanceRelease.objects.create(
        application=application, active_application=application,
        assistance_type='Synthetic previous assistance', benefit='Synthetic delivered support',
        amount='500.00', released_on=timezone.localdate(), recorded_by=user,
        notes='SYNTHETIC historical receipt for prior-assistance tests only.',
        approval_snapshot=snapshot)
    application.status = 'COMPLETED'
    application.save(update_fields=['status'])
    AssistanceLog.objects.create(application=application, actor=user, actor_label=user.username,
        action='release_recorded', notes=release.notes, snapshot={'approval': snapshot})
    return release
