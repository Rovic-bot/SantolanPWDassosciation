"""Add connected fictional intake examples without resetting existing lab data."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from core.demo_seed import TEST, upload, photo_review
from main_testing.seed import require_environment
from members.models import Member, DisabilityType
from programs.models import Program
from programs.services import submit_application
from ewaf.evidence import digest, source_context
from ewaf.operational_models import OperationalConfiguration, OperationalRun
from ewaf import operational_services as operation
from ewaf.weight_input import project
from .access import registered_name, verify_member
from .fixtures import create_program, configure, review_application
from .sources import review_si, review_token, collect_sources


def add_examples():
    require_environment()
    output = Path(settings.MEDIA_ROOT).parent / 'intake-demo.json'
    if output.exists():
        retained = json.loads(output.read_text(encoding='utf-8'))
        if Program.objects.filter(pk__in=[retained['public_program'], retained['ranking_program']]).count() == 2:
            print('Existing intake examples preserved: ' + str(output), flush=True)
            return retained
        # A baseline restore creates a new database and copies private assets.
        # Retain the copied metadata before creating matching examples there.
        output.replace(output.with_name('retained-intake-metadata-' + uuid4().hex + '.json'))
    actor = get_user_model().objects.get(username=settings.MAIN_TESTING_MANIFEST['admin_username'])
    now = timezone.now()
    names = ('EWAF Lab — Public Applications', 'EWAF Lab — Verified Program Sources')
    if Program.objects.filter(name__in=names).exists():
        raise RuntimeError('A partial intake example exists; inspect it before resuming. No existing records were changed.')
    public = create_program(actor, names[0])
    configure(public, actor)
    with patch('django.utils.timezone.now', return_value=now - timedelta(days=3)):
        closed = create_program(actor, names[1], closes=now - timedelta(days=1), slots=3)
        configuration = configure(closed, actor)
        applications = []
        members = list(Member.objects.filter(control_number__startswith='LAB-20261021-').order_by('control_number')[:6])
        for member, value in zip(members, ('90', '45', '40', '40', '55', '55')):
            grant = verify_member(closed.pk, control_number=member.control_number,
                full_name=registered_name(member),
                disability_types=DisabilityType.objects.filter(pk__in=member.disability_ids),
                disability_cause=member.disability_cause, disability_visibility=member.disability_visibility,
                version=closed.version)
            requirement = closed.configured_requirements.get(is_required=True)
            application = submit_application(closed.pk, grant=grant, data={'version': closed.version},
                files=MultiValueDict({'calendar_photo': [upload(portrait=True)],
                    f'requirement_{requirement.pk}': [upload('Fictional socioeconomic observation: ' + value + ' assessment units. ' + member.full_name)]}))
            photo_review(application, actor)
            review_application(application, actor)
            application.refresh_from_db()
            review_si(application.pk, user=actor, expected=review_token(application, configuration), state='VERIFIED',
                value=value, observation_start=timezone.localdate(), observation_end=timezone.localdate(), reason=TEST, confirmed=True)
            collect_sources(application.pk, user=actor, expected=digest(source_context(application)), reason=TEST, confirmed=True)
            applications.append(application)
    experiments = {}
    for emphasis in (None, 'SI', 'ES', 'PA', 'ND'):
        if emphasis:
            proposed = deepcopy(configuration.policy)
            codes = ['SI', 'ES', 'PA', 'ND']
            judgments, _, provenance = project({'order': [emphasis] + [c for c in codes if c != emphasis],
                'weights': {c: 7000 if c == emphasis else 1000 for c in codes}})
            proposed['weight_input'] = provenance
            configuration = operation.record_configuration(closed.pk, user=actor, expected=operation.configuration_token(closed),
                proposed=proposed, judgments=judgments, status='LOCKED', reason=TEST + ' Source-based weight comparison.', attested=True)
        run = operation.generate(closed.pk, user=actor, expected=operation.context(closed.pk, user=actor), reason=TEST, request_key=uuid4())
        ordered = operation.ordered(run)
        names_by_id = {str(app.pk): app.member.full_name for app in applications}
        experiments[emphasis or 'Balanced'] = {'run': run.pk, 'configuration': configuration.revision,
            'rankings': [{'member': names_by_id[row['application']], 'score': row['score_0_100']} for row in ordered]}
    member = members[0]
    result = {'public_program': str(public.pk), 'ranking_program': str(closed.pk),
        'applications': [str(app.pk) for app in applications], 'experiments': experiments,
        'public_member': {'control_number': member.control_number, 'disability_types': member.disability_ids,
            'cause': member.disability_cause, 'visibility': member.disability_visibility},
        'public_requirement': public.configured_requirements.get(is_required=True).pk}
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'public_program': result['public_program'], 'ranking_program': result['ranking_program'],
        'applications_added': 6, 'configuration_versions': 6, 'calculation_versions': 5}), flush=True)
    return result
