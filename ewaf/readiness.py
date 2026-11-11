"""Read-only G12 diagnostics; operational processing deliberately fails closed."""
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from core.permissions import require_workspace_permissions
from programs.models import ProgramApplication, Program
from programs.approval_policy import binding_condition
from .evidence import CRITERIA, criterion_codes, VIEW, source_context, digest
from .models import CriterionAssessment, EvidencePolicyRevision
from .evidence_rules import reuse_issue, substantiate, relevance_findings


def ineligible_exclusion_errors(context):
    """An audited exclusion needs no fresh scoring or eligibility inputs.

    Later member/program edits do not put an ineligible application back in the
    ranking pool. Retain the decision and source history without requiring a
    repeated exclusion review. A raw status without its recorded decision is
    still an integrity error, not an authorized way to omit an applicant.
    """
    case = context.get('case')
    if (case and case['eligibility'] == 'ineligible' and case['active']
            and case['log_matches'] and case['decision'] == 'pending'):
        return []
    return ['INELIGIBLE_OUTCOME_STALE_OR_UNVERIFIED']


def assess_readiness(reference, *, user):
    require_workspace_permissions(user, *VIEW)
    application = ProgramApplication.objects.select_related('program', 'member__application', 'current_photo').get(pk=reference)
    return evaluate(application)


def evaluate(application, *, context=None):
    context = source_context(application) if context is None else context
    today = timezone.localdate()
    groups = {key: [] for key in ('eligibility', 'criteria', 'governance', 'processing')}
    confirmation = context.get('current_information')
    if confirmation and not confirmation.get('resolved'):
        groups['criteria'].append({'code': 'CURRENT_INFORMATION_REVIEW_REQUIRED', 'source': context['application']})

    def add(group, code, source=None):
        groups[group].append({'code': code, 'source': source})

    if not context['member_active']:
        add('eligibility', 'MEMBER_INACTIVE', context['member'])
    membership = context['membership']
    if not (membership['status'] == 'approved' and membership['verified'] is True and
            membership['verified_at'] and membership['decided_at'] and
            membership['verified_by'] and membership['decided_by'] and membership['audit_matches']):
        add('eligibility', 'MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED', membership['intake'])
    if not context['reference_present'] or not context['submitted_at']:
        add('eligibility', 'APPLICATION_INVALID', context['application'])
    if not context['submission_provenance_valid']:
        add('eligibility', 'SUBMISSION_PROVENANCE_REVIEW_REQUIRED', context['application'])
    if context['status'] != 'ELIGIBLE':
        add('eligibility', 'APPLICATION_NOT_CANDIDATE', context['application'])
    classifications = context.get('disabilities', [context['disability']] if context['disability'] else [])
    if context['qualifications'] and not set(classifications).intersection(context['active_qualifications']):
        add('eligibility', 'QUALIFICATION_REVIEW_REQUIRED' if not classifications else 'QUALIFICATION_FAILED', context['member'])
    photo = context['photo']
    if context.get('calendar_photo_required', True) and not (photo and photo['application'] == context['application'] and photo['outcome'] == 'VERIFIED' and
            photo['member_version'] == context['member_version'] and photo['digest']):
        add('eligibility', 'IDENTITY_REVIEW_REQUIRED', photo['id'] if photo else None)
    case = context['case']
    if not case or case['eligibility'] != 'eligible' or not case['active']:
        add('eligibility', 'ELIGIBILITY_INELIGIBLE' if case and case['eligibility'] == 'ineligible' else 'ELIGIBILITY_PENDING', case['id'] if case else None)
    if case:
        schedule = context.get('eligibility_schedule_revision', {})
        program_current = (case['program_version'] == context['program_version'] or
            schedule.get('contract') == 'eligibility-date-only-revision-v1'
            and schedule.get('review_program_version') == case['program_version']
            and schedule.get('current_program_version') == context['program_version']
            and bool(schedule.get('witnesses')))
        if case['member_version'] != context['member_version'] or not program_current or not case['log_matches']:
            add('eligibility', 'ELIGIBILITY_STALE', case['review_log'])
        if case['decision'] != 'pending':
            add('eligibility', 'HISTORICAL_DECISION_REASSESSMENT_REQUIRED', case['id'])
    expected = {'membership', 'other_requirements'}
    if context['qualifications']:
        expected.add('disability')
    checklist = case['checklist'] if case and isinstance(case['checklist'], list) else []
    entries = {str(item.get('key')): item for item in checklist if isinstance(item, dict)}
    if len(entries) != len(checklist):
        add('eligibility', 'CHECKLIST_INCOMPLETE', case['id'] if case else None)
    documents = {row['requirement']: row for row in context['documents']}
    requirements = context['requirements']
    if not isinstance(requirements, list):
        requirements = []
        add('eligibility', 'APPLICATION_INVALID', context['application'])
    for requirement in requirements:
        if not isinstance(requirement, dict) or not {'id', 'kind', 'is_required'} <= set(requirement):
            add('eligibility', 'APPLICATION_INVALID', context['application'])
            continue
        if not requirement['is_required']:
            continue
        key = str(requirement['id'])
        expected.add(key)
        if requirement['kind'] == 'document':
            document = documents.get(requirement['id'])
            if not document or not document['digest']:
                add('eligibility', 'REQUIRED_EVIDENCE_MISSING', requirement['id'])
                continue
            issue = reuse_issue(document, requirement, context, today)
            if issue:
                add('eligibility', issue, document['id'])
        elif not application.answers.get(key):
            add('eligibility', 'REQUIRED_EVIDENCE_MISSING', requirement['id'])
    if any(key not in entries or entries[key].get('required') is not True or entries[key].get('result') != 'pass' for key in expected):
        add('eligibility', 'CHECKLIST_INCOMPLETE', case['id'] if case else None)
    if any(item.get('required') and item.get('result') != 'pass' for item in entries.values()):
        add('eligibility', 'CHECKLIST_FAILED', case['id'] if case else None)
    policy = EvidencePolicyRevision.objects.filter(program=application.program).first()
    if policy:
        try:
            policy.clean()
        except ValidationError:
            add('governance', 'ARTIFACT_INTEGRITY_FAILED', policy.pk)
    assessments = []
    for criterion in criterion_codes(policy.snapshot) if policy else CRITERIA:
        row = CriterionAssessment.objects.filter(application=application, criterion=criterion).first()
        detail = {'criterion': criterion, 'assessment': row.pk if row else None, 'state': row.state if row else 'MISSING', 'current': False}
        start = len(groups['criteria'])
        if not row:
            add('criteria', 'CRITERION_MISSING', criterion)
        else:
            if row.state != 'VERIFIED':
                add('criteria', 'CRITERION_REJECTED' if row.state == 'REJECTED' else 'CRITERION_NOT_VERIFIED', row.pk)
            if row.disputed:
                add('criteria', 'EVIDENCE_DISPUTED', row.pk)
            if row.state == 'VERIFIED':
                if row.source_manifest.get('evidence_contract_version') != 2:
                    add('criteria', 'EVIDENCE_CONTRACT_REVIEW_REQUIRED', row.pk)
                else:
                    try:
                        if criterion in ('SI', 'ES', 'ND', 'HI', 'HM'):
                            expected_mappings = substantiate(row.supporting_reviews,
                                row.policy.snapshot['criteria'][criterion].get('evidence_mappings', {}).get(row.source_type))
                            if expected_mappings != row.source_manifest.get('evidence_mappings'):
                                raise ValidationError('Retained mapping differs.', code='EVIDENCE_MAPPING_INVALID')
                        if criterion == 'PR':
                            retained = row.source_manifest.get('relevance') or {}
                            findings = [{'item_id': item['item_id'], 'outcome': item['outcome'],
                                'explanation': item['explanation'], 'review_ids': [review['id'] for review in item['supporting_reviews']]}
                                for item in retained.get('items', [])]
                            resolved = relevance_findings(application, row.policy, context, findings, retained.get('attested'), today)
                            if resolved != retained:
                                raise ValidationError('Relevance evidence changed.', code='PR_EVIDENCE_INVALID')
                    except ValidationError as error:
                        add('criteria', getattr(error, 'code', None) or 'CRITERION_EVIDENCE_UNSUPPORTED', row.pk)
            if row.expires_on and row.expires_on < today:
                add('criteria', 'EVIDENCE_EXPIRED', row.pk)
            for supporting in row.supporting_reviews:
                if supporting.get('expires_on') and supporting['expires_on'] < str(today):
                    add('criteria', 'EVIDENCE_EXPIRED', supporting['id'])
            if not policy or row.policy_id != policy.pk:
                add('criteria', 'CRITERION_POLICY_CHANGED', row.pk)
            if digest(row.source_manifest) != row.source_digest or row.source_manifest.get('context') != context:
                add('criteria', 'SOURCE_CHANGED', row.pk)
            if digest(row.payload()) != row.digest:
                add('criteria', 'ARTIFACT_INTEGRITY_FAILED', row.pk)
            try:
                row.clean()
            except ValidationError:
                add('criteria', 'ARTIFACT_INTEGRITY_FAILED', row.pk)
            detail['current'] = len(groups['criteria']) == start
        assessments.append(detail)
    program = application.program
    if not program.ewaf_applicable:
        add('governance', 'EWAF_NOT_APPLICABLE', str(program.pk))
    if not program.policy_authorized_at or not program.selection_method.strip():
        add('governance', 'PROGRAM_POLICY_UNAUTHORIZED', str(program.pk))
    if program.status != 'published' or not program.published_at or program.published_at > timezone.now():
        add('governance', 'PROGRAM_UNAVAILABLE', str(program.pk))
    authority = context['approval']
    # Match publication and scoring-policy binding: offline external approval
    # does not require an in-system PDAO record. The operational configuration
    # still validates its own immutable program-terms snapshot before scoring.
    if settings.PDAO_ENFORCEMENT_ENABLED:
        if not Program.objects.filter(pk=program.pk).filter(binding_condition()).exists():
            add('governance', 'BINDING_INVALID', authority['binding'])
        if authority['terms_digest'] != authority['actual_terms_digest']:
            add('governance', 'TERMS_CHANGED', authority['terms_revision'])
    if policy and (policy.terms_revision_id != authority['terms_revision'] or policy.terms_digest != authority['terms_digest']):
        add('governance', 'POLICY_TERMS_CHANGED', policy.pk)
    # G12 records definitions. No operational evidence-policy approval contract
    # exists; an authority reference or a VERIFIED finding cannot supply one.
    add('governance', 'CRITERION_POLICY_UNAPPROVED', policy.pk if policy else None)
    add('processing', 'PROCESSING_GATE_UNAVAILABLE')
    return {'schema_version': 1, 'service_version': 'g12-v2', 'evaluated_at': timezone.now().isoformat(),
        'eligibility_readiness': not groups['eligibility'], 'criterion_completeness': not groups['criteria'],
        'governance_readiness': not groups['governance'], 'processing_authorization_readiness': False,
        'operational_ready': False, 'reasons': groups, 'criteria': assessments,
        'context_digest': digest(context), 'source_manifest': context,
        'integrity_note': 'Photo and direct-upload hashes describe bytes observed now, not bytes authenticated at an earlier review.'}


def require_operational_evidence(*args, **kwargs):
    raise ValidationError('PROCESSING_GATE_UNAVAILABLE', code='PROCESSING_GATE_UNAVAILABLE')
