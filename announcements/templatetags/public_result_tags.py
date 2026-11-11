"""Presentation of already-authorized public result snapshots, with no ORM reads."""
from django import template

register = template.Library()


@register.inclusion_tag('announcements/public_result_details.html')
def public_result_details(results, published_at=None, source_office='', show_heading=False, schedule=None):
    # Never join private applications to fill a gap in an older public revision.
    # Retain the exact names/references allowed by that revision's publication.
    selected = results.get('rows', [])
    selected_keys = {(row['name'], row['reference']) for row in selected}
    applicants = []
    for row in results.get('applicants', []):
        is_selected = (row['name'], row['reference']) in selected_keys
        applicants.append({**row, 'selected': is_selected,
            'display_status': 'Selected' if is_selected else row.get('status', 'Applied')})
    recipients = [{**row, 'received': row.get('claim_received', row.get('status') == 'Received')}
                  for row in selected]
    return {
        'results': results, 'published_at': published_at,
        'schedule': schedule,
        'source_office': source_office or 'Barangay Santolan PWD Association',
        'show_heading': show_heading, 'applicants': applicants, 'recipients': recipients,
        'applicants_available': 'applicants' in results and results.get('applicants_ready', True),
        'receipts_only': results.get('kind') == 'assistance_recipients',
    }
