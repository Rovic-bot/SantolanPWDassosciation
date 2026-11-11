"""Shared SMTP acceptance handling; never retry a possibly accepted message."""
import smtplib


class EmailNotAccepted(Exception):
    """The backend explicitly reported that it accepted no message."""


class EmailDeliveryUnconfirmed(Exception):
    """Submission started, but the backend did not confirm its outcome."""


def send_message(message):
    """Validate, connect, submit once and keep acceptance even if QUIT fails.

    Connection/authentication failures happen before submission and are safe to
    retry. A connection lost during DATA may already have delivered the email.
    Only sanitized exception types are retained by the workflow outboxes.
    """
    # Invalid headers/content must fail before anything is submitted to SMTP.
    message.message()
    connection = message.connection
    try:
        connection.open()
        try:
            accepted = message.send(fail_silently=False)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused,
                smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
            raise
        except Exception:
            raise EmailDeliveryUnconfirmed() from None
        if accepted != 1:
            raise EmailNotAccepted()
    finally:
        try:
            connection.close()
        except Exception:
            # Closing an already accepted submission cannot undo acceptance.
            pass


def latest_error(job):
    if not job or job.state not in ('failed', 'uncertain', 'sending'):
        return ''
    attempt = job.attempts.order_by('-number').first()
    return attempt.error_type if attempt else ''


def delivery_unconfirmed(job):
    return bool(job and (job.state in ('sending', 'uncertain')
                        or latest_error(job) == 'EmailDeliveryUnconfirmed'))


def delivery_help(job):
    """Private staff guidance, with no provider response or credential content."""
    if not job or job.state not in ('failed', 'uncertain', 'sending'):
        return ''
    error = latest_error(job)
    if job.state in ('sending', 'uncertain') or error == 'EmailDeliveryUnconfirmed':
        return ('Email acceptance is unconfirmed. Check the sender mailbox before retrying; '
                'another attempt could send a duplicate.')
    if error == 'EmailConnectionRequired':
        return ('The saved Association sender is not connected. Connect that Gmail account '
                'in Association email settings, then retry the saved email.')
    if error == 'SMTPAuthenticationError':
        return ('Gmail could not sign in. Reconnect the saved Association account with its '
                'Gmail app password in Association email settings, then retry.')
    if error in ('SMTPServerDisconnected', 'SMTPConnectError', 'TimeoutError',
                 'ConnectionRefusedError', 'ConnectionResetError', 'OSError', 'gaierror'):
        return ('The mail server connection failed. Check the internet connection and '
                'Association email settings, and check the sender mailbox before retrying.')
    if error in ('SSLError', 'SSLCertVerificationError', 'SMTPNotSupportedError'):
        return ('A secure mail connection could not be established. Check the mail server '
                'configuration and computer clock before retrying.')
    if error in ('SMTPRecipientsRefused', 'SMTPSenderRefused', 'SMTPDataError', 'EmailNotAccepted'):
        return ('The mail service did not accept this email. Review the saved sender and '
                'recipient before retrying.')
    return 'The email could not be sent. Check Association email settings before retrying.'
