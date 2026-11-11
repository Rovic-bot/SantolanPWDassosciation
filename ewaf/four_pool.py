"""Versioned four-input capture; PR is retained solely as eligibility provenance."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from . import four_policy as four, source_freshness
from .evidence import canonical, digest, source_context
from .models import ScoringPolicyRevision, CriterionAssessment
from .configuration_services import configuration_context
from .readiness import evaluate


def eligibility(assessment, rules):
    retained = assessment.source_manifest.get('relevance') or {}
    indexed = {item['item_id']: item for item in retained.get('items', [])}
    if assessment.state != 'VERIFIED' or assessment.disputed or retained.get('attested') is not True:
        raise ValidationError('FOUR_PROGRAM_RELEVANCE_UNVERIFIED')
    for role, rule in rules.items():
        item = indexed.get(rule['item'])
        if (not item or item['outcome'] != rule['accepted_outcome'] or not item['explanation'].strip() or
                not item['supporting_reviews'] or not item['mappings']):
            raise ValidationError('FOUR_ELIGIBILITY_REQUIREMENT_UNMET: ' + role)
    return {'assessment': {'id': assessment.pk, 'digest': assessment.digest, 'payload': assessment.payload()},
            'rules': rules, 'findings': retained, 'contributes_to_score': False}


def capture(program, applications, contract, user):
    from accounts.authority_services import enlisted
    from .durable_services import _contract
    if not enlisted():
        raise PermissionDenied('Four-criterion capture requires the generation protocol.')
    from .generation_records import require_owner
    require_owner()
    cutoff = _contract(contract)
    before = source_freshness.observe(program, applications, user)
    policy = ScoringPolicyRevision.objects.filter(program=program).first()
    if not policy or policy.profile != four.PROFILE:
        raise ValidationError('FOUR_EXPLICIT_CONFIGURATION_REQUIRED')
    for row in (policy, policy.configuration, policy.validation, policy.evidence_policy):
        row.clean()
    if policy.source_context != configuration_context(program):
        raise ValidationError('FOUR_CONFIGURATION_STALE')
    snapshot = {'engine': four.POOL_ENGINE, 'contract': contract, 'program': str(program.pk),
        'policy': {'id': policy.pk, 'digest': policy.digest, 'payload': policy.payload()},
        'configuration': policy.configuration.payload(), 'validation': policy.validation.payload(),
        'evidence_policy': policy.evidence_policy.payload(), 'context': configuration_context(program),
        'evaluation_date': str(timezone.localdate()), 'timezone': timezone.get_current_timezone_name(),
        'manifest': [], 'eligible': {}}
    for application in applications:
        source = source_context(application)
        ready = evaluate(application, context=source)
        admitted = application.submitted_at <= cutoff
        snapshot['manifest'].append({'application': str(application.pk), 'in_scope': admitted,
            'status': application.status, 'source_digest': digest(source),
            'eligibility_ready': ready['eligibility_readiness'], 'evidence_complete': ready['criterion_completeness'],
            'readiness_reasons': ready['reasons']})
        if not admitted:
            continue
        if application.status not in ('ELIGIBLE', 'INELIGIBLE'):
            raise ValidationError('ELIGIBILITY_UNRESOLVED')
        if application.status == 'INELIGIBLE':
            case = source['case']
            if (not case or case['eligibility'] != 'ineligible' or not case['active'] or not case['log_matches'] or
                    case['member_version'] != source['member_version'] or case['program_version'] != source['program_version'] or
                    case['decision'] != 'pending'):
                raise ValidationError('INELIGIBLE_OUTCOME_STALE_OR_UNVERIFIED')
            continue
        if not ready['eligibility_readiness'] or not ready['criterion_completeness']:
            raise ValidationError('ELIGIBLE_POOL_EVIDENCE_INCOMPLETE')
        pr = CriterionAssessment.objects.filter(application=application, criterion='PR').first()
        pr.clean()
        if pr.policy_id != policy.evidence_policy_id:
            raise ValidationError('FOUR_ELIGIBILITY_POLICY_MISMATCH')
        gate = eligibility(pr, policy.proposal['eligibility'])
        inputs, assessments = {}, {}
        for code in four.CRITERIA:
            row = CriterionAssessment.objects.filter(application=application, criterion=code).first()
            row.clean()
            rule = policy.proposal['criteria'][code]
            if row.policy_id != policy.evidence_policy_id or any(
                    getattr(row, key) != rule[key] for key in ('source_type', 'value_type', 'unit')):
                raise ValidationError('ASSESSMENT_POLICY_MISMATCH')
            assessments[code] = {'id': row.pk, 'digest': row.digest, 'payload': row.payload()}
            inputs[code] = {'source_type': row.source_type, 'unit': row.unit, 'value': row.value}
        snapshot['eligible'][str(application.pk)] = {'source': source, 'assessments': assessments,
            'inputs': inputs, 'program_relevance_eligibility': gate}
    after = source_freshness.observe(program, applications, user)
    if before != after:
        raise ValidationError('SOURCE_OBSERVATION_CHANGED')
    snapshot['freshness'] = after
    validate(snapshot)
    return policy, canonical(snapshot)


def validate(snapshot):
    from .durable_services import _contract
    from .pool_contracts import MAX_APPLICATIONS
    _contract(snapshot['contract'])
    if snapshot['contract'].get('profile') != four.PROFILE:
        raise ValidationError('FOUR_REQUEST_PROFILE_REQUIRED')
    proposal = four.proposal(snapshot['policy']['payload']['proposal'])
    configuration, validation = snapshot['configuration'], snapshot['validation']
    if (configuration['profile'] != four.PROFILE or validation['profile'] != four.PROFILE or
            snapshot['policy']['payload']['profile'] != four.PROFILE or
            configuration['criteria_order'] != list(four.CRITERIA) or
            validation['result'] != four.ahp(configuration['judgments'])):
        raise ValidationError('FOUR_SNAPSHOT_PROFILE_INVALID')
    manifest = snapshot['manifest']
    ids = [entry['application'] for entry in manifest]
    if (not manifest or len(ids) > MAX_APPLICATIONS or len(set(ids)) != len(ids) or
            snapshot['freshness'].get('version') != source_freshness.VERSION or
            snapshot['freshness'].get('inventory') != ids):
        raise ValidationError('COMPLETE_POOL_MANIFEST_REQUIRED')
    expected = {entry['application'] for entry in manifest if entry['in_scope'] and entry['status'] == 'ELIGIBLE'}
    if not expected or set(snapshot['eligible']) != expected:
        raise ValidationError('COMPLETE_POOL_RESULTS_REQUIRED')
    for entry in manifest:
        if entry['in_scope'] and (entry['status'] not in ('ELIGIBLE', 'INELIGIBLE') or
                entry['status'] == 'ELIGIBLE' and not (entry['eligibility_ready'] and entry['evidence_complete'])):
            raise ValidationError('COMPLETE_POOL_MANIFEST_REQUIRED')
    for accepted in snapshot['eligible'].values():
        if set(accepted['inputs']) != set(four.CRITERIA) or set(accepted['assessments']) != set(four.CRITERIA):
            raise ValidationError('COMPLETE_CRITERION_TRACES_REQUIRED')
        gate = accepted['program_relevance_eligibility']
        if gate['contributes_to_score'] is not False or gate['rules'] != proposal['eligibility']:
            raise ValidationError('FOUR_ELIGIBILITY_PROVENANCE_INVALID')
        payload = gate['assessment']['payload']
        if (payload['criterion'] != 'PR' or payload['state'] != 'VERIFIED' or payload['disputed'] or
                payload['source_manifest']['relevance'] != gate['findings'] or
                digest(payload) != gate['assessment']['digest'] or gate['findings']['attested'] is not True):
            raise ValidationError('FOUR_ELIGIBILITY_PROVENANCE_INVALID')
        indexed = {item['item_id']: item for item in gate['findings']['items']}
        for rule in gate['rules'].values():
            if (rule['item'] not in indexed or indexed[rule['item']]['outcome'] != rule['accepted_outcome'] or
                    not indexed[rule['item']]['supporting_reviews'] or not indexed[rule['item']]['mappings']):
                raise ValidationError('FOUR_ELIGIBILITY_REQUIREMENT_UNMET')


def calculate(snapshot):
    validate(snapshot)
    return {key: four.calculate(inputs=value['inputs'], definitions=snapshot['policy']['payload']['proposal']['criteria'],
        judgments=snapshot['configuration']['judgments'], validation=snapshot['validation']['result'])
        for key, value in snapshot['eligible'].items()}
