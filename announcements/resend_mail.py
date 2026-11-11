"""Small server-only Resend adapter; no provider error bodies or keys are logged."""
import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.views.decorators.debug import sensitive_variables
from .certificate_pdf import attachment_details


class ResendFailure(Exception):
    def __init__(self, code, *, uncertain=False):
        super().__init__(code)
        self.code, self.uncertain = code, uncertain


def setup_problem():
    if not settings.CERTIFICATE_RESEND_ENABLED:
        return 'setup'
    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
        return 'setup'
    try:
        validate_email(settings.RESEND_FROM_EMAIL)
    except ValidationError:
        return 'sender'
    domain = settings.RESEND_FROM_EMAIL.rsplit('@', 1)[-1].lower()
    if domain in ('resend.dev', 'gmail.com', 'googlemail.com', 'yahoo.com', 'outlook.com', 'hotmail.com'):
        return 'domain'
    return ''


@sensitive_variables()
def send_certificate(job):
    filename, _ = attachment_details(job.document)
    payload = {
        'from': f'Santolan PWD Association <{job.sender}>',
        'to': [job.recipient], 'subject': job.subject, 'text': job.body,
        'attachments': [{'filename': filename,
                         'content': base64.b64encode(bytes(job.document)).decode('ascii')}],
    }
    if job.reply_to:
        payload['reply_to'] = job.reply_to
    request = Request('https://api.resend.com/emails', method='POST',
        data=json.dumps(payload).encode('utf-8'), headers={
            'Authorization': f'Bearer {settings.RESEND_API_KEY}',
            'Content-Type': 'application/json', 'User-Agent': 'SantolanPWD/1.0',
            'Idempotency-Key': f'selection-certificate/{job.pk}',
        })
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read(8192))
    except HTTPError as error:
        # 5xx and conflicts may leave acceptance unknown. A retry uses the same
        # immutable payload/key within Resend's 24-hour idempotency window.
        codes = {401: 'api_key', 403: 'domain', 422: 'rejected', 429: 'rate_limit'}
        raise ResendFailure(codes.get(error.code, 'provider'),
                            uncertain=error.code not in (400, 401, 403, 404, 422, 429)) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ResendFailure('connection', uncertain=True) from None
    provider_id = result.get('id') if isinstance(result, dict) else None
    if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 100:
        raise ResendFailure('response', uncertain=True)
    return provider_id
