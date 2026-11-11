"""Provider selection for private certificate attachments."""
import smtplib

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.views.decorators.debug import sensitive_variables

from assistance.referral_connection import EmailConnectionRequired, transport_for
from assistance.referral_models import ReferralSettings
from core.email_delivery import EmailDeliveryUnconfirmed, EmailNotAccepted, send_message
from . import resend_mail
from .certificate_pdf import attachment_details

DeliveryFailure = resend_mail.ResendFailure


def selected_provider():
    return settings.CERTIFICATE_EMAIL_PROVIDER


def setup_problem(provider=None):
    provider = provider or selected_provider()
    if provider == 'resend':
        return resend_mail.setup_problem()
    if provider != 'gmail':
        return 'mail_provider'
    try:
        transport_for(ReferralSettings.objects.filter(pk=1).first())
    except EmailConnectionRequired:
        return 'gmail_setup'
    return ''


def sender_for(provider):
    if provider == 'resend':
        return settings.RESEND_FROM_EMAIL
    row = ReferralSettings.objects.filter(pk=1).first()
    return row.sender_email if provider == 'gmail' and row else ''


@sensitive_variables()
def send_certificate(job):
    if job.provider == 'resend':
        return resend_mail.send_certificate(job)
    if job.provider != 'gmail':
        raise DeliveryFailure('mail_provider')
    row = ReferralSettings.objects.filter(pk=1).first()
    if not row or row.sender_email.casefold() != job.sender.casefold():
        raise DeliveryFailure('sender_changed')
    try:
        backend, options = transport_for(row)
        connection = get_connection(backend=backend, **options)
    except (EmailConnectionRequired, smtplib.SMTPAuthenticationError):
        raise DeliveryFailure('gmail_setup') from None
    except (smtplib.SMTPException, OSError):
        raise DeliveryFailure('gmail_connection') from None
    try:
        message = EmailMessage(subject=job.subject, body=job.body,
            from_email=f'Santolan PWD Association <{job.sender}>', to=[job.recipient],
            reply_to=[job.reply_to or job.sender], connection=connection,
            headers={'Message-ID': f'<selection-certificate-{job.pk}@{job.sender.rsplit("@", 1)[-1]}>'})
        filename, content_type = attachment_details(job.document)
        message.attach(filename, bytes(job.document), content_type)
        send_message(message)
    except EmailDeliveryUnconfirmed:
        raise DeliveryFailure('gmail_uncertain', uncertain=True) from None
    except smtplib.SMTPAuthenticationError:
        raise DeliveryFailure('gmail_setup') from None
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError, EmailNotAccepted):
        raise DeliveryFailure('gmail_rejected') from None
    except (smtplib.SMTPException, OSError):
        raise DeliveryFailure('gmail_connection') from None
    # SMTP supplies no Resend-style provider ID; do not invent one.
    return ''
