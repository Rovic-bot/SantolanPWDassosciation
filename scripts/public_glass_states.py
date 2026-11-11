"""Render synthetic private UI states for local browser QA. No accounts, submissions or database access."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import resolve, reverse
from programs.tracking_forms import ApplicationTrackingForm

key = UUID('00000000-0000-4000-8000-000000000001')
date = datetime(2026, 10, 1, tzinfo=timezone.utc)
output = ROOT / '.local' / 'blue-glass-states'
output.mkdir(parents=True, exist_ok=True)
states = [
    ('membership', 'membership:registration_receipt', 'membership/registration/receipt.html', None,
     dict(reference=key, submitted={'profile_kind': 'association_pdf_v1'}, receipt_requirements=[{'label': 'Synthetic preparation item'}])),
    ('pdao', 'membership:pdao_receipt', 'membership/pdao/receipt.html', None,
     dict(reference=key, received_at=date, submitted={'application_type': 'Renewal'})),
    ('request', 'assistance:referral_receipt', 'assistance/referrals/receipt.html', None,
     dict(ticket={'short_reference': 'DEMO-1234', 'subject': 'Synthetic concern', 'email': 'sample@example.invalid'}, delivery='Pending')),
    ('submission', 'programs:submitted', 'programs/submitted.html', [key],
     dict(program={'pk': key, 'name': 'Synthetic program'}, application={'pk': key, 'short_reference': 'DEMO-1234'}, information_change_reported=True)),
    ('progress', 'programs:tracking_progress', 'programs/tracking/progress.html', None,
     dict(progress={'program_name': 'Synthetic program', 'reference': key, 'submitted_at': date, 'status_label': 'Submitted', 'explanation': 'Pending review.'})),
    ('invalid', 'programs:tracking', 'programs/tracking/verify.html', None, dict(form=ApplicationTrackingForm(data={}))),
    ('forbidden', 'assistance:referral_verify', '403.html', None, {}),
    ('missing', 'programs:tracking', '404.html', None, {}),
]


def no_database(*_):
    raise RuntimeError('Fixtures must never access application records.')


with connection.execute_wrapper(no_database):
    for label, route, template, args, context in states:
        request = RequestFactory().get(reverse(route, args=args))
        request.resolver_match = resolve(request.path)
        request.user = AnonymousUser()
        (output / f'{label}.html').write_text(render_to_string(template, context, request=request), encoding='utf-8')
print(f'Rendered {len(states)} synthetic states without database access.')
