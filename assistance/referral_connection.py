"""Sender-bound Gmail credentials and direct-mail connection selection.

The app password is encrypted at rest using a domain-separated key derived
from the server's generated SECRET_KEY. Keep that secret outside DB backups.
"""
import base64
import json
import smtplib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.views.decorators.debug import sensitive_variables

SMTP_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
TEST_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


class EmailConnectionRequired(Exception):
    pass


def cipher():
    keys = [settings.SECRET_KEY, *getattr(settings, 'SECRET_KEY_FALLBACKS', [])]
    return MultiFernet([Fernet(base64.urlsafe_b64encode(HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=b'santolan.referral.gmail.v1',
    ).derive(key.encode()))) for key in keys])


@sensitive_variables()
def encrypt_password(sender, password):
    payload = json.dumps({'sender': sender.casefold(), 'password': password}).encode()
    return cipher().encrypt(payload).decode()


@sensitive_variables()
def decrypt_password(sender, encrypted):
    try:
        data = json.loads(cipher().decrypt(encrypted.encode()))
        if data['sender'] == sender.casefold() and data['password']:
            return data['password']
    except (InvalidToken, ValueError, KeyError, TypeError):
        pass
    raise EmailConnectionRequired('Reconnect the Association Gmail account in email settings.')


@sensitive_variables()
def gmail_options(sender, password):
    return dict(host='smtp.gmail.com', port=587, username=sender, password=password,
                use_tls=True, use_ssl=False, timeout=settings.EMAIL_TIMEOUT)


@sensitive_variables()
def check_gmail_login(sender, password):
    """Authenticate over TLS only; saving settings never sends a test message."""
    connection = None
    try:
        connection = get_connection(backend=SMTP_BACKEND, **gmail_options(sender, password))
        connection.open()
    except smtplib.SMTPAuthenticationError:
        raise ValidationError('Google could not sign in. Check the Gmail address and its app password.') from None
    except (smtplib.SMTPException, OSError):
        raise ValidationError('Could not connect to Gmail. Check your connection and try again; the previous settings were kept.') from None
    finally:
        if connection:
            try:
                connection.close()
            except (smtplib.SMTPException, OSError):
                pass


@sensitive_variables()
def transport_for(row):
    if row and row.gmail_password_encrypted:
        password = decrypt_password(row.sender_email, row.gmail_password_encrypted)
        return SMTP_BACKEND, gmail_options(row.sender_email, password)
    # Only the explicitly selected memory backend captures test mail. File and
    # console outboxes must never masquerade as the user's direct Send action.
    if row and settings.EMAIL_BACKEND == TEST_BACKEND:
        return TEST_BACKEND, {}
    if (row and settings.EMAIL_BACKEND == SMTP_BACKEND and settings.EMAIL_HOST_PASSWORD
            and settings.EMAIL_HOST_USER.casefold() == row.sender_email.casefold()):
        return SMTP_BACKEND, {}
    raise EmailConnectionRequired('Connect this Gmail account in Association email settings before sending.')


def connection_status(row):
    try:
        backend, _ = transport_for(row)
    except EmailConnectionRequired:
        return {'ready': False, 'label': 'Gmail is not connected.'}
    return {'ready': True, 'label': 'Test mail capture is active.' if backend == TEST_BACKEND
            else 'Email connection configured.'}


def require_connection(row):
    try:
        transport_for(row)
    except EmailConnectionRequired as error:
        raise ValidationError(str(error)) from None
