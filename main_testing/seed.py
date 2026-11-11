"""Fixed-seed fictional records created through current application services."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, localcontext
import json
from pathlib import Path
import random
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from core.demo_seed import upload, approve_terms, review, photo_review, receive, TEST, ROLES

SEED = 20261021


def require_environment():
    assert getattr(settings, 'MAIN_TESTING', False)
    manifest = settings.MAIN_TESTING_MANIFEST
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE(), @@server_uuid, CURRENT_USER()')
        name, server, user = cursor.fetchone()
    assert name == manifest['database'] and name.startswith('santolan_lab_')
    assert server == manifest['server_uuid'] and user.split('@')[0] == manifest['user']


def seed():
    require_environment()
    from members.models import Member
    from membership.models import MembershipSettings, MembershipApplication
    from programs.models import Program
    assert not any(model.objects.exists() for model in (Member, MembershipApplication, Program)), 'Use a new empty database'
    manifest = settings.MAIN_TESTING_MANIFEST
    actor = get_user_model().objects.create_superuser(manifest['admin_username'], email='admin@example.test', password=manifest['admin_password'])
    get_user_model().objects.create_user('lab_viewer', email='viewer@example.test', password=None, is_staff=True)
    MembershipSettings.objects.update_or_create(pk=1, defaults={'registration_open': False,
        'prpwd_url': 'https://example.invalid/simulated-registry-no-government-service'})
    builder = Builder(actor)
    builder.run()


class Builder:
    def __init__(self, actor):
        from documents.models import MembershipDocumentRequirement
        self.actor = actor
        self.random = random.Random(SEED)
        self.now = timezone.now().replace(second=0, microsecond=0)
        self.members, self.programs, self.applications, self.evidence = [], [], {}, {}
        self.out = Path(settings.MEDIA_ROOT).parent
        self.out.mkdir(parents=True, exist_ok=True)
        slots = list(MembershipDocumentRequirement.objects.filter(capture_key__isnull=False))
        self.evidence_requirement = {code: next(item for item in slots if item.capture_key == key)
            for code, key in (('SI', 'valid_id_front'), ('ES', 'valid_id_back'), ('ND', 'disability_certificate'), ('PR', 'medical_certificate'))}
        self.result = {'seed': SEED, 'purpose': TEST, 'programs': {}, 'ranking_experiments': {}, 'blocked': []}

    def progress(self, message):
        print(message, flush=True)

    def register_members(self, count=1800, pending=40):
        from members.models import Member, DisabilityType
        from members.profile import INCOME, EMPLOYMENT, EDUCATION
        from membership.forms import ApplicationForm
        from membership.services import submit_application, record_verification, decide_application
        from documents.services import verify_document
        types = list(DisabilityType.objects.order_by('name'))
        assert len(types) == 10
        first_names = ('Amihan', 'Bituin', 'Cielo', 'Dalisay', 'Elio', 'Fiora', 'Giliw', 'Hiraya', 'Isla', 'Juno',
                       'Kislap', 'Liora', 'Mithi', 'Nilo', 'Orion', 'Pia', 'Quilo', 'Raya', 'Sinta', 'Tala')
        surnames = ('Alonverde', 'Bituinal', 'Cielomar', 'Daliraya', 'Elunara', 'Fioraluz', 'Gintala', 'Hirayon',
                    'Islavela', 'Junoria', 'Kislora', 'Liorasol', 'Mithiran', 'Nilovela', 'Orihaya', 'Pialuna',
                    'Quilomar', 'Rayalun', 'Sintavela', 'Taloria')
        special = [(0, 0, 1), (3, 3, 1), (4, 1, 1), (3, 1, 8), (2, 2, 4), (2, 2, 4)]
        with patch('django.utils.timezone.now', return_value=self.now - timedelta(days=400)):
            for index in range(count + pending):
                si, es, nd = special[index] if index < 6 else (self.random.randrange(6), self.random.randrange(4), self.random.randrange(9))
                first = first_names[index % 20]
                last = surnames[(index // 20) % 20] + f' {index // 400 + 1:02d}'
                birth_year = self.random.randrange(1944, 2007)
                data = {'submission_token': ApplicationForm().initial['submission_token'], 'control_number': f'LAB-{SEED}-{index + 1:05d}',
                    'first_name': first, 'last_name': last, 'middle_name': '', 'no_middle_name': True, 'suffix': '',
                    'municipality': 'Fictional Santolan Testing Municipality', 'barangay': f'Imaginary District {index % 12 + 1}',
                    'house_number': str(index % 250 + 1), 'street': f'Invented {surnames[index % 20]} Street',
                    'purok_zone': f'Zone {index % 7 + 1}', 'sex': 'male' if index % 2 else 'female',
                    'civil_status': ('single', 'married', 'widowed', 'separated', 'divorced')[index % 5],
                    'birthdate': date(birth_year, index % 12 + 1, index % 27 + 1),
                    'email': f'member{index + 1}@example.test', 'contact_number': f'000{index + 1:08d}',
                    'disability_types': [types[index % 10].pk], 'disability_information': 'Synthetic profile; no clinical or government identity.',
                    'disability_cause': 'acquired' if index % 2 else 'congenital',
                    'disability_visibility': 'apparent' if index % 3 else 'non_apparent',
                    'education': EDUCATION[index % len(EDUCATION)][0], 'employment_status': EMPLOYMENT[es][0],
                    'income_category': INCOME[si][0], 'dependents': nd, 'monthly_income': '', 'employment_information': ''}
                if index % 5 == 0:
                    data['disability_types'] = list({types[index % 10].pk, types[(index + 3) % 10].pk})
                initial = ApplicationForm()
                files = MultiValueDict({f'document_{item["id"]}': [upload(item['label'], portrait=item.get('capture_key') == 'photo_1x1')]
                    for item in initial.snapshot if index < count or item['required']})
                form = ApplicationForm(data, files)
                if not form.is_valid():
                    raise ValidationError(str(form.errors))
                with transaction.atomic():
                    intake = submit_application(form, user=self.actor)
                    if index < count:
                        record_verification(intake.reference, user=self.actor, version=intake.version, verified=True,
                                            notes=TEST + ' Simulated local review; no registry lookup.')
                        intake.refresh_from_db()
                        decide_application(intake.reference, user=self.actor, version=intake.version, decision='approved', notes=TEST)
                        member = Member.objects.get(application=intake)
                        for document in intake.documents.all():
                            verify_document(document.pk, user=self.actor, member_version=member.version, verified=True,
                                            expires_on=None, reason=TEST)
                        self.members.append(member)
                if (index + 1) % 100 == 0:
                    self.progress(f'Onsite profiles: {index + 1}/{count + pending}; approved members: {len(self.members)}')

    def make_program(self, title, category='Food & Nutrition', slots=20, *, ewaf=True, offset=-20, close=-2,
                     draft=False, disability_ids=()):
        from programs.services import save_program_with_requirements, change_publication
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(days=offset)):
            program = save_program_with_requirements(user=self.actor, data={
                'name': title, 'description': 'Fictional ' + title + '. Review evidence, compare applicants and record a reasoned decision. '
                    'Any PDAO review recorded here is simulated and has no external authority.',
                'assistance_type': category, 'registration_opens_at': self.now + timedelta(days=offset - 1),
                'registration_closes_at': self.now + timedelta(days=close), 'starts_at': self.now + timedelta(days=max(close + 2, 2)),
                'ends_at': self.now + timedelta(days=max(close + 5, 5)), 'slots': slots,
                'requirements': 'Verified membership and current required evidence; functional need reviewed for this program.',
                'eligible_disability_types': list(disability_ids), 'ewaf_applicable': ewaf,
                'selection_method': TEST + ' Reasoned human selection within slots; scores do not automatically select.',
                'photo_instructions': 'Review the artificial portrait as fictional evidence only.',
                'resubmission_closes_at': self.now + timedelta(days=90), 'version': 0, 'notes': TEST},
                requirements=[{'label': role.replace('_', ' ').title(), 'kind': 'text', 'instructions': TEST,
                               'is_required': True} for role in ROLES])
            if not draft:
                approve_terms(program, self.actor)
                program.refresh_from_db()
                change_publication(program.pk, user=self.actor, version=program.version, action='published', notes=TEST)
                program.refresh_from_db()
        self.programs.append(program)
        self.applications[str(program.pk)] = []
        self.result['programs'][title] = str(program.pk)
        return program

    def apply(self, program, member, *, outcome='eligible', photo='VERIFIED', at=None):
        from programs.services import verify_member, submit_application
        with patch('django.utils.timezone.now', return_value=at or self.now - timedelta(days=10)):
            grant = verify_member(program.pk, version=program.version, control_number=member.control_number,
                full_name=member.full_name, birthdate=member.birthdate, contact_number=member.contact_number)
            data = {'version': program.version, **{f'requirement_{req.pk}': 'Synthetic reviewed evidence supports this condition.'
                    for req in program.configured_requirements.filter(is_active=True)}}
            with transaction.atomic():
                app = submit_application(program.pk, grant=grant, data=data,
                    files=MultiValueDict({'calendar_photo': [upload(portrait=True)]}))
                if photo:
                    photo_review(app, self.actor, photo)
                if photo == 'VERIFIED' and outcome:
                    review(app, self.actor, outcome, failing=outcome == 'ineligible')
            self.applications[str(program.pk)].append(app)
            return app

    def previous_assistance(self):
        from assistance.services import decide_assistance, void_release
        special_counts = [4, 3, 0, 3, 1, 1]
        for round in range(4):
            program = self.make_program(f'Community Pantry — Historical Round {round + 1}', slots=400,
                                        ewaf=False, offset=-300 + round * 55, close=-290 + round * 55)
            indices = [i for i in range(6) if special_counts[i] > round]
            indices += [i for i in range(6, 306) if i % 4 >= round]
            for index in indices:
                when = self.now - timedelta(days=298 - round * 55)
                app = self.apply(program, self.members[index], at=when)
                with patch('django.utils.timezone.now', return_value=when + timedelta(days=10)):
                    app.refresh_from_db()
                    decide_assistance(app.pk, user=self.actor, data={'version': app.version, 'decision': 'approved',
                                      'notes': TEST, 'confirm': True})
                    receipt = receive(app, self.actor, f'LAB-HISTORY-{round + 1}-{index + 1:05d}')
                    if index >= 6 and index % 17 == 0:
                        app.refresh_from_db()
                        void_release(app.pk, receipt.pk, user=self.actor, data={'version': app.version, 'notes': TEST + ' Incorrect fictional receipt.', 'confirm': True})
                        if index % 34 == 0:
                            review(app, self.actor)
                            app.refresh_from_db()
                            decide_assistance(app.pk, user=self.actor, data={'version': app.version,
                                'decision': 'approved', 'notes': TEST + ' Renewed approval after receipt correction.', 'confirm': True})
                            receive(app, self.actor, f'LAB-CORRECTED-{round + 1}-{index + 1:05d}')
            self.progress(f'Historical assistance round {round + 1}: {len(indices)} applications and reasoned receipts')

    def mapping(self, code):
        req = self.evidence_requirement[code]
        return {'document_type_id': req.document_type_id, 'membership_requirement_id': req.pk,
                'basis': TEST, 'authority_reference': TEST}

    def configure(self, program, emphasis=None):
        from members.profile import INCOME, EMPLOYMENT
        from ewaf.evidence import digest, approval_context
        from ewaf.evidence_services import record_policy
        from ewaf import operational_services as service
        from ewaf.weight_input import project
        from programs.terms import terms_digest, snapshot_terms
        program.refresh_from_db()
        criteria = {
            'SI': {'definition': TEST, 'source_types': ['income_category'], 'unit': 'category', 'categories': dict(INCOME),
                   'rule_authority': TEST, 'evidence_mappings': {'income_category': [self.mapping('SI')]}},
            'ES': {'definition': TEST, 'source_types': ['employment_status'], 'unit': 'category', 'categories': dict(EMPLOYMENT),
                   'rule_authority': TEST, 'evidence_mappings': {'employment_status': [self.mapping('ES')]}},
            'PA': {'definition': TEST, 'source_types': ['successful_releases'], 'unit': 'records',
                   'pa_scope': 'all_retained_successful_releases', 'rule_authority': TEST},
            'ND': {'definition': TEST, 'source_types': ['dependent_count'], 'unit': 'persons',
                   'evidence_mappings': {'dependent_count': [self.mapping('ND')]}},
            'PR': {'definition': TEST, 'source_types': ['program_relevance'], 'unit': 'category',
                   'categories': {'relevant': 'Fictional documented functional need'}, 'rubric': TEST, 'rule_authority': TEST},
        }
        criteria['PR']['rubric_definition'] = {'program_id': str(program.pk), 'version': 1,
            'terms_digest': terms_digest(snapshot_terms(program)), 'authority_reference': TEST,
            'items': [{'id': role, 'requirement_id': req.pk, 'applicability': 'all_applications',
                'outcomes': {'supported': TEST}, 'evidence_mappings': [self.mapping('PR')]}
                for role, req in zip(ROLES, program.configured_requirements.order_by('position', 'pk'))]}
        evidence = record_policy(program.pk, user=self.actor, snapshot={'criteria': criteria}, authority_reference=TEST,
            expected_revision=0, expected_context=digest({'program_version': program.version, 'approval': approval_context(program)}),
            reason=TEST, confirmed=True)
        self.evidence[str(program.pk)] = evidence
        sources = {'SI': 'income_category', 'ES': 'employment_status', 'PA': 'successful_releases', 'ND': 'dependent_count'}
        encodings = {'SI': {key: str(5 - i) for i, (key, _) in enumerate(INCOME)},
                     'ES': {'employed': '0', 'self_employed': '1', 'student': '2', 'retired': '3'}}
        rules = {code: {'measure': TEST, 'source_type': sources[code],
            'value_type': 'category' if code in encodings else 'integer', 'unit': unit,
            'direction': 'inverse' if code == 'PA' else 'benefit', 'encoding': encodings.get(code),
            'bounds': {'method': 'fixed', 'lower': '0', 'upper': upper}, 'observation_period': 'Current verified fictional profile',
            'edge_cases': 'block'} for code, upper, unit in [('SI', '5', 'category'), ('ES', '3', 'category'), ('PA', '4', 'records'), ('ND', '8', 'persons')]}
        rules['PA']['observation_period'] = 'All retained successful releases'
        policy = {'authority_reference': TEST, 'authorized_scope': 'Only this isolated fictional testing program',
            'approval_date': str(self.now.date() - timedelta(days=30)), 'effective_from': (self.now - timedelta(days=30)).isoformat(),
            'effective_until': (self.now + timedelta(days=365)).isoformat(), 'selection_rule': 'reasoned_human_within_slots',
            'tie_rule': 'reasoned_human', 'tie_procedure': TEST + ' Explain human review of exact ties; never modify scores.',
            'classification_mode': 'none', 'classifications': None, 'edge_cases': 'block', 'pa_scope': 'all_programs',
            'pa_period': 'all_retained', 'pa_start': None, 'pa_end': None, 'criteria': rules,
            'eligibility': {role: {'item': role, 'accepted_outcome': 'supported'} for role in ROLES}}
        proposal = self.proposal(emphasis)
        judgments, _, provenance = project(proposal)
        policy['weight_input'] = provenance
        return service.record_configuration(program.pk, user=self.actor, expected=service.configuration_token(program),
            proposed=policy, judgments=judgments, status='LOCKED', reason=TEST, attested=True)

    @staticmethod
    def proposal(emphasis):
        codes = ['SI', 'ES', 'PA', 'ND']
        return {'order': ([emphasis] + [code for code in codes if code != emphasis]) if emphasis else codes,
                'weights': {code: (7000 if code == emphasis else 1000) if emphasis else 2500 for code in codes}}

    def assess(self, app):
        from ewaf.evidence import digest, source_context
        from ewaf.evidence_services import record_assessment
        evidence = self.evidence[str(app.program_id)]
        sources = {'SI': 'income_category', 'ES': 'employment_status', 'PA': 'successful_releases', 'ND': 'dependent_count', 'PR': 'program_relevance'}
        docs = {doc.requirement_id: doc for doc in app.member.application.documents.all()}
        reviews = {code: docs[req.pk].verifications.first().pk for code, req in self.evidence_requirement.items()}
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            app.refresh_from_db()
            record_assessment(app.pk, user=self.actor, criterion=code, policy_id=evidence.pk, state='VERIFIED',
                source_type=sources[code], value='relevant' if code == 'PR' else None, expected_revision=0,
                expected_context=digest(source_context(app)), reason=TEST, confirmed=True,
                supporting_review_ids=[reviews[code]] if code in ('SI', 'ES', 'ND') else [],
                **({'rubric_attested': True, 'rubric_findings': [{'item_id': role, 'outcome': 'supported',
                    'explanation': TEST + ' Reviewed ' + role, 'review_ids': [reviews['PR']]} for role in ROLES]} if code == 'PR' else {}))

    def calculate(self, program):
        from ewaf import operational_services as service
        return service.generate(program.pk, user=self.actor, expected=service.context(program.pk, user=self.actor), reason=TEST, request_key=uuid4())

    def labs(self):
        from ewaf import operational_services as service
        from ewaf.weight_input import project
        from assistance.services import decide_assistance
        labs = [('SI Emphasis', 'SI', 3), ('Employment Emphasis', 'ES', 5), ('Previous Assistance Emphasis', 'PA', 10),
                ('Dependents Emphasis', 'ND', 20), ('Balanced Weights', None, 50), ('Exact Tie', None, 3),
                ('Selection & Slots', None, 5), ('Assistance Release', None, 10)]
        for index, (label, emphasis, slots) in enumerate(labs):
            program = self.make_program('EWAF Lab — ' + label, ('Food & Nutrition', 'Healthcare & Medical Aid', 'Assistive Devices')[index % 3], slots)
            cohort = [4, 5] if label == 'Exact Tie' else list(range(350, 410)) if label == 'Selection & Slots' else list(range(420, 440)) if label == 'Assistance Release' else list(range(6))
            for member_index in cohort:
                self.apply(program, self.members[member_index])
            configuration = self.configure(program, emphasis)
            for app in self.applications[str(program.pk)]:
                self.assess(app)
            run = self.calculate(program)
            if label == 'Balanced Weights':
                # Real configuration revisions and invalidation on one retained pool.
                retained = deepcopy(run.payload())
                for experiment in ('SI', 'ES', 'PA', 'ND', None):
                    policy = deepcopy(configuration.policy)
                    judgments, _, provenance = project(self.proposal(experiment))
                    policy['weight_input'] = provenance
                    configuration = service.record_configuration(program.pk, user=self.actor,
                        expected=service.configuration_token(program), proposed=policy, judgments=judgments,
                        status='LOCKED', reason=TEST + ' Weight experiment ' + str(experiment), attested=True)
                    try:
                        with service.fence(program.pk, self.actor) as (actor, current, applications):
                            service._current(current, applications, actor, run.pk)
                    except ValidationError:
                        pass
                    else:
                        raise AssertionError('Old result must be stale after changed configuration')
                    run = self.calculate(program)
                    self.result['ranking_experiments'][experiment or 'Balanced'] = self.ranking(run)
                first = type(run).objects.filter(program=program).order_by('revision').first()
                assert first.payload() == retained
            if label == 'Exact Tie':
                rows = service.ordered(run)
                assert rows[0]['score_0_100'] == rows[1]['score_0_100']
            if label == 'Assistance Release':
                # Deliberate fictional human choices in application order, never auto-top-N.
                for app in self.applications[str(program.pk)][:5]:
                    service.record_decision(program.pk, user=self.actor, run_id=run.pk, application_id=app.pk,
                        expected_revision=0, outcome='SELECTED', reason=TEST + ' Simulated human choice for hands-on release testing.', tie_reason=TEST)
            self.progress(f'{program.name}: {len(cohort)} reviewed applicants, real calculation; history retained')

    def ranking(self, run):
        from ewaf.operational_services import ordered
        from programs.models import ProgramApplication
        rows = []
        for row in ordered(run):
            app = ProgramApplication.objects.select_related('member').get(pk=row['application'])
            rows.append({'member': app.member.full_name, 'application': str(app.pk), 'score': row['score_0_100'],
                         'rank': row['comparison']['higher'] + 1})
        return {'run': str(run.pk), 'weights': run.configuration.validation['weights'], 'rows': rows}

    def general_programs(self):
        from assistance.services import decide_assistance, void_release
        from programs.models import ProgramApplication
        names = ['Monthly Food Assistance', 'Family Nutrition Support', 'Emergency Grocery Assistance',
                 'Medical Aid Assistance', 'Medical Checkup Support', 'Hospital Bed Assistance',
                 'Wheelchair Distribution', 'Hearing Aid Assistance', 'Mobility Device Assistance',
                 'Therapy Support', 'Medical Supplies Assistance', 'Assistive Technology Support']
        for index in range(30):
            category = ('Food & Nutrition', 'Healthcare & Medical Aid', 'Assistive Devices')[index % 3]
            title = names[index % 12] + f' — Community Cycle {index // 12 + 1}'
            upcoming, draft = index >= 28, index in (26, 27)
            program = self.make_program(title, category, (3, 5, 10, 20, 50)[index % 5], ewaf=index % 4 == 0,
                offset=5 if upcoming else -20, close=20 if upcoming or index in (23, 24, 25) else -2, draft=draft)
            if draft or upcoming:
                continue
            size = 5 if index == 25 else 155
            for position in range(size):
                member = self.members[600 + (index * 43 + position) % 1100]
                case = position % 10
                photo = {6: None, 7: 'REJECTED', 8: 'NEEDS_RESUBMISSION'}.get(case, 'VERIFIED')
                outcome = 'ineligible' if case == 5 else 'review' if case == 9 else 'eligible'
                app = self.apply(program, member, photo=photo, outcome=outcome)
                if not program.ewaf_applicable and position < min(program.slots, 5) and index < 12:
                    app.refresh_from_db()
                    decide_assistance(app.pk, user=self.actor, data={'version': app.version, 'decision': 'approved', 'notes': TEST, 'confirm': True})
                    if index % 3 != 1:
                        receipt = receive(app, self.actor, f'LAB-CURRENT-{index}-{position}')
                        if position == 0 and index % 3 == 2:
                            app.refresh_from_db()
                            void_release(app.pk, receipt.pk, user=self.actor, data={'version': app.version, 'notes': TEST + ' Correction required.', 'confirm': True})
            if program.ewaf_applicable:
                self.configure(program)
            self.progress(f'General programs: {index + 1}/30; total applications: {ProgramApplication.objects.count()}')

    def scenarios(self):
        from documents.services import verify_document
        from members.services import change_status
        # Keep evidence-expiry cases away from the immediately usable labs.
        member = self.members[1750]
        doc = member.application.documents.get(requirement=self.evidence_requirement['PR'])
        with patch('django.utils.timezone.now', return_value=self.now - timedelta(days=5)):
            verify_document(doc.pk, user=self.actor, member_version=member.version, verified=True,
                            expires_on=self.now.date() - timedelta(days=1), reason=TEST + ' Expired fictional evidence.')

    def announcements(self):
        from announcements.services import save_announcement, change_publication
        from announcements.results import prepare_results, publish_results
        from assistance.models import AssistanceRelease
        for index in range(38):
            title = ('Help Desk Schedule', 'Accessible Community Activities', 'Nutrition Program Notice',
                     'Document Review Guidance', 'Health Support Update', 'Assistive Device Orientation')[index % 6]
            with patch('django.utils.timezone.now', return_value=self.now - timedelta(days=index * 4)):
                item = save_announcement(user=self.actor, data={'version': 0, 'title': title + f' — Bulletin {index + 1:02d}',
                    'content': f'Fictional community bulletin {index + 1}. Visit the testing Help Desk for assistance with onsite registration, '
                               'program evidence and accessible support. No real event, government approval or personal contact is represented.', 'image_alt': ''})
                if index % 4:
                    change_publication(item.pk, user=self.actor, version=item.version, action='published')
                if index % 4 == 3:
                    item.refresh_from_db()
                    change_publication(item.pk, user=self.actor, version=item.version, action='archived')
        for program in self.programs[:2]:
            assert AssistanceRelease.objects.successful().filter(application__program=program).exists()
            revision = prepare_results(program.pk, user=self.actor, version=0, reason=TEST, recipients=True)
            publish_results(revision.pk, user=self.actor, version=revision.version)

    def observances(self):
        from dataclasses import asdict
        from events.observances import REFERENCE_CATALOGUE
        from events.services import save_observance, change_observance_publication
        for reference in REFERENCE_CATALOGUE:
            item = save_observance(user=self.actor, data={**asdict(reference), 'version': 0,
                'image_alt': '', 'notes': TEST + ' Reference calendar copied as fictional published content.'})
            change_observance_publication(item.pk, user=self.actor, version=item.version, action='published', notes=TEST)

    def finish(self):
        from core.demo_seed import counts
        from assistance.models import AssistanceRelease
        from ewaf.operational_models import OperationalRun
        from ewaf.operational_services import ordered
        self.result['counts'] = counts()
        self.result['counts']['assistance_records'] = AssistanceRelease.objects.count()
        checked = 0
        for run in OperationalRun.objects.all():
            run.clean()
            scores = []
            for row in ordered(run):
                with localcontext() as ctx:
                    ctx.prec = 80
                    expected = sum(Decimal(t['normalized']) * Decimal(t['weight']) for t in row['traces']) * 100
                assert abs(expected - Decimal(row['score_0_100'])) < Decimal('1e-24')
                assert 0 <= expected <= 100
                scores.append(Decimal(row['score_0_100']))
                checked += 1
            assert scores == sorted(scores, reverse=True)
        self.result['scores_verified'] = checked
        self.result['application_ids'] = {key: [str(app.pk) for app in values] for key, values in self.applications.items()}
        (self.out / 'dataset.json').write_text(json.dumps(self.result, indent=2, default=str), encoding='utf-8')
        self.progress(json.dumps(self.result['counts']))

    def run(self):
        self.register_members()
        self.previous_assistance()
        self.labs()
        self.general_programs()
        self.announcements()
        self.observances()
        self.finish()
