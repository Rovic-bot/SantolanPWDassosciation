"""Render public form/receipt states with fictional data, without submitting forms."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ewaf_twelve_demo import environment
os.environ.update(environment())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.current_development_settings')
import django
django.setup()

from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils import timezone

from assistance.referral_forms import TicketForm, VerificationForm
from membership.guidance import membership_guidance
from membership.registration_forms import OnlineRegistrationForm
from config.registration_workflow import association_policy
from programs.forms import ApplicationForm
from programs.models import Program
from programs.tracking_forms import ApplicationTrackingForm


def read_only(execute, sql, params, many, context):
    if not sql.lstrip().upper().startswith(('SELECT', 'SHOW', 'SET')):
        raise RuntimeError('This visual fixture renderer must not change database records.')
    return execute(sql, params, many, context)


def render_states():
    output = Path(os.environ.get('QA_FIXTURES', ROOT / '.local/public-dark-contrast-20261109/fixtures'))
    output.mkdir(parents=True, exist_ok=True)
    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    request.session = {}
    now = timezone.now()
    profile = {'full_name': 'Synthetic Applicant', 'email': 'synthetic@example.invalid',
               'profile_sections': [('Personal information', [('Name', 'Synthetic Applicant'),
                                      ('Address', 'Synthetic test address')])], 'acknowledgement': True}
    receipt = {'submitted': profile, 'reference': 'SYNTHETIC-0000000001', 'received_at': now,
               'form_version': 'Visual sample', 'receipt_requirements': [],
               'onsite_instructions': 'Bring your documents to the Association Help Desk.'}
    states = [
        ('association-receipt', 'membership/registration/receipt.html', receipt),
        ('pdao-receipt', 'membership/pdao/receipt.html', receipt),
        ('tracking-progress', 'programs/tracking/progress.html', {'progress': {
            'program_name': 'Synthetic assistance program', 'reference': 'SYNTHETIC-0000000001',
            'submitted_at': now, 'status_label': 'Under review', 'explanation': 'Your application is being reviewed.'}}),
        ('concern-receipt', 'assistance/referrals/receipt.html', {'ticket': {
            'short_reference': 'SYNTHETIC-001', 'subject': 'Synthetic request',
            'get_assistance_type_display': 'Medical assistance', 'email': profile['email']},
            'delivery': 'Acknowledgment queued', 'notice': 'Contact the Help Desk for follow-up.'}),
        ('concern-errors', 'assistance/referrals/apply.html', {'form': TicketForm({}, member=None),
            'notice': 'Requests are reviewed by the Association.'}),
        ('verification-errors', 'assistance/referrals/verify.html', {'form': VerificationForm({})}),
        ('tracking-errors', 'programs/tracking/verify.html', {'form': ApplicationTrackingForm({})}),
    ]
    policy = association_policy(settings.MEMBERSHIP_FILE_MAX_BYTES, settings.MEMBERSHIP_TOTAL_MAX_BYTES)
    states.append(('registration-errors', 'membership/registration/apply.html', {
        **membership_guidance(), 'form': OnlineRegistrationForm({}, policy=policy),
        'policy': policy, 'privacy_notice': policy['privacy_notice']}))
    program = Program.objects.public().first()
    if program:
        states.append(('program-receipt', 'programs/submitted.html', {'program': program,
            'application': {'short_reference': 'SYNTHETIC-001'}, 'information_change_reported': True,
            'tracking_url': '/programs/tracking/'}))
        form = ApplicationForm({}, program=program, require_calendar_photo=True)
        states.append(('program-errors', 'programs/apply.html', {'program': SimpleNamespace(
            pk=program.pk, name='Synthetic assistance program', registration_available=True,
            requirements='Please complete the required information.', photo_instructions='Provide your current photo.'),
            'form': form}))
    payload = {'program_name': 'Synthetic published result', 'description': 'A fictional result for visual inspection.',
               'program_date': 'November 9, 2026', 'slots': 2, 'eligible_count': 2,
               'eligibility_explanation': 'Requirements were reviewed.', 'selection_method': 'Authorized selection.',
               'ewaf_explanation': 'Private assessments remain protected.',
               'rows': [{'name': 'S*** A***', 'reference': '0001', 'status': 'Selected', 'ambiguous': True}]}
    states.append(('published-result', 'results/public_detail.html', {
        'result': {'pk': uuid.uuid4(), 'published_at': now, 'public_payload': payload}}))
    for name, template, context in states:
        html = render_to_string(template, {'program_tracking_enabled': True, **context}, request=request)
        (output / f'{name}.html').write_text(html, encoding='utf-8')
    print(f'Rendered {len(states)} fictional visual states to {output}')


if __name__ == '__main__':
    with connection.execute_wrapper(read_only):
        render_states()
