"""Authenticated Gmail HTTPS relay for hosts that block outbound SMTP.

Credentials stay server-side. Each submission is attempted once; an interrupted
response is deliberately left unconfirmed by the existing delivery service.
"""
import base64
import json
import re
import smtplib
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.views.decorators.debug import sensitive_variables


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class EmailBackend(BaseEmailBackend):
    @sensitive_variables()
    def __init__(self, username=None, password=None, timeout=None, **kwargs):
        super().__init__(**kwargs)
        self.username = username or settings.EMAIL_HOST_USER
        self.password = password or settings.EMAIL_HOST_PASSWORD
        self.timeout = max(timeout or settings.EMAIL_TIMEOUT, 40)
        self.url = settings.EMAIL_HTTPS_RELAY_URL
        self.token = settings.EMAIL_HTTPS_RELAY_TOKEN
        if (not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co/functions/v1/deployment-gateway', self.url)
                or len(self.token) < 48):
            raise ImproperlyConfigured('A private Supabase email relay must be configured.')
        self.opened = False

    @sensitive_variables()
    def _request(self, action, **payload):
        request = Request(self.url, data=json.dumps({
            'action': action, 'username': self.username, 'password': self.password, **payload,
        }).encode(), headers={'Authorization': 'Bearer ' + self.token,
                             'Content-Type': 'application/json'})
        try:
            try:
                response = build_opener(NoRedirect()).open(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                if response.status not in (200, 400, 401, 422, 502):
                    raise OSError('Email relay unavailable.')
                result = json.loads(response.read(4097))
        except (URLError, ValueError, OSError):
            raise OSError('Email relay did not confirm the request.') from None
        error = result.get('error')
        if error == 'authentication':
            raise smtplib.SMTPAuthenticationError(535, b'Gmail authentication failed.')
        if error == 'rejected':
            raise smtplib.SMTPDataError(550, b'Gmail did not accept the message.')
        if result.get('ok') is not True:
            raise OSError('Email relay did not confirm the request.')
        return result

    def open(self):
        if self.opened:
            return False
        self._request('verify')
        self.opened = True
        return True

    def close(self):
        self.opened = False

    @sensitive_variables()
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            if parseaddr(message.from_email)[1].casefold() != self.username.casefold():
                raise smtplib.SMTPSenderRefused(550, b'Sender must match the connected Gmail account.', '')
            raw = message.message().as_bytes(linesep='\r\n')
            if len(raw) > 12 * 1024 * 1024:
                raise smtplib.SMTPDataError(552, b'Message exceeds relay limit.')
            self.open()
            self._request('send', sender=self.username, recipients=message.recipients(),
                          raw=base64.b64encode(raw).decode('ascii'))
            sent += 1
        return sent
