"""Explicit fictional policies and service-created programs for tests and the lab."""
from datetime import timedelta
from django.utils import timezone
from members.profile import EMPLOYMENT
from programs.services import save_program_with_requirements, change_publication
from ewaf.evidence import approval_context, digest
from ewaf.evidence_services import record_policy
from ewaf.operational_services import configuration_token, record_configuration
from ewaf.weight_input import project
from core.demo_seed import TEST, approve_terms
from .sources import CONTRACT


def review_application(application, actor, outcome='eligible'):
    from programs.review_services import complete_eligibility_review
    application.refresh_from_db()
    data = {'version': application.version, 'member_version': application.member.version,
        'program_version': application.program.version, 'eligibility': outcome, 'other_requirements': 'pass', 'notes': TEST}
    present = set(application.documents.values_list('requirement_id', flat=True))
    data.update({f'check_{r["id"]}': 'pass' if r['id'] in present else 'review' for r in application.requirements_snapshot})
    return complete_eligibility_review(application.pk, user=actor, data=data)


def create_program(actor, name='Public Application Lab', *, closes=None, restrictions=(), slots=3, ewaf=True):
    now = timezone.now()
    program = save_program_with_requirements(user=actor, data={
        'name': name, 'description': 'Fictional program for secure public applications and verified source collection. PDAO approval here is simulated.',
        'assistance_type': 'Food & Nutrition', 'registration_opens_at': now - timedelta(days=1),
        'registration_closes_at': closes or now + timedelta(days=30), 'starts_at': now + timedelta(days=35),
        'ends_at': now + timedelta(days=40), 'slots': slots, 'requirements': 'Verified membership and the configured socioeconomic evidence.',
        'eligible_disability_types': list(restrictions), 'ewaf_applicable': ewaf,
        'selection_method': TEST + ' Reasoned human selection within capacity.',
        'photo_instructions': 'Fictional current calendar portrait for manual identity review.',
        'resubmission_closes_at': now + timedelta(days=60), 'version': 0, 'notes': TEST}, requirements=[
            {'label': 'Socioeconomic assessment document', 'kind': 'document', 'instructions': 'Fictional evidence documenting the observed household-need measurement.', 'is_required': True},
            {'label': 'Additional supporting evidence (optional)', 'kind': 'document', 'instructions': 'Supply only if relevant.', 'is_required': False}])
    approve_terms(program, actor)
    program.refresh_from_db()
    change_publication(program.pk, user=actor, version=program.version, action='published', notes=TEST)
    program.refresh_from_db()
    return program


def configure(program, actor, emphasis=None):
    now = timezone.now()
    requirement = program.configured_requirements.get(is_required=True)
    definitions = {
        'SI': {'definition': TEST + ' Observed fictional household-need measure documented in the submitted program assessment.',
            'source_types': ['socioeconomic_assessment'], 'unit': 'assessment units', 'rule_authority': TEST,
            'observation_rule': 'Fictional evidence observation date, valid for 365 days.', 'freshness_days': 365},
        'ES': {'definition': TEST + ' Recorded onsite employment identifier.', 'source_types': ['employment_status'],
            'unit': 'category', 'categories': dict(EMPLOYMENT), 'rule_authority': TEST},
        'PA': {'definition': TEST + ' Confirmed non-voided actual receipts.', 'source_types': ['successful_releases'],
            'unit': 'records', 'pa_scope': 'all_retained_successful_releases', 'rule_authority': TEST},
        'ND': {'definition': TEST + ' Recorded onsite dependent count.', 'source_types': ['dependent_count'], 'unit': 'persons'},
        'PR': {'definition': TEST + ' Disability qualification only; no additional functional-need requirement for this fictional food program.',
            'source_types': ['program_relevance'], 'unit': 'category', 'categories': {'relevant': 'Applicable disability match'}, 'rule_authority': TEST},
    }
    evidence = record_policy(program.pk, user=actor, snapshot={'criteria': definitions}, authority_reference=TEST,
        expected_revision=0, expected_context=digest({'program_version': program.version, 'approval': approval_context(program)}),
        reason=TEST, confirmed=True)
    rules = {}
    for code, source, kind, unit, upper in [
            ('SI', 'socioeconomic_assessment', 'decimal', 'assessment units', '100'),
            ('ES', 'employment_status', 'category', 'category', '3'),
            ('PA', 'successful_releases', 'integer', 'records', '10'),
            ('ND', 'dependent_count', 'integer', 'persons', '8')]:
        rules[code] = {'measure': definitions[code]['definition'], 'source_type': source, 'value_type': kind,
            'unit': unit, 'direction': 'inverse' if code == 'PA' else 'benefit',
            'encoding': {'employed': '0', 'self_employed': '1', 'student': '2', 'retired': '3'} if code == 'ES' else None,
            'bounds': {'method': 'fixed', 'lower': '0', 'upper': upper},
            'observation_period': 'All retained confirmed non-voided receipts' if code == 'PA' else
                'Document observation period within 365 days' if code == 'SI' else 'Current verified onsite membership record', 'edge_cases': 'block'}
    policy = {'source_contract': CONTRACT, 'si_requirement': requirement.pk,
        'authority_reference': TEST, 'authorized_scope': 'This fictional food program in the isolated testing environment only',
        'approval_date': str(now.date()), 'effective_from': now.isoformat(), 'effective_until': (now + timedelta(days=365)).isoformat(),
        'selection_rule': 'reasoned_human_within_slots', 'tie_rule': 'reasoned_human', 'tie_procedure': TEST + ' Explain human decisions for tied applicants.',
        'classification_mode': 'none', 'classifications': None, 'edge_cases': 'block', 'pa_scope': 'all_programs',
        'pa_period': 'all_retained', 'pa_start': None, 'pa_end': None, 'criteria': rules, 'eligibility': {}}
    codes = ['SI', 'ES', 'PA', 'ND']
    proposed = {'order': [emphasis] + [c for c in codes if c != emphasis] if emphasis else codes,
        'weights': {c: (7000 if c == emphasis else 1000) if emphasis else 2500 for c in codes}}
    judgments, _, provenance = project(proposed)
    policy['weight_input'] = provenance
    return record_configuration(program.pk, user=actor, expected=configuration_token(program), proposed=policy,
        judgments=judgments, status='LOCKED', reason=TEST, attested=True)
