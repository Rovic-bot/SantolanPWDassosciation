"""Read-only labels for the PDAO application workspace."""
from django.utils.dateparse import parse_date


def record_summary(data, status):
    parts = str(data.get('full_name', '')).split()
    initials = ''.join(part[0] for part in (parts[:1] + parts[-1:] if len(parts) > 1 else parts)).upper()
    try:
        birthdate = parse_date(data.get('birthdate', ''))
    except (TypeError, ValueError):
        birthdate = None
    descriptions = {
        'received': ('Check the saved PWD number in PRPWD, if provided. Mark ready to invite the applicant for onsite verification, or request corrected information.'
            if data.get('intake_channel', 'online') == 'online' else 'Verify the applicant’s details and requirements onsite. Save any corrections before marking the form ready.'),
        'needs_info': 'Information needs correction. Check email delivery below, then save corrected details and review again before forwarding.',
        'ready': 'Complete onsite verification, then record forwarding only after the signed form and requirements have been delivered to PDAO.',
        'forwarded': 'Forwarding to PDAO has been recorded. These details are now locked. PDAO makes the final PWD ID decision.',
    }
    return {
        'initials': initials or '—',
        'birthdate': birthdate,
        'channel': {'online': 'Online', 'walk_in': 'Walk-in', 'barangay': 'Barangay'}.get(data.get('intake_channel'), 'Not recorded'),
        'status_help': descriptions.get(status, ''),
    }
