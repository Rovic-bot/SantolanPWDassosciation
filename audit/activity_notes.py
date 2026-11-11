"""Plain descriptions for the audit reader; original audit records stay untouched.

Only the recorded action and allowlisted changed-field names inform the summary.
Do not infer past outcomes from a member, application, or program's current state.
"""
import json
import re


ACTION_NOTES = {
    'Program changed': 'Changed the program details.',
    'Program EWAF setting changed': 'Made EWAF required for this program. Previous decisions, results and assistance records were kept.',
    'Program requirements changed': 'Changed the requirements for this program.',
    'Program policy approved': 'Approved the program policy.',
    'External program approval recorded': 'Recorded the external approval for this program.',
    'Program approval linked': 'Linked the recorded approval to this program.',
    'Application recorded': 'Recorded a program application.',
    'Member approved': "Approved this person's Association membership.",
    'Membership rejected': 'Rejected the membership application.',
    'Membership verification confirmed': 'Recorded a successful membership verification.',
    'Membership verification not confirmed': 'Recorded that membership verification was unsuccessful.',
    'Member details changed': 'Changed the member details.',
    'Member status changed': 'Changed the member status.',
    'Member marked eligible': 'Marked this member as eligible for the program.',
    'Member marked eligible and automatically selected': 'Confirmed this member is eligible. The system automatically selected them because this program has no beneficiary limit.',
    'Member marked ineligible': 'Marked this member as ineligible for the program.',
    'Eligibility reviewed': 'Reviewed the member\'s eligibility for this program.',
    'More information requested': 'Requested more information before continuing the review.',
    'Assistance approved / member selected': 'Approved this member for assistance.',
    'Member selected': 'Selected this member for the program.',
    'Member not selected': 'Recorded that this member was not selected for the program.',
    'Member unselected': 'Removed this member from the program selection.',
    'Selection deferred': 'Deferred the selection decision for this member.',
    'Selection returned for review': 'Returned the selection decision for further review.',
    'Selection decision recorded': 'Recorded a selection decision for this member.',
    'Assistance released': 'Recorded the assistance given to this member.',
    'Assistance release voided': 'Voided the recorded assistance release.',
    'Application review required': 'Marked the application for another review.',
    'Results prepared': 'Prepared the program results for review.',
    'Results published': 'Published the program results for the public to view.',
    'Announcement changed': 'Changed the announcement details.',
    'Event changed': 'Changed the event details.',
    'Attendance recorded': 'Recorded attendance at this event.',
    'Attendance corrected': 'Corrected an attendance record for this event.',
    'PDAO application marked ready': 'Marked the PDAO application as ready for forwarding.',
    'PDAO forwarding recorded': 'Recorded that the application was forwarded to PDAO.',
    'PDAO form opened for printing': 'Opened the PDAO application form for printing.',
    'PDAO information requested': 'Requested more information for the PDAO application.',
    'PWD ID claim notice requested': 'Requested an email notifying the applicant about claiming their PWD ID.',
    'EWAF scores calculated': 'Calculated the program applicants\' EWAF scores.',
    'EWAF weights saved': 'Saved a version of the EWAF scoring weights.',
    'EWAF scoring policy saved': 'Saved a version of the EWAF scoring policy.',
    'EWAF configuration saved': 'Saved the EWAF settings for this program.',
    'EWAF inputs reviewed': 'Reviewed the information used to calculate EWAF scores.',
    'EWAF evidence assessed': 'Assessed the supporting information for an EWAF review.',
    'EWAF evidence policy saved': 'Saved the rules for reviewing EWAF supporting information.',
    'EWAF preview exported': 'Exported an EWAF calculation preview.',
    'EWAF record saved': 'Saved an EWAF record.',
    'Report viewed or exported': 'Viewed or exported a report.',
    'Office verification email requested': 'Requested an email asking the member to visit the office for verification.',
    'Membership reminder requested': 'Requested a membership reminder email.',
    'Onsite review requested': 'Requested an onsite membership review.',
    'Member information verified onsite': 'Verified the member information during an office visit.',
    'Membership details corrected': 'Corrected the membership application details.',
    'Member information confirmed': 'Confirmed the reviewed member information.',
    'Email settings changed': 'Changed the Association email settings.',
}

# These names describe recorded changes without exposing values, private
# snapshots, file paths, hashes, or internal identifiers.
CHANGED_FIELDS = {
    'program': {'name': 'name', 'description': 'description', 'benefits': 'benefits',
                'registration_opens_at': 'application opening date',
                'registration_closes_at': 'application closing date',
                'starts_at': 'start date', 'ends_at': 'end date', 'location': 'location',
                'slots': 'available places', 'image': 'picture', 'image_alt': 'picture description'},
    'event': {'title': 'title', 'description': 'description', 'location': 'location',
              'starts_at': 'start date and time', 'ends_at': 'end date and time',
              'image': 'picture', 'image_alt': 'picture description'},
    'member': {'full_name': 'name', 'birthdate': 'birth date', 'address': 'address',
               'contact_number': 'contact number', 'email': 'email address',
               'status': 'status', 'disability_type': 'disability classification'},
}

GENERATED_NOTES = (
    'Private G12 evidence record retained;',
    'Private G14 preparatory record;',
    'Private G15 diagnostic artifact;',
    'Private EWAF development artifact;',
    'revised_preview_export;',
    'Private program document downloaded:',
    'Saved for review as a private draft. Updated:',
    'Status changed from ',
    'Result revision ',
    'Authorized publication of reviewed privacy-masked result revision ',
)


def action_description(label):
    if label in ACTION_NOTES:
        return ACTION_NOTES[label]
    if label.endswith('activity recorded') or label == 'Activity recorded':
        return 'Recorded an administrative action for this record.'
    # Most labels share the same simple subject + past-tense verb structure.
    for verb in ('created', 'added', 'changed', 'updated', 'corrected', 'saved', 'approved',
                 'rejected', 'published', 'unpublished', 'archived', 'cancelled', 'deleted',
                 'downloaded', 'viewed', 'verified', 'reviewed', 'recorded', 'started',
                 'received', 'prepared', 'requested', 'opened', 'closed', 'reopened'):
        ending = ' ' + verb
        if label.endswith(ending):
            subject = label[:-len(ending)]
            subject = subject[0].lower() + subject[1:] if not subject.split()[0].isupper() else subject
            if verb == 'unpublished':
                return f'Removed the {subject} from public view.'
            return f'{verb.capitalize()} the {subject}.'
    if label.endswith(' retried'):
        subject = label[:-len(' retried')]
        subject = subject[0].lower() + subject[1:] if not subject.split()[0].isupper() else subject
        return f'Requested another attempt at {subject}.'
    return label.rstrip('.') + '.'


def administrator_note(raw):
    """Retain prose notes, but do not present machine payloads as explanations."""
    raw = str(raw or '').strip()
    if not raw or raw.startswith(GENERATED_NOTES):
        return ''
    if re.fullmatch(r'(?:sha256[:=]\s*)?[a-f0-9]{64}', raw, re.I):
        return ''
    if raw.startswith(('{', '[')):
        try:
            if isinstance(json.loads(raw), (dict, list)):
                return ''
        except ValueError:
            pass
    if re.search(r'(?:^|;\s*)[\w_]+\s*=', raw) or re.match(r'^Report \w+;', raw):
        return ''
    return raw


def readable_notes(item, specification, activity):
    label = activity['activity_label']
    note = action_description(label)
    if label in ('Program changed', 'Event changed', 'Member details changed', 'Member status changed'):
        changes = getattr(item, 'changes', {})
        fields = CHANGED_FIELDS.get(specification.key, {})
        changed = [name for key, name in fields.items() if isinstance(changes, dict) and key in changes]
        if changed:
            names = ', '.join(changed[:-1]) + ' and ' + changed[-1] if len(changed) > 1 else changed[0]
            note += f' Updated the {names}.'
    raw = item.get_change_message() if specification.key == 'administration' else getattr(item, specification.note, '')
    if label == 'Report viewed or exported':
        report = re.match(r'^Report (view|csv|pdf); rows=(\d+);', str(raw))
        if report:
            format, count = report.groups()
            action = 'Viewed' if format == 'view' else f'Exported a {format.upper()} copy of'
            note = f'{action} the report containing {int(count):,} records.'
    # Old preparatory records must never read as active approvals or processing.
    if str(raw).startswith(('Private G14 preparatory record;', 'Private EWAF development artifact;',
                            'Private G15 diagnostic artifact;')):
        note = 'Saved a historical EWAF preparation record. It did not authorize program processing.'
    return {'note': note, 'additional_note': administrator_note(raw)}
