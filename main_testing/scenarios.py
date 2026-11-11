"""Add clearly separated unresolved and adversarial fictional review scenarios."""
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from members.models import Member
from programs.models import Program, ProgramApplication
from .seed import Builder, require_environment, TEST


def add_scenarios():
    require_environment()
    actor = get_user_model().objects.get(username=settings.MAIN_TESTING_MANIFEST['admin_username'])
    builder = Builder(actor)
    path = Path(settings.MEDIA_ROOT).parent / 'dataset.json'
    builder.result = json.loads(path.read_text(encoding='utf-8'))
    if builder.result.get('special_scenarios_complete'):
        return
    builder.members = list(Member.objects.order_by('pk'))
    builder.programs = list(Program.objects.all())
    builder.applications = {str(program.pk): list(program.applications.all()) for program in builder.programs}
    pending = builder.make_program('EWAF Lab — Pending Evidence', 'Healthcare & Medical Aid', 3)
    for index, photo in enumerate(('VERIFIED', None, 'REJECTED', 'NEEDS_RESUBMISSION', 'VERIFIED')):
        builder.apply(pending, builder.members[1750 + index], photo=photo, outcome='review' if index == 0 else None)
    builder.configure(pending)
    builder.scenarios()
    try:
        builder.calculate(pending)
    except ValidationError as error:
        builder.result['blocked'].append({'program': str(pending.pk), 'scenario': 'Unresolved evidence blocks complete pool', 'reasons': error.messages})
    else:
        raise AssertionError('Incomplete pool calculated')
    cutoff = builder.make_program('EWAF Lab — Cutoff Review', 'Assistive Devices', 3)
    late = builder.apply(cutoff, builder.members[1760])
    # Explicit adversarial imported-inventory fixture, never a permitted late intake.
    # No score/rank/review state is fabricated; the actual engine must reject it.
    ProgramApplication.objects.filter(pk=late.pk).update(submitted_at=builder.now)
    builder.configure(cutoff)
    builder.assess(late)
    try:
        builder.calculate(cutoff)
    except ValidationError as error:
        assert any('APPLICATION_SUBMITTED_AFTER_APPROVED_CLOSE' in value for value in error.messages)
        builder.result['blocked'].append({'program': str(cutoff.pk), 'scenario': 'Adversarial retained late-inventory fixture', 'reasons': error.messages})
    else:
        raise AssertionError('After-cutoff fixture calculated')
    required = builder.members[1770].disability_ids[0]
    qualification = builder.make_program('Mobility Device Assistance — Qualification Review', 'Assistive Devices', 5,
                                          ewaf=False, disability_ids=[required], close=90)
    matching = [member for member in builder.members[1700:] if required in member.disability_ids][:8]
    for member in matching:
        builder.apply(qualification, member)
    mismatch = next(member for member in builder.members[1700:] if required not in member.disability_ids)
    try:
        builder.apply(qualification, mismatch)
    except ValidationError:
        builder.result['blocked'].append({'program': str(qualification.pk), 'scenario': 'Disability mismatch prevents submission; no fabricated rejected application'})
    else:
        raise AssertionError('Disability mismatch accepted')
    from membership.models import MembershipApplication
    from programs.services import verify_member
    intake = MembershipApplication.objects.filter(status='pending').first()
    try:
        verify_member(qualification.pk, version=qualification.version, control_number=intake.control_number,
            full_name=intake.full_name, birthdate=intake.birthdate, contact_number=intake.contact_number)
    except ValidationError:
        builder.result['blocked'].append({'scenario': 'Unapproved membership cannot submit a program application'})
    else:
        raise AssertionError('Unverified membership accepted')
    from members.services import change_status
    for index, member in enumerate(builder.members[1790:1800]):
        change_status(member.pk, user=actor, version=member.version, status='inactive' if index < 5 else 'archived', notes=TEST)
    from core.content import DEFAULTS, save_content
    for key, (title, body) in DEFAULTS.items():
        save_content(key, user=actor, data={'version': 0, 'title': title,
            'body': 'Fictional local testing information.\n\n' + body,
            'action': 'publish', 'reason': TEST, 'confirm': True})
    builder.result['special_scenarios_complete'] = True
    builder.finish()
