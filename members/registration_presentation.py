"""Read-only presentation of approved member and registration information."""


def overview_details(member):
    """Use the current approved profile, never a pending update or old intake.

    Association PDF intake retains gender/civil-status labels in its JSON
    profile, while older records use coded model columns. Family and household
    counts are distinct from dependents and must not be substituted for them.
    """
    profile = member.registration_profile
    profile = profile if isinstance(profile, dict) else {}
    association = profile.get('profile_kind') == 'association_pdf_v1'
    return {
        'sex': member.get_sex_display() or (profile.get('gender') if association else ''),
        'civil_status': member.get_civil_status_display() or (profile.get('civil_status') if association else ''),
        'show_family_members': association,
        'family_members': profile.get('family_members') if association else None,
        'household_members': member.household_members,
    }


def registration_tabs(sections):
    groups = {
        'personal': {'key': 'personal', 'label': 'Personal', 'icon': 'profile', 'fields': []},
        'contact': {'key': 'contact', 'label': 'Address & Contact', 'icon': 'pin', 'fields': []},
        'family': {'key': 'family', 'label': 'Family & Edu', 'icon': 'family', 'fields': []},
        'assessment': {'key': 'assessment', 'label': 'IDs & Assessment', 'icon': 'document', 'fields': []},
    }
    for title, fields in sections or []:
        section = title.casefold()
        for label, value in fields:
            name = label.casefold()
            if section.startswith('address') or name in ('email', 'email address', 'contact number'):
                key = 'contact'
            elif 'control number' in name:
                key = 'assessment'
            elif section.startswith('personal'):
                key = 'personal'
            elif section.startswith(('family', 'disability')) or name in ('education', 'number of dependents'):
                key = 'family'
            else:
                key = 'assessment'
            groups[key]['fields'].append({'label': label, 'value': value,
                'missing': value in (None, '', 'Not provided', 'Not recorded')})
    return [group for group in groups.values() if group['fields']]
