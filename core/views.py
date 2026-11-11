from accounts.decorators import dashboard_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from announcements.models import Announcement
from programs.models import Program
from django.utils import timezone


# Stable Home anchors also preserve existing bookmarks and in-application links.
HOME_INFORMATION = (
    ('application-information', 'Application guidance'),
    ('contact', 'Contact / Help Desk'),
    ('faq', 'Frequently asked questions'),
    ('ewaf', 'How EWAF works'),
    ('privacy', 'Privacy information'),
)
HOME_CONTENT_KEYS = {key for key, _ in HOME_INFORMATION} | {'accessibility'}


@never_cache
@require_safe
def home(request):
    from announcements.notices import public_notice
    from .content import published_content
    from events.models import Event
    from events.services import public_observance_calendar
    from members.models import Member
    now = timezone.now()
    published_events = Event.objects.public().filter(status=Event.Status.PUBLISHED)
    scheduled_events = published_events.filter(ends_at__gt=now).order_by('starts_at', 'pk')
    current_event = scheduled_events.filter(starts_at__lte=now).order_by('-starts_at', 'pk').first()
    current_event_initials = ''.join(word[0] for word in current_event.title.split()[:2]).upper() if current_event else ''
    information = {key: published_content(key) for key in HOME_CONTENT_KEYS}
    guidance_cards = [
        {'anchor': 'contact', 'title': 'Contact / Help Desk',
         'excerpt': 'A helping hand with applications, services and your next steps.',
         'action': 'Go to Community Assistance', 'href': reverse('core:contact')},
        {'anchor': 'faq', 'title': 'Frequently asked questions',
         'excerpt': 'Quick answers about membership, requirements and program applications.',
         'action': 'Read FAQs', 'href': reverse('core:resources') + '#faq'},
        {'anchor': 'ewaf', 'title': 'How EWAF works',
         'excerpt': 'Understand how eligible applications are assessed and ranked, and how administrators select beneficiaries within the available slots.',
         'action': 'Learn about EWAF', 'href': '#ewaf-details'},
        {'anchor': 'member-update', 'title': 'Update member information',
         'excerpt': 'Review your saved member details and request an update.',
         'action': 'Update my information', 'href': reverse('members:update_start'),
         'content': {'body': 'Verify your identity through your saved email, edit your information, and submit it for staff review. Your PWD number stays unchanged. Visit the barangay office when invited for an interview or screening.', 'version': 0}},
        {'anchor': 'privacy', 'title': 'System information',
         'excerpt': 'Know how your information is used, protected and reviewed.',
         'action': 'View privacy notice', 'href': '#privacy-details'},
        {'anchor': 'accessibility', 'title': 'Reading help',
         'excerpt': 'Make the page easier to read, in a way that works for you.',
         'action': 'Accessibility tools'},
    ]
    for card in guidance_cards:
        card['content'] = card.get('content') or information[card['anchor']]
    return render(request, 'public/home.html', {
        'home_content': published_content('home'),
        'home_information': [
            {'anchor': key, 'label': label, 'content': information[key]}
            for key, label in HOME_INFORMATION
        ],
        'accessibility_content': information['accessibility'],
        'guidance_cards': guidance_cards,
        'home_events': scheduled_events[:2],
        'current_event': current_event,
        'current_event_initials': current_event_initials,
        'public_member_count': Member.objects.filter(is_active=True, archived_at__isnull=True).count(),
        'public_event_count': published_events.count(),
        'public_scheduled_event_count': scheduled_events.count(),
        'announcements': [public_notice(item) for item in Announcement.objects.published()
                          .select_related('linked_program', 'result_revision').order_by('-published_at', '-pk')[:3]],
        'public_program_count': Program.objects.public().count(),
        'has_open_programs': Program.objects.accepting_applications().exists(),
        'home_observances': [item for month in public_observance_calendar() for item in month['observances']][:3]})


@never_cache
@dashboard_required
@require_safe
def dashboard(request):
    from analytics.forms import ActivityRangeForm
    from analytics.services import overview
    now = timezone.now()
    form = ActivityRangeForm(request.GET or {'period': 'six_months'},
                             today=timezone.localdate(now, timezone=timezone.get_default_timezone()), user=request.user)
    valid = form.is_valid()
    data = overview(request.user, form.cleaned_data, now=now) if valid else None
    return render(request, 'admin_portal/dashboard.html', {'form': form, 'overview': data,
                  'filtered': bool(request.GET)}, status=200 if valid else 400)


@require_safe
def public_page(request, page):
    if page == 'contact':
        return redirect(f'{reverse("core:resources")}#referral-support')
    if page in HOME_CONTENT_KEYS:
        return redirect(f'{reverse("core:home")}#{page}')
    from .content import published_content
    content = published_content(page)
    if page == 'about':
        from .about import about_blocks
        return render(request, 'public/about.html', {**content, 'blocks': about_blocks(content.get('body', ''))})
    return render(request, 'public/page.html', {**content, 'eyebrow': 'PUBLIC INFORMATION PORTAL', 'heading': 'Association information'})
