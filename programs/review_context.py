"""Shared, permission-aware applicant details for application and eligibility review."""
from .workflow import PHOTO_VIEW, calendar_photo_required


def identity_status(application, user):
    if not calendar_photo_required(application):
        return 'Not required'
    if not user.has_perms(PHOTO_VIEW):
        return 'Restricted'
    from django.core.exceptions import ValidationError
    from .workflow import require_verified_photo
    try:
        require_verified_photo(application, application.member)
        return 'Verified'
    except ValidationError:
        return 'Needs review'


def applicant_context(application, user, *, document_review=None, include_member_information=True):
    from .information_confirmation import VIEW, UPDATE, declaration, confirmation_context
    context = {
        'application_confirmation': declaration(application) if user.has_perms(VIEW) else None,
        'confirmation_status': confirmation_context(application) if user.has_perms(VIEW) else None,
        'can_review_confirmation': user.has_perms(UPDATE),
        'can_view_photo': user.has_perms(PHOTO_VIEW),
        'can_review_photo': calendar_photo_required(application) and user.has_perms((*PHOTO_VIEW, 'programs.review_applicationphoto')) and application.status in
            ('PENDING_PHOTO_VERIFICATION', 'NEEDS_INFORMATION', 'PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW'),
        'documents': application.documents.all() if user.has_perm('programs.view_programdocument') else [],
        'membership_documents': application.member.application.documents.select_related('requirement')
            if include_member_information and user.has_perms(('members.view_member', 'documents.view_membershipapplicationdocument')) else [],
        'can_review_documents': user.has_perms(('members.view_member',
            'documents.view_membershipapplicationdocument', 'documents.verify_document')),
        'can_view_membership': user.has_perms(('members.view_member', 'membership.view_membershipapplication')),
        'can_view_program_documents': user.has_perm('programs.view_programdocument'),
        'can_correct_application': user.has_perms((*PHOTO_VIEW,
            'programs.resubmit_applicationphoto', 'programs.view_programdocument')),
    }
    from django.urls import reverse
    report = context['application_confirmation'] or {}
    context['member_edit_url'] = (reverse('programs:information_review', args=[application.pk])
        if context['can_review_confirmation'] and report.get('current_information') in ('changed', 'uncertain')
        else reverse('members:edit', args=[application.member_id]))
    from django.core.exceptions import ValidationError
    from .services import disability_matches
    from assistance.models import AssistanceCase
    from assistance.services import VIEW_PERMISSIONS
    from documents.services import file_digest, program_document_current
    from django.utils import timezone
    case = AssistanceCase.objects.filter(application=application).first() if user.has_perms(VIEW_PERMISSIONS) else None
    checks = {row['key']: row['result'] for row in case.checklist} if (
        case and case.member_version == application.member.version and case.program_version == application.program.version) else {}
    context['membership_status'] = ('Verified' if application.member.is_active and not application.member.archived_at
        and application.member.application.status == 'approved' else 'Needs review')
    if include_member_information and context['can_view_membership']:
        context['membership_intake'] = application.member.application
    if user.has_perm('members.view_member'):
        member_ids = set(application.member.disability_ids)
        qualifications = list(application.program.eligible_disability_types.all())
        context['disability_comparison'] = [{'name': item.name,
            'status': 'Matches' if item.pk in member_ids and item.is_active else
                      'Inactive classification' if not item.is_active else 'Does not match'} for item in qualifications]
    for document in context['membership_documents']:
        if document.requirement.capture_key == 'photo_1x1' and document.content_type in ('image/jpeg', 'image/png'):
            context['member_portrait'] = document
        verification = document.verifications.first()
        digest = file_digest(document)
        if verification and verification.expires_on and verification.expires_on < timezone.localdate():
            document.review_status = 'Expired'
        elif (verification and verification.verified and verification.member_version == application.member.version
              and verification.file_digest == digest):
            document.review_status = 'Verified'
        else:
            document.review_status = 'Needs verification'
        document.review_button_label = 'Review' if document.review_status == 'Verified' else 'Needs Review'
        if context['can_review_documents']:
            from documents.forms import QuickReviewForm
            document.review_form = (document_review[1] if document_review and document_review[0] == document.pk else
                QuickReviewForm(prefix=f'document-{document.pk}', initial={'member_version': application.member.version,
                    'review_id': verification.pk if verification else 0, 'document_digest': digest}))
    context['review_documents'] = [
        {'document': row, 'status': {'pass': 'Verified', 'fail': 'Not met'}.get(checks.get(str(row.requirement_id)), 'Needs review')
            if program_document_current(row, application.member) else 'Needs verification'}
        for row in context['documents']]
    context['photo_status'] = identity_status(application, user)
    if context['can_view_photo'] and application.current_photo_id:
        context['latest_photo_review'] = application.current_photo.reviews.first()
    context['eligibility_summary'] = [
        ('Association membership', context['membership_status']),
        ('Photo / identity', context['photo_status']),
        ('Disability qualification', 'Matches' if disability_matches(application.program, application.member) else 'Does not match'),
    ]
    required_ids = {row['id'] for row in application.requirements_snapshot if row['is_required']}
    documents_current = all(row['status'] == 'Verified' for row in context['review_documents']
                            if row['document'].requirement_id in required_ids)
    submitted_ids = {row['document'].requirement_id for row in context['review_documents']}
    required_present = all(item['id'] in submitted_ids if item['kind'] == 'document' else
        bool(application.answers.get(str(item['id']))) for item in application.requirements_snapshot if item['is_required'])
    requirements_ready = required_present and documents_current and checks.get('other_requirements') == 'pass' and all(
        checks.get(str(pk)) == 'pass' for pk in required_ids)
    context['eligibility_summary'].append(('Required documents and instructions',
                                          'Verified' if requirements_ready else 'Needs review'))
    # Inventory includes absent requirements, not just files that happened to be uploaded.
    context['program_requirement_rows'] = []
    if context['can_view_program_documents']:
        by_requirement = {row['document'].requirement_id: row for row in context['review_documents']}
        for requirement in application.requirements_snapshot:
            row = by_requirement.get(requirement['id'])
            submitted = bool(row) if requirement['kind'] == 'document' else bool(application.answers.get(str(requirement['id'])))
            result = checks.get(str(requirement['id']))
            status = ('Missing' if requirement['is_required'] else 'Not required') if not submitted else (
                'Rejected' if result == 'fail' else row['status'] if row else
                'Verified' if result == 'pass' else 'Needs review')
            context['program_requirement_rows'].append({**requirement, 'status': status,
                'document': row['document'] if row else None})
    context['program_instructions_status'] = {'pass': 'Verified', 'fail': 'Not met'}.get(checks.get('other_requirements'), 'Needs review')
    context['qualification_status'] = 'Not required'
    if application.program.ewaf_applicable:
        from ewaf.evidence import VIEW, criterion_codes
        from ewaf.household_criteria import CRITERIA, NAMES
        context['qualification_status'] = 'Restricted'
        if user.has_perms(VIEW):
            assessments = {row.criterion: row for row in application.criterion_assessments.order_by('criterion', 'revision')}
            from ewaf.models import EvidencePolicyRevision
            policy = EvidencePolicyRevision.objects.filter(program=application.program).first()
            codes = criterion_codes(policy.snapshot) if policy else CRITERIA
            context['input_reviews'] = [
                {'code': code, 'label': NAMES[code], 'assessment': assessments.get(code)} for code in codes if code != 'PR'
            ]
            from ewaf.evidence import source_context
            from django.utils import timezone
            assessment = assessments.get('PR')
            from ewaf.models import EvidencePolicyRevision
            policy = EvidencePolicyRevision.objects.filter(program=application.program).first()
            current = bool(assessment and assessment.state == 'VERIFIED' and not assessment.disputed
                and policy and assessment.policy_id == policy.pk
                and (not assessment.expires_on or assessment.expires_on >= timezone.localdate())
                and assessment.source_manifest.get('context') == source_context(application))
            if current:
                from ewaf.evidence_rules import relevance_findings
                try:
                    assessment.clean()
                    findings = [{'item_id': item['item_id'], 'outcome': item['outcome'],
                        'explanation': item['explanation'],
                        'review_ids': [review['id'] for review in item['supporting_reviews']]}
                        for item in assessment.source_manifest.get('relevance', {}).get('items', [])]
                    relevance_findings(application, policy, source_context(application), findings, True, timezone.localdate())
                except ValidationError:
                    current = False
            requirement_met = True
            if current:
                from ewaf.operational_services import available, configuration_source
                if available():
                    from ewaf.operational_models import OperationalConfiguration
                    configuration = OperationalConfiguration.objects.filter(program=application.program, status='LOCKED').first()
                    if configuration:
                        try:
                            configuration.clean()
                            current = configuration.source == configuration_source(application.program)
                            if current:
                                from ewaf.four_pool import eligibility
                                eligibility(assessment, configuration.policy['eligibility'])
                        except ValidationError:
                            requirement_met = False
            context['qualification_current'] = current
            context['qualification_assessment'] = assessment
            context['qualification_status'] = ('Verified' if requirement_met else 'Not met') if current else 'Needs review'
            rubric = (policy.snapshot['criteria']['PR'].get('rubric_definition') or {}) if policy else {}
            requirements = {item['id']: item for item in application.requirements_snapshot}
            findings = {item['item_id']: item for item in (assessment.source_manifest.get('relevance', {}).get('items', []) if assessment else [])}
            context['qualification_findings'] = [{'label': requirements.get(item['requirement_id'], {}).get('label', 'Program requirement'),
                'instructions': requirements.get(item['requirement_id'], {}).get('instructions', ''),
                'outcome': item['outcomes'].get(findings.get(item['id'], {}).get('outcome'), 'Needs review')}
                for item in rubric.get('items', [])]
            context['eligibility_summary'].append(('Program fit and required consent', context['qualification_status']))
    context['eligibility_checks'] = [
        {'key': 'membership', 'label': 'Association Membership', 'target': 'membership-review',
         'status': context['membership_status'] if user.has_perm('members.view_member') else 'Restricted'},
        {'key': 'photo', 'label': 'Photo / Identity', 'target': 'photo-review', 'status': context['photo_status']},
        {'key': 'disability', 'label': 'Disability Qualification', 'target': 'disability-review',
         'status': ('Matches' if disability_matches(application.program, application.member) else 'Does not match')
             if user.has_perm('members.view_member') and application.program.eligible_disability_types.exists() else
             'Not required' if user.has_perm('members.view_member') else 'Restricted'},
        {'key': 'documents', 'label': 'Required Documents', 'target': 'documents',
         'status': ('Verified' if requirements_ready else 'Needs review') if context['can_view_program_documents'] else 'Restricted'},
    ]
    if application.program.ewaf_applicable:
        context['eligibility_checks'].append({'key': 'qualification', 'label': 'Program Fit / Consent',
            'target': 'program-fit-review', 'status': context['qualification_status']})
    context['review_result'] = case.eligibility_label if case else (
        'Not reviewed' if user.has_perms(VIEW_PERMISSIONS) else 'Restricted')
    context['review_code'] = case.eligibility_id if case else 'review'
    context['review_explanation'] = {
        'eligible': 'Recorded eligible. Submitted information and required evidence are shown below.',
        'ineligible': 'The recorded review found a program requirement was not met.',
    }.get(context['review_code'], 'Review the saved information and required evidence before deciding.')
    from .applicant_information import applicant_information
    if include_member_information:
        context.update(applicant_information(application, user))
    direct_review = bool(case and any(item['key'] == 'admin_review' for item in case.checklist))
    if direct_review:
        context['review_explanation'] = 'Administrator eligibility decision recorded.'
    if case and case.eligibility_id == 'eligible' and any(
            status in ('Needs review', 'Does not match', 'Not met') for label, status in context['eligibility_summary']
            if not (direct_review and label == 'Program fit and required consent')):
        # Keep the saved human decision intact; do not present stale evidence as current verification.
        context.update(review_result='Review needed', review_code='review',
                       review_explanation='Earlier result: Eligible. Some required evidence needs review.')
    return context
