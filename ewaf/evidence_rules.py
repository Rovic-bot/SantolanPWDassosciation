"""Explicit recorded evidence contracts; no Association defaults or operational authority."""
from django.core.exceptions import ValidationError
from .evidence import digest


def fail(code, message):
    raise ValidationError(f'{code}: {message}', code=code)


def validate_mappings(mappings):
    if not isinstance(mappings, list) or not mappings or len(mappings) > 30:
        fail('EVIDENCE_MAPPING_PENDING', 'Record specific accepted evidence mappings and their authority.')
    for mapping in mappings:
        if (not isinstance(mapping, dict) or set(mapping) != {
                'document_type_id', 'membership_requirement_id', 'basis', 'authority_reference'} or
                any(type(mapping.get(key)) is not int or mapping[key] < 1
                    for key in ('document_type_id', 'membership_requirement_id')) or
                any(not isinstance(mapping.get(key), str) or not mapping[key].strip() or len(mapping[key]) > 500
                    for key in ('basis', 'authority_reference'))):
            fail('EVIDENCE_MAPPING_PENDING', 'Each mapping needs exact source identities, basis and authority reference.')


def validate_contract(rule):
    mappings = rule.get('evidence_mappings', {})
    if not isinstance(mappings, dict) or set(mappings) - set(rule['source_types']):
        fail('EVIDENCE_MAPPING_PENDING', 'Mappings must belong to a declared criterion source type.')
    for rows in mappings.values():
        validate_mappings(rows)
    rubric = rule.get('rubric_definition')
    if rubric is None:
        return
    if (not isinstance(rubric, dict) or set(rubric) != {
            'program_id', 'version', 'terms_digest', 'authority_reference', 'items'} or
            not isinstance(rubric['program_id'], str) or
            type(rubric['version']) is not int or rubric['version'] < 1 or
            not isinstance(rubric['terms_digest'], str) or len(rubric['terms_digest']) != 64 or
            not isinstance(rubric['authority_reference'], str) or not rubric['authority_reference'].strip() or
            not isinstance(rubric['items'], list) or not rubric['items'] or len(rubric['items']) > 30):
        fail('PR_RUBRIC_PENDING', 'A versioned program-specific rubric and authority are required.')
    identifiers = set()
    for item in rubric['items']:
        if (not isinstance(item, dict) or set(item) != {
                'id', 'requirement_id', 'applicability', 'outcomes', 'evidence_mappings'} or
                not isinstance(item['id'], str) or not item['id'].strip() or len(item['id']) > 80 or
                item['id'] in identifiers or type(item['requirement_id']) is not int or
                item['applicability'] != 'all_applications' or
                not isinstance(item['outcomes'], dict) or not item['outcomes'] or
                any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                    for k, v in item['outcomes'].items())):
            fail('PR_RUBRIC_PENDING', 'Each rubric item needs a stable ID, requirement, explicit applicability and defined findings.')
        identifiers.add(item['id'])
        validate_mappings(item['evidence_mappings'])


def validate_policy_relationships(snapshot, program):
    """Recording officer claims documented authority; this does not approve operation."""
    from documents.models import MembershipDocumentRequirement
    from programs.models import ProgramRequirement
    for rule in snapshot['criteria'].values():
        lists = list(rule.get('evidence_mappings', {}).values())
        rubric = rule.get('rubric_definition')
        if rubric:
            if rubric['program_id'] != str(program.pk):
                fail('PR_RUBRIC_PENDING', 'The rubric belongs to another program.')
            for item in rubric['items']:
                if not ProgramRequirement.objects.filter(pk=item['requirement_id'], program=program, is_active=True).exists():
                    fail('PR_RUBRIC_PENDING', 'Rubric requirements must belong to this program.')
                lists.append(item['evidence_mappings'])
        for mappings in lists:
            for mapping in mappings:
                if not MembershipDocumentRequirement.objects.filter(pk=mapping['membership_requirement_id'],
                        document_type_id=mapping['document_type_id']).exists():
                    fail('EVIDENCE_MAPPING_INVALID', 'Document type does not match the recorded membership requirement.')


def substantiate(reviews, mappings):
    validate_mappings(mappings)
    if not reviews:
        fail('CRITERION_EVIDENCE_UNSUPPORTED', 'Current evidence for the specific criterion/source is required.')
    accepted = []
    for review in reviews:
        match = next((row for row in mappings if row['document_type_id'] == review.get('document_type')
                      and row['membership_requirement_id'] == review.get('membership_requirement')), None)
        if not match:
            fail('CRITERION_EVIDENCE_UNSUPPORTED', 'A supporting document does not substantiate this criterion/source under the recorded mapping.')
        accepted.append({'review': review['id'], 'mapping_digest': digest(match)})
    return accepted


def reuse_issue(document, requirement, context, today):
    """Exact immutable requirement -> source type -> current verification -> bytes."""
    if document['program'] != context['program'] or document['requirement'] != requirement['id']:
        return 'EVIDENCE_REFERENCE_INVALID'
    if not document['source']:
        return 'EVIDENCE_REFERENCE_INVALID' if document['source_verification'] else None
    expected = requirement.get('reusable_document_type_id')
    if type(expected) is not int or expected < 1:
        return 'REUSABLE_TYPE_DEFINITION_PENDING'
    review = document['latest_verification']
    if (expected != document['reusable_document_type'] or expected != document['source_document_type'] or
            document['source_membership_requirement'] is None):
        return 'REUSABLE_TYPE_MISMATCH'
    if (document['source_member_application'] != context['membership']['intake'] or not review or
            review['id'] != document['source_verification'] or review['document'] != document['source'] or
            review['membership_requirement'] != document['source_membership_requirement'] or
            review['document_type'] != expected):
        return 'SOURCE_CHANGED'
    if not review['verified']:
        return 'EVIDENCE_REJECTED'
    if review['expires_on'] and review['expires_on'] < str(today):
        return 'EVIDENCE_EXPIRED'
    if (review['member_version'] != context['member_version'] or not document['digest'] or
            review['digest'] != document['digest'] or review['digest'] != document['source_digest']):
        return 'SOURCE_CHANGED'
    return None


def relevance_findings(application, policy, context, findings, attested, at):
    from programs.models import Program
    from programs.approval_policy import binding_condition
    from programs.terms import snapshot_terms, terms_digest
    from .evidence import resolve_reviews
    rule = policy.snapshot['criteria']['PR']
    rubric = rule.get('rubric_definition')
    if not rubric:
        fail('PR_RUBRIC_PENDING', 'A generic rubric description cannot verify program relevance.')
    terms = snapshot_terms(application.program)
    authority = context['approval']
    if (rubric['program_id'] != str(application.program_id) or
            rubric['terms_digest'] != terms_digest(terms) or
            policy.terms_digest != authority['terms_digest'] or
            policy.terms_revision_id != authority['terms_revision'] or
            authority['terms_digest'] != rubric['terms_digest'] or
            not Program.objects.filter(pk=application.program_id).filter(binding_condition()).exists()):
        fail('PR_REQUIREMENTS_STALE', 'Rubric must reference the current retained approved program requirements.')
    case = context['case']
    if not case or not case['log_matches'] or case['member_version'] != context['member_version'] or case['program_version'] != context['program_version']:
        fail('PR_REQUIREMENTS_STALE', 'Current documented eligibility review findings are required.')
    if attested is not True:
        fail('PR_ATTESTATION_REQUIRED', 'The reviewing officer must attest to the item findings and cited authority.')
    if not isinstance(findings, list) or len(findings) != len(rubric['items']):
        fail('PR_FINDINGS_INCOMPLETE', 'Record one evidence-backed finding for every rubric item.')
    indexed = {}
    for finding in findings:
        if (not isinstance(finding, dict) or set(finding) != {'item_id', 'outcome', 'explanation', 'review_ids'} or
                not isinstance(finding['item_id'], str) or finding['item_id'] in indexed or
                not isinstance(finding['outcome'], str) or not isinstance(finding['explanation'], str) or
                not finding['explanation'].strip() or len(finding['explanation']) > 500):
            fail('PR_FINDINGS_INCOMPLETE', 'Use distinct item IDs, defined outcomes, minimal explanations and review IDs.')
        indexed[finding['item_id']] = finding
    retained = []
    for item in rubric['items']:
        finding = indexed.get(item['id'])
        requirement = next((row for row in context['requirements'] if row['id'] == item['requirement_id']), None)
        current = next((row for row in terms['requirements'] if row['id'] == item['requirement_id']), None)
        if not requirement or not current or not current['is_active'] or any(
                requirement.get(key) != current[key] for key in ('kind', 'label', 'instructions', 'is_required', 'position')):
            fail('PR_REQUIREMENTS_STALE', 'Application requirements differ from the current approved rubric requirements.')
        if not finding or finding['outcome'] not in item['outcomes']:
            fail('PR_FINDINGS_INCOMPLETE', 'Every item requires a finding from its documented outcomes.')
        reviews = resolve_reviews(application, finding['review_ids'], at=at)
        mapping = substantiate(reviews, item['evidence_mappings'])
        if requirement['kind'] == 'document':
            document = next((row for row in context['documents'] if row['requirement'] == requirement['id']), None)
            if not document or not document['source'] or reuse_issue(document, requirement, context, at) or document['source_verification'] not in finding['review_ids']:
                fail('PR_EVIDENCE_INVALID', 'Document findings require the exact current verified program evidence.')
            source = {'document': document['id'], 'digest': document['digest']}
        else:
            answer = application.answers.get(str(requirement['id']))
            if not answer:
                fail('PR_EVIDENCE_INVALID', 'The current application answer is missing.')
            source = {'requirement': requirement['id'], 'answer_digest': digest(answer)}
        retained.append({'item_id': item['id'], 'outcome': finding['outcome'], 'explanation': finding['explanation'],
                         'requirement_digest': digest(requirement), 'source': source,
                         'supporting_reviews': reviews, 'mappings': mapping})
    return {'rubric_version': rubric['version'], 'rubric_digest': digest(rubric),
            'authority_reference': rubric['authority_reference'], 'attested': True, 'items': retained}
