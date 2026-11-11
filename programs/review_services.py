"""Combined Admin eligibility review; keep applicable PR evidence outside scoring."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.permissions import require_workspace_permissions
from assistance.services import review_eligibility
from .models import ProgramApplication
from .terms import terms_lock


DIRECT_REVIEW_PERMISSIONS = (
    'programs.view_program', 'programs.view_programapplication', 'members.view_member',
    'assistance.view_assistancecase', 'assistance.review_eligibility',
    'programs.view_programdocument', 'programs.view_applicationphoto',
    'programs.review_applicationphoto', 'documents.view_membershipapplicationdocument',
)
DIRECT_REVIEW_STATUSES = ('PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW',
                          'NEEDS_INFORMATION', 'ELIGIBLE')


def decision_availability(application):
    if application.status in DIRECT_REVIEW_STATUSES:
        return True, ''
    if application.status == 'COMPLETED':
        from assistance.reassessment import completed_receipt
        try:
            completed_receipt(application)
        except ValidationError as error:
            return False, ' '.join(error.messages)
        return True, ''
    return False, 'This application has a final or closed decision.'


@terms_lock()
@transaction.atomic
def review_submitted_application(reference, *, user, data, address=None):
    """One human decision over the displayed submission, with retained audits."""
    from assistance.services import locked_application, require_unreleased
    from documents.services import program_document_current
    from events.services import check_version
    from ewaf.evidence import source_context, digest
    from .application_workflow import confirmed_member
    from .review_forms import ApplicationDecisionForm
    from .workflow import require_verified_photo, review_photo
    require_workspace_permissions(user, *DIRECT_REVIEW_PERMISSIONS)
    application, program, member = locked_application(reference, user, 'assistance.review_eligibility')
    application.program, application.member = program, member
    form = ApplicationDecisionForm(data, application=application)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    check_version(application, values['version'])
    if (member.version != values['member_version'] or program.version != values['program_version']
            or values['expected_context'] != digest(source_context(application))):
        raise ValidationError('The application or supporting information changed. Reload before reviewing.')
    available, unavailable_reason = decision_availability(application)
    if not available:
        raise ValidationError(unavailable_reason)
    completed = application.status == 'COMPLETED'
    if not completed:
        require_unreleased(application)
    outcome = values['eligibility']
    label = dict(form.fields['eligibility'].choices)[outcome]
    notes = values['notes'].strip() or f'Administrator marked {label} after reviewing the submitted application.'
    documents = {row.requirement_id for row in application.documents.select_related('source_document')
                 if program_document_current(row, member)}
    payload = {'version': application.version, 'member_version': member.version, 'program_version': program.version,
               'eligibility': outcome, 'notes': notes, 'other_requirements': 'pass' if outcome == 'eligible' else 'review'}
    for item in application.requirements_snapshot:
        present = item['id'] in documents if item['kind'] == 'document' else bool(application.answers.get(str(item['id'])))
        if outcome == 'eligible' and item['is_required'] and not present:
            raise ValidationError(f'{item["label"]}: the required submission is missing or no longer current. Choose Needs Information.')
        payload[f'check_{item["id"]}'] = 'pass' if outcome == 'eligible' and present else 'review'
    if outcome == 'eligible':
        if not confirmed_member(member):
            raise ValidationError('An active, approved member record is required. Choose Needs Information or Ineligible.')
        from .services import require_disability
        require_disability(program, member)
        if program.status != 'published' or not program.policy_authorized_at:
            raise ValidationError('Publish and authorize the program before marking an application Eligible.')
        try:
            require_verified_photo(application, member)
        except ValidationError:
            # Eligible is the administrator's explicit review of the displayed
            # identity evidence; it is never inferred from uploading a file.
            review_photo(reference, user=user, address=address, completed_reassessment=completed, data={
                'version': application.version, 'photo_id': application.current_photo_id,
                'outcome': 'VERIFIED', 'confirm': True,
                'reason': ('Identity evidence reviewed as part of the Eligible action. ' + notes)[:2000]})
            application.refresh_from_db()
            payload['version'] = application.version
    case = review_eligibility(reference, user=user, data=payload, address=address, direct_review=True)
    application.refresh_from_db(fields=['version'])
    from .decision_email import queue_decision_email
    queue_decision_email(application, outcome=outcome, remarks=values['notes'].strip(), user=user)
    return case


@terms_lock()
@transaction.atomic
def complete_eligibility_review(reference, *, user, data, address=None):
    application = ProgramApplication.objects.select_related('program', 'member__application').get(pk=reference)
    retained = None
    if data.get('eligibility') == 'eligible' and application.program.ewaf_applicable:
        from ewaf.models import EvidencePolicyRevision, CriterionAssessment
        from ewaf.evidence import VIEW, source_context
        from ewaf.evidence_rules import relevance_findings
        policy = EvidencePolicyRevision.objects.filter(program=application.program).first()
        if not policy or not policy.snapshot['criteria']['PR'].get('rubric_definition'):
            raise ValidationError('The required program qualification definition is missing. Keep this application pending until it is authorized.')
        if policy and policy.snapshot['criteria']['PR'].get('rubric_definition'):
            require_workspace_permissions(user, *VIEW, 'ewaf.review_criterionassessment')
            assessment = CriterionAssessment.objects.filter(application=application, criterion='PR').first()
            context = source_context(application)
            if (not assessment or assessment.policy_id != policy.pk or assessment.state != 'VERIFIED'
                    or assessment.disputed or (assessment.expires_on and assessment.expires_on < timezone.localdate())
                    or assessment.source_manifest.get('context') != context):
                raise ValidationError('Verify the current program qualification and functional need below before marking this application Eligible.')
            assessment.clean()
            retained = [{'item_id': item['item_id'], 'outcome': item['outcome'],
                         'explanation': item['explanation'],
                         'review_ids': [review['id'] for review in item['supporting_reviews']]}
                        for item in assessment.source_manifest['relevance']['items']]
            relevance_findings(application, policy, context, retained, True, timezone.localdate())
            from ewaf.operational_services import available, configuration_source
            if available():
                from ewaf.operational_models import OperationalConfiguration
                configuration = OperationalConfiguration.objects.filter(
                    program=application.program, status='LOCKED').first()
                if configuration:
                    configuration.clean()
                    if configuration.source != configuration_source(application.program):
                        raise ValidationError('The authorized program qualification rules need renewed review.')
                    from ewaf.four_pool import eligibility
                    eligibility(assessment, configuration.policy['eligibility'])
    case = review_eligibility(reference, user=user, data=data, address=address)
    if retained is not None:
        # The checklist update changes source context. Preserve the previous finding
        # and append the explicitly rechecked finding against that new context.
        from ewaf.evidence import source_context, digest
        from ewaf.evidence_services import record_assessment
        application.refresh_from_db()
        record_assessment(reference, user=user, criterion='PR', policy_id=policy.pk,
            expected_revision=assessment.revision, expected_context=digest(source_context(application)),
            state='VERIFIED', source_type=assessment.source_type, value=assessment.value,
            reason=data['notes'], confirmed=True, rubric_attested=True, rubric_findings=retained)
    return case
