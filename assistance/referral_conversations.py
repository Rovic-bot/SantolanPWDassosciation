"""Private, ticket-scoped conversations without member accounts or new tickets."""
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, transaction
from django.db.models import Q
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.debug import sensitive_variables

from . import referral_services as service
from .referral_forms import ConversationReplyForm
from .referral_models import ReferralTicket, ReferralWindow, referral_write

ACCESS_SALT = 'referral.conversation.v1'
ACCESS_ERROR = 'Unable to open this conversation. Check the complete conversation reference, or contact the Association Help Desk.'


class ConversationClosed(PermissionDenied):
    """A matched conversation has ended and can no longer grant public access."""


def require_open(ticket):
    if ticket.status == ReferralTicket.Status.CLOSED:
        raise ConversationClosed('This conversation has finished. Please submit a new concern.')


def issue_access(ticket, binding):
    if not service.enabled() or not binding or not service.valid_member(ticket.member):
        raise PermissionDenied
    require_open(ticket)
    return signing.dumps({'ticket': str(ticket.pk), 'member': ticket.member_id,
        'binding': binding, 'source': service.digest(service.source_snapshot(ticket.member))},
        salt=ACCESS_SALT)


@sensitive_variables()
def verify_conversation(*, binding, conversation_reference):
    if not service.enabled():
        raise PermissionDenied
    # The existing random full reference is the private conversation key.
    # Sequential REF- aliases are inbox search keys, never access credentials.
    reference = conversation_reference.strip()
    try:
        if not reference.upper().startswith('ASR-'):
            raise ValueError
        identifier = UUID(reference[4:])
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(ACCESS_ERROR) from None
    ticket = ReferralTicket.objects.select_related('member__application').filter(pk=identifier).first()
    if not (ticket and constant_time_compare(ticket.reference.upper(), reference.upper())
            and service.valid_member(ticket.member)):
        raise ValidationError(ACCESS_ERROR)
    return issue_access(ticket, binding)


@sensitive_variables()
def get_conversation(token, binding, *, lock=False):
    if not service.enabled():
        raise PermissionDenied
    try:
        payload = signing.loads(token or '', salt=ACCESS_SALT, max_age=settings.REFERRAL_GRANT_SECONDS)
        identifier = UUID(payload['ticket'])
        if not constant_time_compare(payload['binding'], binding):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, KeyError, AttributeError):
        raise PermissionDenied from None
    records = ReferralTicket.objects.select_for_update() if lock else ReferralTicket.objects
    ticket = records.select_related('member__application').filter(pk=identifier).first()
    if not (ticket and ticket.member_id == payload['member'] and service.valid_member(ticket.member)
            and constant_time_compare(payload['source'], service.digest(service.source_snapshot(ticket.member)))):
        raise PermissionDenied
    require_open(ticket)
    return ticket


def visible_messages(ticket):
    # Never include internal notes, evidence access, private contact details or mail metadata.
    return ticket.actions.filter(~Q(member_message=''), version__lte=ticket.version).filter(
        Q(action='member_replied', channel='online', actor__isnull=True)
        | Q(action='reviewed', channel__in=['email', 'online', 'onsite'], actor__isnull=False))


def message_payload(item):
    return {'id': item.pk, 'sender': 'member' if item.action == 'member_replied' else 'staff',
        'message': item.member_message, 'recorded_at': item.recorded_at.isoformat()}


def conversation_payload(ticket):
    return {'ticket': str(ticket.pk), 'version': ticket.version,
        'status': ticket.get_status_display(), 'closed': False,
        'messages': [message_payload(item) for item in visible_messages(ticket)]}


def reserve_reply(ticket):
    key = salted_hmac('referral.reply.member', str(ticket.member_id), algorithm='sha256').hexdigest()
    try:
        return service.reserve_windows({key: settings.REFERRAL_REPLY_LIMIT},
            settings.REFERRAL_WINDOW_SECONDS, ReferralWindow)
    except (OperationalError, ReferralWindow.DoesNotExist):
        return False


@transaction.atomic
def reply(token, binding, *, data):
    form = ConversationReplyForm(data)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    with referral_write():
        ticket = get_conversation(token, binding, lock=True)
        values = form.cleaned_data
        if ticket.version != values['version']:
            # A repeat of the same accepted POST must not duplicate a message.
            previous = ticket.actions.filter(action='member_replied', channel='online', actor__isnull=True,
                version=values['version'] + 1).first()
            if previous and previous.member_message == values['message']:
                return ticket
            raise ValidationError('This conversation has new activity. Read the latest messages below, then send your reply again.')
        if not reserve_reply(ticket):
            raise ValidationError('Please wait before sending another message. Your draft is kept below.')
        before = ticket.status
        if ticket.status == ReferralTicket.Status.INFORMATION:
            ticket.status = ReferralTicket.Status.REVIEW
        ticket.version += 1
        ticket.save(update_fields=['status', 'version'])
        service.record_action(ticket, action='member_replied', channel='online', before=before,
            notes='Member sent a follow-up through the Community Assistance Desk.', message=values['message'])
        return ticket
