"""Private presentation data for the existing staff conversation workspace."""
from django.template.loader import render_to_string
from core.email_delivery import delivery_help

from .referral_mail import delivery_label
from .referral_models import ReferralSettings, ReferralTicket


def wants_json(request):
    return 'application/json' in request.headers.get('Accept', '')


def ticket_payload(ticket, actor, request):
    actions = list(ticket.actions.filter(version__lte=ticket.version))
    emails = list(ticket.emails.prefetch_related('attempts'))
    for email in emails:
        email.delivery_label = delivery_label(email)
        email.delivery_help = delivery_help(email)
    settings = ReferralSettings.objects.filter(pk=1).first()
    return {
        'ticket': str(ticket.pk), 'version': ticket.version,
        'status': ticket.get_status_display(), 'status_code': ticket.status,
        'closed': ticket.status == ReferralTicket.Status.CLOSED,
        'can_review': actor.has_perm('assistance.review_referralticket'),
        'can_email': actor.has_perm('assistance.send_referral_email'),
        'sender_version': settings.version if settings else 0,
        'sender_email': settings.sender_email if settings else '',
        'messages': [{'id': item.pk,
            'sender': 'member' if item.action == 'member_replied' else 'staff',
            'message': item.member_message, 'recorded_at': item.recorded_at.isoformat()}
            for item in actions if item.member_message],
        'activity_html': render_to_string('assistance/referrals/activity.html',
            {'ticket': ticket, 'actions': actions}, request=request),
        'email_revision': '|'.join(f'{item.pk}:{item.state}:{item.attempt_count}' for item in emails),
        'email_html': render_to_string('assistance/referrals/email_history.html',
            {'emails': emails}, request=request),
    }


def reply_feedback(ticket, values, actor):
    if values['channel'] == 'online':
        return 'Reply sent to the online conversation.', False
    email = ticket.emails.filter(action__version=values['version'] + 1,
        action__actor=actor).first()
    if email and email.state == 'failed':
        return 'Your reply was saved. ' + delivery_help(email), True
    if email and email.state == 'sent':
        return delivery_label(email), False
    return 'Your reply is queued. Email history will update when its delivery status changes.', False
