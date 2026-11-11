"""Fictional-only scenario builder. Every score comes from the real EWAF services."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, localcontext
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

TEST = 'TEST ONLY — fictional local demonstration; no Association or external approval.'
ROLES = ('functional_need', 'consent', 'accessible_alternative')
NAMES = ('Amihan', 'Bituin', 'Cielo', 'Dalisay', 'Elio', 'Fiora', 'Giliw', 'Hiraya',
         'Isla', 'Juno', 'Kislap', 'Liora', 'Mithi', 'Nilo', 'Orion', 'Pia',
         'Quilo', 'Raya', 'Sinta', 'Tala', 'Ulani', 'Vela', 'Wilo', 'Xara',
         'Yumi', 'Zeno', 'Aster', 'Brisa', 'Coral', 'Dewi')


def upload(label='Fictional evidence', portrait=False):
    if portrait:
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (400, 400), '#e6efec')
        draw = ImageDraw.Draw(image)
        draw.ellipse((140, 60, 260, 180), fill='#73988c')
        draw.rounded_rectangle((80, 200, 320, 350), radius=40, fill='#73988c')
        draw.text((125, 365), 'TEST ONLY - NOT A PERSON', fill='#183a30')
        output = BytesIO()
        image.save(output, format='PNG')
        return SimpleUploadedFile('test-only.png', output.getvalue(), content_type='image/png')
    from core.pdf import render_pdf
    return SimpleUploadedFile('test-only.pdf', render_pdf(label, subtitle=TEST),
                              content_type='application/pdf')


def approve_terms(program, actor):
    from programs.binding_services import capture_terms, bind_approval
    from programs.approval_services import record_pdao_approval
    from programs.terms import snapshot_terms, terms_digest
    from programs.models import ProgramApprovalControl
    program.refresh_from_db()
    control = ProgramApprovalControl.objects.filter(program=program).first()
    revision = capture_terms(program.pk, user=actor, version=control.version if control else 0,
        program_version=program.version, digest=terms_digest(snapshot_terms(program)), reason=TEST, confirmed=True)
    prior = program.pdao_approval_records.first()
    approval = record_pdao_approval(program.pk, user=actor, data={
        'kind': 'official', 'approval_date': timezone.localdate(),
        'signatory': 'TEST ONLY simulated signatory — no external approval',
        'manual_confirmation': True, 'reason': TEST, 'expected_version': prior.version if prior else 0,
        'expected_program_version': program.version})
    control = ProgramApprovalControl.objects.get(program=program)
    bind_approval(program.pk, user=actor, version=control.version, program_version=program.version,
        revision_id=revision.pk, approval_id=approval.pk, approval_version=approval.version,
        reason=TEST, confirmed=True)


def review(application, actor, outcome='eligible', *, failing=False):
    from assistance.services import review_eligibility
    application.refresh_from_db()
    application.member.refresh_from_db()
    application.program.refresh_from_db()
    data = {'version': application.version, 'member_version': application.member.version,
            'program_version': application.program.version, 'eligibility': outcome,
            'other_requirements': 'fail' if failing else ('review' if outcome == 'review' else 'pass'),
            'notes': TEST + (' Documented functional-need qualification failure.' if failing else ' Evidence reviewed.')}
    data.update({f'check_{item["id"]}': 'pass' for item in application.requirements_snapshot})
    return review_eligibility(application.pk, user=actor, data=data)


def photo_review(application, actor, outcome='VERIFIED'):
    from programs.workflow import review_photo
    application.refresh_from_db()
    return review_photo(application.pk, user=actor, data={'version': application.version,
        'photo_id': application.current_photo_id, 'outcome': outcome, 'category': 'TEST evidence review',
        'reason': TEST, 'confirm': True})


def receive(application, actor, reference):
    from assistance.services import record_release
    application.refresh_from_db()
    return record_release(application.pk, user=actor, data={'version': application.version,
        'assistance_type': application.program.assistance_type, 'benefit': 'Fictional demonstration package',
        'released_on': timezone.localdate(), 'reference': reference, 'notes': TEST, 'confirm': True})


def assert_blocked(operation, label, outcomes):
    try:
        operation()
    except ValidationError as error:
        outcomes.append({'scenario': label, 'blocked': True, 'reasons': error.messages})
    else:
        raise AssertionError(label + ' should have been blocked')


def counts():
    from members.models import Member
    from membership.models import MembershipApplication
    from programs.models import Program, ProgramApplication
    from announcements.models import Announcement
    from assistance.models import AssistanceRelease
    from ewaf.operational_models import OperationalRun
    return {'members': Member.objects.count(), 'onsite_registrations': MembershipApplication.objects.count(),
            'programs': Program.objects.count(), 'applications': ProgramApplication.objects.count(),
            'announcements': Announcement.objects.count(), 'calculations': OperationalRun.objects.count(),
            'confirmed_receipts': AssistanceRelease.objects.successful().count(),
            'voided_receipts': AssistanceRelease.objects.filter(voided_at__isnull=False).count()}


def seed():
    if not getattr(settings, 'EWAF_FICTIONAL_DEMO', False) or not hasattr(settings, 'DEMO_MANIFEST'):
        raise CommandError('Fictional data requires the isolated demo settings and manifest.')
    directory = Path(settings.MEDIA_ROOT).parent
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / 'dataset.json'
    if manifest.exists():
        result = json.loads(manifest.read_text(encoding='utf-8'))
        return {**result, 'current_counts': counts(), 'idempotent': True}
    from members.models import Member
    from membership.models import MembershipApplication
    from programs.models import Program
    from announcements.models import Announcement
    if any(model.objects.exists() for model in (Member, MembershipApplication, Program, Announcement)):
        raise CommandError('Unlabelled records exist. Refusing deletion; --reset creates another empty isolated workspace.')
    actor = get_user_model().objects.filter(is_superuser=True, is_active=True, is_staff=True).first()
    if actor is None:
        raise CommandError('A retained active Admin account is required; existing accounts will not be modified.')
    with transaction.atomic():
        result = build(actor)
    result['counts'] = counts()
    manifest.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    return result


def build(actor):
    from members.models import Member, DisabilityType
    from membership.models import MembershipApplication
    from members.profile import INCOME, EMPLOYMENT, EDUCATION
    from membership.forms import ApplicationForm
    from membership.services import submit_application as register, record_verification, decide_application
    from documents.models import MembershipDocumentRequirement, DocumentType
    from documents.services import verify_document
    from programs.services import save_program_with_requirements, change_publication, verify_member, submit_application
    from programs.models import ProgramApplication
    from assistance.services import decide_assistance, void_release
    from ewaf import operational_services as operational
    from ewaf.operational_models import OperationalRun, OperationalDecision
    from ewaf.evidence import digest, source_context, approval_context
    from ewaf.evidence_services import record_policy, record_assessment
    from ewaf.weight_input import project
    from programs.terms import snapshot_terms, terms_digest
    from announcements.services import save_announcement, change_publication as publish_announcement
    from announcements.results import prepare_results, publish_results

    now = timezone.now()
    outcomes, members, programs, applications, policies = [], [], [], {}, {}
    types = list(DisabilityType.objects.filter(is_active=True).order_by('pk'))
    if not types:
        raise CommandError('Retain/configure Disability Types before seeding; no competing master list is generated.')
    slots = list(MembershipDocumentRequirement.objects.filter(capture_key__isnull=False))
    evidence_requirement = {code: next(item for item in slots if item.capture_key == key) for code, key in
        (('SI', 'valid_id_front'), ('ES', 'valid_id_back'), ('ND', 'disability_certificate'), ('PR', 'medical_certificate'))}

    # Advance a fictional timeline through the real registration and review services.
    # No score, rank, or production clock is edited.
    with patch('django.utils.timezone.now', return_value=now - timedelta(days=8)):
        for index, name in enumerate(NAMES):
            same = 22 if index == 23 else index
            data = {'submission_token': ApplicationForm().initial['submission_token'],
                'control_number': f'TEST-ONLY-{index + 1:03d}', 'first_name': name, 'last_name': f'Sample{index + 1:02d}',
                'middle_name': '' if index % 2 else 'Fictional', 'no_middle_name': bool(index % 2),
                'suffix': 'Jr.' if index == 3 else '', 'municipality': 'Fictional Test Municipality',
                'barangay': f'Test Barangay {index % 4 + 1}', 'house_number': str(index + 1),
                'street': f'Synthetic Street {index % 5 + 1}', 'purok_zone': f'Test Zone {index % 3 + 1}',
                'sex': 'male' if index % 2 else 'female',
                'civil_status': ('single', 'married', 'widowed', 'separated', 'divorced')[index % 5],
                'birthdate': date(1950 + index * 2, index % 12 + 1, index % 20 + 1),
                'email': f'fictional{index + 1}@example.test', 'contact_number': f'0000000{index + 1:04d}',
                'disability_types': [types[index % len(types)].pk],
                'disability_information': TEST, 'disability_cause': 'acquired' if index % 2 else 'congenital',
                'disability_visibility': 'apparent' if index % 3 else 'non_apparent',
                'education': EDUCATION[index % len(EDUCATION)][0], 'employment_status': EMPLOYMENT[same % 4][0],
                'income_category': INCOME[same % 6][0], 'dependents': same % 7,
                'monthly_income': '', 'employment_information': ''}
            if index % 5 == 0:
                data['disability_types'] = list({types[0].pk, types[-1].pk})
            initial = ApplicationForm()
            files = MultiValueDict({f'document_{item["id"]}': [upload(item['label'], portrait=item.get('capture_key') == 'photo_1x1')]
                for item in initial.snapshot if not (index >= 26 and item.get('capture_key') == 'medical_certificate' and not item['required'])})
            form = ApplicationForm(data, files)
            if not form.is_valid():
                raise ValidationError(str(form.errors))
            intake = register(form, user=actor)
            if index >= 28:
                continue  # Pending onsite registrations never become fabricated members.
            record_verification(intake.reference, user=actor, version=intake.version, verified=True, notes=TEST)
            intake.refresh_from_db()
            decide_application(intake.reference, user=actor, version=intake.version, decision='approved', notes=TEST)
            member = Member.objects.get(application=intake)
            for document in intake.documents.all():
                verify_document(document.pk, user=actor, member_version=member.version, verified=True,
                                expires_on=None, reason=TEST)
            members.append(member)

    def make_program(title, category, capacity, *, ewaf=True, offset=-3, close=-1, draft=False, disability_ids=()):
        at = now + timedelta(days=offset)
        with patch('django.utils.timezone.now', return_value=at):
            requirements = [{'label': 'TEST ' + role.replace('_', ' '), 'kind': 'text',
                'instructions': TEST, 'is_required': True} for role in ROLES]
            program = save_program_with_requirements(user=actor, data={
                'name': 'TEST ONLY — ' + title, 'description': TEST + ' ' + title,
                'assistance_type': category, 'registration_opens_at': now + timedelta(days=3) if close > 1 else at - timedelta(days=1),
                'registration_closes_at': now + timedelta(days=close), 'starts_at': now + timedelta(days=max(2, close + 1)),
                'ends_at': now + timedelta(days=max(5, close + 3)), 'slots': capacity, 'requirements': TEST,
                'eligible_disability_types': list(disability_ids),
                'ewaf_applicable': ewaf, 'selection_method': TEST + ' Reasoned human decisions within slots.',
                'photo_instructions': TEST + ' Manually review the artificial portrait.',
                'resubmission_closes_at': now + timedelta(days=1), 'version': 0, 'notes': TEST},
                requirements=requirements)
            if not draft:
                approve_terms(program, actor)
                program.refresh_from_db()
                change_publication(program.pk, user=actor, version=program.version, action='published', notes=TEST)
                program.refresh_from_db()
        programs.append(program)
        return program

    def apply(program, member, outcome='eligible', photo='VERIFIED', at=None):
        with patch('django.utils.timezone.now', return_value=at or now - timedelta(days=3)):
            program.refresh_from_db()
            grant = verify_member(program.pk, version=program.version, control_number=member.control_number,
                full_name=member.full_name, birthdate=member.birthdate, contact_number=member.contact_number)
            data = {'version': program.version, **{f'requirement_{req.pk}': TEST + ' Evidence supports this item.'
                for req in program.configured_requirements.filter(is_active=True)}}
            application = submit_application(program.pk, grant=grant, data=data,
                files=MultiValueDict({'calendar_photo': [upload(portrait=True)]}))
            if photo:
                photo_review(application, actor, photo)
            if photo == 'VERIFIED' and outcome:
                review(application, actor, outcome, failing=outcome == 'ineligible')
            applications.setdefault(str(program.pk), []).append(application)
            return application

    prior = make_program('Prior confirmed food assistance', 'Food & Nutrition', 4, ewaf=False, offset=-7, close=-6)
    for index in (0, 4, 8, 12):
        application = apply(prior, members[index], at=now - timedelta(days=7))
        with patch('django.utils.timezone.now', return_value=now - timedelta(days=5)):
            application.refresh_from_db()
            decide_assistance(application.pk, user=actor, data={'version': application.version,
                'decision': 'approved', 'notes': TEST, 'confirm': True})
            receipt = receive(application, actor, f'TEST-PRIOR-{index}')
            if index == 12:
                application.refresh_from_db()
                void_release(application.pk, receipt.pk, user=actor,
                    data={'version': application.version, 'notes': TEST + ' Incorrect fictional receipt.', 'confirm': True})

    food = make_program('Nutrition comparison', 'Food & Nutrition', 4)
    medical = make_program('Medical support comparison', 'Healthcare & Medical Aid', 10)
    mobility = make_program('Mobility qualification review', 'Assistive Devices', 2)
    beds = make_program('Hospital beds — corrections needed', 'Assistive Devices', 2)
    make_program('Upcoming nutrition outreach — no applicants', 'Food & Nutrition', 12, close=10)
    make_program('Medical proposal — simulated approval pending', 'Healthcare & Medical Aid', 3, draft=True)
    manual = make_program('Non-EWAF food distribution', 'Food & Nutrition', 2, ewaf=False)
    ties = make_program('Equal-score assistive-device comparison', 'Assistive Devices', 1)
    cutoff = make_program('Late inventory — calculation blocked', 'Healthcare & Medical Aid', 2)
    for index in range(12):
        apply(food, members[index])
    for index in range(14, 22):
        apply(medical, members[index])
    for index in range(5):
        apply(mobility, members[18 + index], outcome='ineligible' if index == 4 else 'eligible')
    for index in range(5):
        apply(beds, members[23 + index], outcome='review' if index == 0 else None,
              photo=('VERIFIED', None, 'REJECTED', 'NEEDS_RESUBMISSION', 'VERIFIED')[index])
    for index in range(3):
        apply(manual, members[24 + index])
    for index in (22, 23):
        apply(ties, members[index])
    late = apply(cutoff, members[13])
    # Explicit adversarial retained-inventory fixture: this is NOT a permitted late submission.
    ProgramApplication.objects.filter(pk=late.pk).update(submitted_at=now)
    qualification = make_program('Disability qualification example', 'Assistive Devices', 2,
                                  ewaf=False, disability_ids=[types[0].pk])
    apply(qualification, members[0])
    if len(types) > 1:
        with patch('django.utils.timezone.now', return_value=now - timedelta(days=3)):
            assert_blocked(lambda: apply(qualification, members[1]),
                           'Disability classification mismatch cannot submit', outcomes)
    pending_intake = MembershipApplication.objects.filter(control_number='TEST-ONLY-029').get()
    with patch('django.utils.timezone.now', return_value=now - timedelta(days=3)):
        assert_blocked(lambda: verify_member(manual.pk, version=manual.version,
            control_number=pending_intake.control_number, full_name=pending_intake.full_name,
            birthdate=pending_intake.birthdate, contact_number=pending_intake.contact_number),
            'Unapproved onsite registration cannot apply', outcomes)

    def mapping(code):
        req = evidence_requirement[code]
        return {'document_type_id': req.document_type_id, 'membership_requirement_id': req.pk,
                'basis': TEST, 'authority_reference': TEST}

    sources = {'SI': 'income_category', 'ES': 'employment_status', 'PA': 'successful_releases',
               'ND': 'dependent_count', 'PR': 'program_relevance'}
    numeric = {'SI': {key: str(5 - i) for i, (key, _) in enumerate(INCOME)},
               'ES': {'employed': '0', 'self_employed': '1', 'student': '2', 'retired': '3'}}
    proposal = {'order': ['SI', 'ES', 'PA', 'ND'],
                'weights': {'SI': 4000, 'ES': 3000, 'PA': 2000, 'ND': 1000}}
    judgments, _, provenance = project(proposal)

    def assess(application, evidence):
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            from ewaf.models import CriterionAssessment
            application.refresh_from_db()
            previous = CriterionAssessment.objects.filter(application=application, criterion=code).first()
            documents = {doc.requirement_id: doc for doc in application.member.application.documents.all()}
            reviews = {key: documents[req.pk].verifications.first().pk
                       for key, req in evidence_requirement.items() if req.pk in documents}
            if code in ('SI', 'ES', 'ND', 'PR') and code not in reviews:
                continue
            record_assessment(application.pk, user=actor, criterion=code, policy_id=evidence.pk, state='VERIFIED',
                source_type=sources[code], value='relevant' if code == 'PR' else None,
                expected_revision=previous.revision if previous else 0,
                expected_context=digest(source_context(application)), reason=TEST, confirmed=True,
                supporting_review_ids=[reviews[code]] if code in ('SI', 'ES', 'ND') else [],
                **({'rubric_attested': True, 'rubric_findings': [
                    {'item_id': role, 'outcome': 'supported', 'explanation': TEST + ' Reviewed ' + role,
                     'review_ids': [reviews['PR']]} for role in ROLES]} if code == 'PR' else {}))

    for program in (food, medical, mobility, beds, ties, cutoff):
        program.refresh_from_db()
        criteria = {
            'SI': {'definition': TEST, 'source_types': ['income_category'], 'unit': 'category',
                   'categories': dict(INCOME), 'rule_authority': TEST, 'evidence_mappings': {'income_category': [mapping('SI')]}},
            'ES': {'definition': TEST, 'source_types': ['employment_status'], 'unit': 'category',
                   'categories': dict(EMPLOYMENT), 'rule_authority': TEST, 'evidence_mappings': {'employment_status': [mapping('ES')]}},
            'PA': {'definition': TEST, 'source_types': ['successful_releases'], 'unit': 'records',
                   'pa_scope': 'all_retained_successful_releases', 'rule_authority': TEST},
            'ND': {'definition': TEST, 'source_types': ['dependent_count'], 'unit': 'persons',
                   'evidence_mappings': {'dependent_count': [mapping('ND')]}},
            'PR': {'definition': TEST, 'source_types': ['program_relevance'], 'unit': 'category',
                   'categories': {'relevant': 'Fictional documented functional need'}, 'rubric': TEST, 'rule_authority': TEST},
        }
        requirements = list(program.configured_requirements.order_by('position', 'pk'))
        criteria['PR']['rubric_definition'] = {'program_id': str(program.pk), 'version': 1,
            'terms_digest': terms_digest(snapshot_terms(program)), 'authority_reference': TEST,
            'items': [{'id': role, 'requirement_id': req.pk, 'applicability': 'all_applications',
                'outcomes': {'supported': TEST}, 'evidence_mappings': [mapping('PR')]}
                for role, req in zip(ROLES, requirements)]}
        evidence = record_policy(program.pk, user=actor, snapshot={'criteria': criteria},
            authority_reference=TEST, expected_revision=0,
            expected_context=digest({'program_version': program.version, 'approval': approval_context(program)}),
            reason=TEST, confirmed=True)
        policies[str(program.pk)] = evidence
        rules = {}
        for code, upper, unit in (('SI', '5', 'category'), ('ES', '3', 'category'), ('PA', '4', 'records'), ('ND', '8', 'persons')):
            rules[code] = {'measure': TEST, 'source_type': sources[code],
                'value_type': 'category' if code in numeric else 'integer', 'unit': unit,
                'direction': 'inverse' if code == 'PA' else 'benefit', 'encoding': numeric.get(code),
                'bounds': {'method': 'fixed', 'lower': '0', 'upper': upper},
                'observation_period': 'All retained successful releases' if code == 'PA' else 'Current verified fictional profile',
                'edge_cases': 'block'}
        policy = {'authority_reference': TEST, 'authorized_scope': 'Only this isolated fictional program',
            'approval_date': str(now.date() - timedelta(days=4)), 'effective_from': (now - timedelta(days=4)).isoformat(),
            'effective_until': (now + timedelta(days=30)).isoformat(), 'selection_rule': 'reasoned_human_within_slots',
            'tie_rule': 'reasoned_human', 'tie_procedure': TEST + ' Human review must explain each exact tie.',
            'classification_mode': 'none', 'classifications': None, 'edge_cases': 'block',
            'pa_scope': 'all_programs', 'pa_period': 'all_retained', 'pa_start': None, 'pa_end': None,
            'criteria': rules, 'eligibility': {role: {'item': role, 'accepted_outcome': 'supported'} for role in ROLES},
            'weight_input': provenance}
        operational.record_configuration(program.pk, user=actor, expected=operational.configuration_token(program),
            proposed=policy, judgments=judgments, status='LOCKED', reason=TEST, attested=True)
        for application in applications[str(program.pk)]:
            application.refresh_from_db()
            if application.status == 'ELIGIBLE':
                assess(application, evidence)

    disputed = applications[str(beds.pk)][0]
    record_assessment(disputed.pk, user=actor, criterion='SI', policy_id=policies[str(beds.pk)].pk,
        state='NEEDS_REVIEW', source_type='income_category', value=None, expected_revision=0,
        expected_context=digest(source_context(disputed)), reason=TEST + ' Disputed fictional income evidence.',
        confirmed=True, disputed=True)
    expired_member = members[25]
    expired_document = expired_member.application.documents.get(requirement=evidence_requirement['PR'])
    with patch('django.utils.timezone.now', return_value=now - timedelta(days=2)):
        verify_document(expired_document.pk, user=actor, member_version=expired_member.version, verified=True,
            expires_on=now.date() - timedelta(days=1), reason=TEST + ' Fictional evidence expired after this review.')

    def calculate(program):
        return operational.generate(program.pk, user=actor, expected=operational.context(program.pk, user=actor),
                                    reason=TEST, request_key=uuid4())

    runs = {}
    for program in (food, medical, mobility, ties):
        runs[str(program.pk)] = calculate(program)
    # Correct one verified source through the existing reasoned return/correction
    # workflow, then retain a replacement run and its immutable predecessor.
    from members.services import update_member
    from membership.forms import PROFILE_FIELDS
    from programs.workflow import correct_application
    changed = applications[str(medical.pk)][0]
    previous = runs[str(medical.pk)]
    retained = deepcopy(previous.payload())
    changed.refresh_from_db()
    decide_assistance(changed.pk, user=actor, data={'version': changed.version, 'decision': 'pending',
        'notes': TEST + ' Return for a verified dependent-count correction.', 'confirm': True})
    member = changed.member
    member.refresh_from_db()
    values = {key: getattr(member, key) for key in PROFILE_FIELDS}
    values.update(disability_type=member.disability_type_id, disability_types=member.disability_ids,
                  disability_selection_present='1', dependents=3)
    member = update_member(member.pk, user=actor, version=member.version, data=values,
                           notes=TEST + ' Correct verified dependents.')
    assert_blocked(lambda: calculate(medical), 'Changed member source blocks old evidence', outcomes)
    changed.refresh_from_db()
    correct_application(changed.pk, user=actor, data={'version': changed.version, 'reason': TEST,
        'confirm': True, **{f'requirement_{key}': value for key, value in changed.answers.items()}},
        files=MultiValueDict({'calendar_photo': [upload(portrait=True)]}))
    photo_review(changed, actor)
    for document in member.application.documents.all():
        verify_document(document.pk, user=actor, member_version=member.version, verified=True,
                        expires_on=None, reason=TEST + ' Renewed document verification.')
    review(changed, actor)
    assess(changed, policies[str(medical.pk)])
    runs[str(medical.pk)] = calculate(medical)
    previous.refresh_from_db()
    if previous.payload() != retained or runs[str(medical.pk)].previous_id != previous.pk:
        raise AssertionError('Recalculation did not preserve predecessor history')
    for program in (beds, cutoff):
        assert_blocked(lambda program=program: calculate(program), program.name, outcomes)
    tie_run = runs[str(ties.pk)]
    tied_rows = operational.ordered(tie_run)
    if tied_rows[0]['score_0_100'] != tied_rows[1]['score_0_100']:
        raise AssertionError('Exact tie fixture must retain identical Decimal scores')
    operational.record_decision(ties.pk, user=actor, run_id=tie_run.pk, application_id=tied_rows[0]['application'],
        expected_revision=0, outcome='SELECTED', reason=TEST + ' Explicit fictional human decision within the one available slot.',
        tie_reason=TEST + ' Both scores remain equal; a documented fictional human review selects this applicant without changing either score.')
    assert_blocked(lambda: operational.record_decision(ties.pk, user=actor, run_id=tie_run.pk,
        application_id=tied_rows[1]['application'], expected_revision=0, outcome='SELECTED',
        reason=TEST, tie_reason=TEST), 'Exact tie cannot override the slot limit', outcomes)
    comparisons = {}
    for key, run in runs.items():
        comparisons[key] = []
        for row in operational.ordered(run):
            with localcontext() as ctx:
                ctx.prec = 80
                expected = sum(Decimal(trace['normalized']) * Decimal(trace['weight']) for trace in row['traces']) * 100
            if abs(expected - Decimal(row['score_0_100'])) > Decimal('1e-24'):
                raise AssertionError('Independent Decimal score check failed')
            application = ProgramApplication.objects.select_related('member').get(pk=row['application'])
            comparisons[key].append({'member': application.member.full_name,
                'score': row['score_0_100'], 'position': row['comparison']['higher'] + 1})
    run = runs[str(food.pk)]
    ranked = operational.ordered(run)
    for index, row in enumerate(ranked):
        operational.record_decision(food.pk, user=actor, run_id=run.pk, application_id=row['application'],
            expected_revision=0, outcome='SELECTED' if index < food.slots else 'NOT_SELECTED',
            reason=TEST + ' Reviewed applicant need against program capacity.', tie_reason=TEST)
    assert_blocked(lambda: operational.record_decision(food.pk, user=actor, run_id=run.pk,
        application_id=ranked[food.slots]['application'], expected_revision=1, outcome='SELECTED',
        reason=TEST, tie_reason=TEST), 'Selection exceeds beneficiary capacity', outcomes)
    selected = ProgramApplication.objects.get(pk=ranked[0]['application'])
    receive(selected, actor, 'TEST-NUTRITION-RECEIPT')
    result = prepare_results(food.pk, user=actor, version=0, reason=TEST, recipients=True)
    publish_results(result.pk, user=actor, version=result.version)
    manual_selected = applications[str(manual.pk)][0]
    manual_selected.refresh_from_db()
    decide_assistance(manual_selected.pk, user=actor, data={'version': manual_selected.version,
        'decision': 'approved', 'notes': TEST + ' Authorized non-EWAF beneficiary workflow.', 'confirm': True})
    receive(manual_selected, actor, 'TEST-MANUAL-RECEIPT')
    for index in range(4):
        item = save_announcement(user=actor, data={'version': 0, 'title': f'TEST ONLY — Community update {index + 1}',
            'content': TEST + ' Fictional Help Desk demonstration notice.', 'image_alt': ''})
        if index < 3:
            publish_announcement(item.pk, user=actor, version=item.version, action='published')
        if index == 0:
            item.refresh_from_db()
            publish_announcement(item.pk, user=actor, version=item.version, action='draft')
            item.refresh_from_db()
            item = save_announcement(user=actor, pk=item.pk, data={'version': item.version,
                'title': item.title, 'content': TEST + ' Edited and republished fictional notice.', 'image_alt': ''})
            publish_announcement(item.pk, user=actor, version=item.version, action='published')
    return {'purpose': TEST, 'comparisons': comparisons, 'blocked_checks': outcomes,
            'program_ids': {program.name: str(program.pk) for program in programs},
            'application_ids': {key: [str(app.pk) for app in value] for key, value in applications.items()},
            'demonstration_program': str(medical.pk), 'receipt_program': str(food.pk)}
