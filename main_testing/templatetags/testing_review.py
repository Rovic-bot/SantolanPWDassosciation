"""Separate disability matching from a program's additional evidence requirements."""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def review_guidance(context):
    application = context['application']
    user = context['request'].user
    guidance = {'relevance': 'Restricted', 'requirements_current': False}
    if user.has_perm('members.view_member'):
        from programs.services import disability_matches
        restricted = application.program.eligible_disability_types.exists()
        guidance['relevance'] = ('Matches' if disability_matches(application.program, application.member)
                                 else 'Does not match') if restricted else 'No disability-type restriction'
    if context.get('qualification_form'):
        from ewaf.evidence import source_context
        source = source_context(application)
        case = source['case']
        guidance['requirements_current'] = bool(case and case['log_matches']
            and case['member_version'] == source['member_version']
            and case['program_version'] == source['program_version']
            and any(row['key'] == 'documents' and row['status'] == 'Verified'
                    for row in context['eligibility_checks']))
    return guidance


@register.filter
def review_label(value):
    return {'Disability Qualification': 'Program relevance — disability match',
            'Disability qualification': 'Program relevance — disability match',
            'Program Fit / Consent': 'Additional program requirements',
            'Program fit and required consent': 'Additional program requirements',
            'Program fit': 'Overall requirement finding'}.get(value, value)


@register.filter
def review_error(value):
    text = str(value)
    if 'PR_REQUIREMENTS_STALE' in text:
        return ('The saved program requirement review is missing or out of date. '
                'Review the checklist under Submitted Documents, enter a reason, '
                'and click Save requirement review before continuing.')
    return text.replace('program qualification and functional need below', 'additional program requirements below')
