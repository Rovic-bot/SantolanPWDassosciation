from django.conf import settings


# Some error and printable templates also serve staff routes. Choose their
# resident layout by the resolved endpoint, independently of who is signed in.
RESIDENT_ROUTES = frozenset({
    'core:home', 'core:about', 'core:announcements', 'core:events', 'core:programs',
    'core:result_detail', 'core:resources', 'core:resource_detail',
    'core:membership', 'core:contact', 'core:privacy', 'core:accessibility',
    'core:application_information', 'core:ewaf_information', 'core:faq',
    'announcements:detail', 'events:detail', 'events:observance_public_detail',
    'programs:list', 'programs:detail', 'programs:verify', 'programs:apply',
    'programs:submitted', 'programs:tracking', 'programs:tracking_progress', 'programs:tracking_finish',
    'membership:registration_apply', 'membership:registration_receipt', 'membership:registration_finish',
    'membership:pdao_apply', 'membership:pdao_prepare', 'membership:pdao_receipt', 'membership:pdao_finish',
    'members:update_start', 'members:update_code', 'members:update_information', 'members:update_finish',
    'assistance:referral_information', 'assistance:referral_verify', 'assistance:referral_apply',
    'assistance:referral_receipt', 'assistance:referral_finish',
    'assistance:referral_conversation_verify', 'assistance:referral_conversation',
    'assistance:referral_conversation_page',
})


def navigation(request):
    view_name = getattr(getattr(request, 'resolver_match', None), 'view_name', '')
    resources_section_active = view_name in {
        'core:resources', 'core:resource_detail', 'assistance:referral_information',
        'assistance:referral_verify', 'assistance:referral_apply', 'assistance:referral_receipt',
        'assistance:referral_conversation_verify', 'assistance:referral_conversation',
        'assistance:referral_conversation_page',
    }
    active_route = view_name
    app_name = getattr(getattr(request, 'resolver_match', None), 'app_name', '')
    if app_name in ('programs', 'events', 'announcements', 'membership'):
        active_route = 'core:' + app_name
    if view_name in ('members:update_start', 'members:update_code', 'members:update_information', 'members:update_finish'):
        active_route = 'core:membership'
    if view_name == 'core:result_detail':
        active_route = 'core:announcements'
    elif resources_section_active or view_name in (
            'core:contact', 'core:privacy', 'core:accessibility',
            'core:application_information', 'core:ewaf_information', 'core:faq'):
        active_route = 'core:resources'
    return {'resources_section_active': resources_section_active,
        'public_active_route': active_route,
        'portal_editor_preview': bool(getattr(request, '_portal_preview', False)),
        'portal_editor_page': getattr(request, '_portal_page', ''),
        'csrf_cookie_name': settings.CSRF_COOKIE_NAME,
        'public_redesign_enabled': view_name in RESIDENT_ROUTES,
        'resident_support_layout': 'public/resident_base.html' if view_name in RESIDENT_ROUTES else 'public/base.html',
        'ewaf_vault_enabled': getattr(settings, 'EWAF_VAULT_ENABLED', False),
        'ewaf_dataset_policy_enabled': getattr(settings, 'EWAF_DATASET_POLICY_ENABLED', False),
        'program_tracking_enabled': settings.PROGRAM_TRACKING_ENABLED,
        'program_tracking_qr_enabled': settings.PROGRAM_TRACKING_QR_ENABLED,
        'program_application_workflow_enabled': settings.PROGRAM_APPLICATION_WORKFLOW_ENABLED,
        'public_navigation': [
        ('core:home', 'Home'), ('core:about', 'About'),
        ('core:announcements', 'Announcements'), ('core:events', 'Events'),
        ('core:programs', 'Programs'),
        ('core:membership', 'Membership & PWD ID'),
        ('core:resources', 'Resources & Help'),
    ]}
