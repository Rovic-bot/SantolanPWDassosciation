"""One permission-aware navigation projection for custom and native Admin."""
from django import template
from django.urls import reverse
from assistance.services import VIEW_PERMISSIONS
from announcements.results import RESULT_PERMISSIONS
from programs.workflow import PHOTO_VIEW
from ewaf.services import VIEW as EWAF_VIEW
from ewaf.evidence import VIEW as EVIDENCE_VIEW
from ewaf.configuration_services import VIEW as CONFIGURATION_VIEW
from ewaf.scoring_inputs import VIEW as SCORING_VIEW
from ewaf.operational_services import VIEW as OPERATIONAL_VIEW
from core.review_notifications import review_counts

register = template.Library()


@register.simple_tag(takes_context=True)
def operational_ewaf_access(context):
    user = context['request'].user
    return (user.is_authenticated and user.is_active and user.is_staff and
            user.has_perms(('accounts.access_dashboard', *OPERATIONAL_VIEW)))


@register.simple_tag(takes_context=True)
def workspace_navigation(context):
    request = context['request']
    user = request.user
    if not (user.is_authenticated and user.is_active and user.is_staff):
        return []
    match = request.resolver_match
    route = match.view_name if match else ''
    app = match.app_name if match else ''
    opts = context.get('opts')
    model = opts.label_lower if opts else ''
    workspace = user.has_perm('accounts.access_dashboard')
    groups = []
    counts = review_counts(request)

    def allowed(*permissions):
        return workspace and user.has_perms(permissions)

    def link(label, name, permitted, active=False, query='', review_kind=''):
        if not permitted:
            return None
        return {'label': label, 'url': reverse(name) + query, 'active': active,
                'review_kind': review_kind, 'review_count': counts.get(review_kind, 0)}

    def group(key, label, index, links, notice='', current=False):
        links = [item for item in links if item is not None]
        if links or notice:
            groups.append({'key': key, 'label': label, 'index': index, 'links': links,
                           'review_kind': next((item['review_kind'] for item in links if item['review_kind']), ''),
                           'review_count': sum(item['review_count'] for item in links),
                           'referral_badge': next((item['referral_badge'] for item in links if item.get('referral_badge')), None),
                           'notice': notice, 'active': current or any(item['active'] for item in links)})

    group('dashboard', 'Dashboard', '01', [
        link('Overview', 'core:dashboard', workspace, route == 'core:dashboard'),
    ])
    group('members', 'Members', '02', [
        link('Member Directory', 'member_directory', allowed('members.view_member'),
             app == 'members' or route == 'member_directory'),
        link('Onsite registration', 'membership:encode', allowed('membership.view_membershipapplication',
             'membership.encode_membershipapplication'), route == 'membership:encode'),
        link('Membership reviews', 'membership:review_home',
             allowed('membership.view_membershipapplication') or allowed('membership.view_pdaoregistration'),
             app == 'membership' and route not in ('membership:encode', 'membership:pdao_onsite'), review_kind='membership'),
        link('Onsite PDAO registration', 'membership:pdao_onsite',
             allowed('membership.view_pdaoregistration', 'membership.add_pdaoregistration'),
             route == 'membership:pdao_onsite'),
    ])
    application_routes = ('programs:applications', 'programs:application_detail', 'programs:document',
                          'programs:document_revision', 'programs:correction')
    photo_routes = ('programs:photo_queue', 'programs:photo_review', 'programs:photo')
    group('programs', 'Programs & Events', '03', [
        link('Program Management', 'program_portfolio', allowed('programs.view_program'),
             route in ('program_portfolio', 'program_builder', 'program_detail') or (app == 'programs' and route not in application_routes + photo_routes),
             review_kind='programs' if allowed('programs.view_programapplication') else ''),
        link('Events Calendar', 'event_workspace',
             allowed('events.view_annualobservance') or allowed('events.view_event'), app == 'events' or route == 'event_workspace'),
    ])
    release_access = allowed(*VIEW_PERMISSIONS, 'assistance.view_assistancerelease')
    assistance_review = app == 'assistance' and not route.startswith('assistance:referral_') and route not in (
        'assistance:statuses', 'assistance:status_edit', 'assistance:release', 'assistance:void',
        'assistance:release_programs', 'assistance:program_releases',
    )
    referral_link = link('Community Assistance Desk Inbox', 'assistance:referral_inbox',
        allowed('assistance.view_referralticket'), route.startswith('assistance:referral_'))
    if referral_link:
        from assistance.referral_services import new_concern_count
        referral_link['referral_badge'] = {
            'count': new_concern_count(), 'url': reverse('assistance:referral_new_count'),
        }
    group('applications', 'Applications & Verification', '04', [
        referral_link,
        link('Program Applications & Eligibility', 'application_workspace', allowed('programs.view_program',
             'programs.view_programapplication'), route in ('core:application_programs', 'application_workspace') or route in application_routes + photo_routes
             or route.startswith('ewaf:evidence_') or assistance_review),
    ])
    ewaf_notice = ''
    if workspace and (user.is_superuser or user.has_perm('ewaf.add_configuration') or user.has_perms(EWAF_VIEW)):
        ewaf_notice = 'Operational EWAF requires the EWAF view permission and its private evidence permissions. An authorized account administrator can assign them in Roles & permissions.'
    if allowed(*OPERATIONAL_VIEW):
        ewaf_notice = ''
    group('selection', 'EWAF & Selection', '05', [
        link('EWAF', 'ewaf_selection', allowed(*OPERATIONAL_VIEW),
             route.startswith('ewaf:operational_') or route in ('ewaf_selection', 'ewaf:vault', 'ewaf:registered_review')),
        link('Assistance releases', 'assistance:release_programs', release_access,
             route in ('assistance:release_programs', 'assistance:program_releases', 'assistance:release', 'assistance:void')),
    ], ewaf_notice, app == 'ewaf' and not route.startswith('ewaf:evidence_'))
    group('content', 'Announcements & CMS', '06', [
        link('Announcements', 'announcements:manage_list', allowed('announcements.view_announcement'),
             app == 'announcements'),
        link('Content Management', 'core:content_list', allowed('core.view_publiccontent'),
             route in ('core:content_list', 'core:content_edit')),
    ])
    group('reports', 'Reports & Exports', '07', [
        link('Members', 'reports:members', allowed('members.view_member'), route == 'reports:members'),
        link('Applications', 'reports:applications', allowed('programs.view_program', 'programs.view_programapplication'),
             route == 'reports:applications'),
        link('Programs', 'reports:programs', allowed('programs.view_program'), route == 'reports:programs'),
        link('Assistance', 'reports:assistance', allowed(*VIEW_PERMISSIONS, 'assistance.view_assistancerelease'),
             route == 'reports:assistance'),
    ])
    native_links = [
        ('Administrator accounts', 'admin:auth_user_changelist', user.is_superuser, 'auth.user'),
        ('Roles & permissions', 'admin:auth_group_changelist', user.is_superuser, 'auth.group'),
        ('Sign-in activity', 'admin:audit_securityevent_changelist', user.has_perm('audit.view_securityevent'), 'audit.securityevent'),
        ('Administration changes', 'admin:admin_logentry_changelist', user.has_perm('admin.view_logentry'), 'admin.logentry'),
    ]
    group('administration', 'Administration', '08', [
        link(label, name, permitted, model in target if isinstance(target, tuple) else model == target)
        for label, name, permitted, target in native_links
    ], current=app == 'admin' or route in ('assistance:statuses', 'assistance:status_edit'))
    return groups
