"""Screen-only decoration of the existing permission-scoped report rows."""


def member_rows(rows):
    result = []
    for control_number, name, joined, status in rows:
        words = name.split()
        initials = (words[0][0] + words[-1][0] if len(words) > 1 else name[:2]).upper()
        result.append({'control_number': control_number, 'name': name, 'joined': joined,
            'status': status, 'status_code': status.lower(), 'initials': initials or '?',
            'tone': sum(ord(character) for character in name) % 6})
    return result


def report_rows(kind, rows):
    """Decorate only the existing report projection, including restricted values."""
    result = []
    for values in rows:
        if kind == 'applications':
            reference, member, program, submitted, status, eligibility, selection, approval, received = values
            row = dict(reference=reference, member=member, program=program, submitted=submitted,
                status=status, eligibility=eligibility, selection=selection.replace('_', ' ').title(),
                approval=approval, received=received, selected=selection.upper() in ('SELECTED', 'APPROVED'))
            row['show_eligibility'] = eligibility not in (status, 'Restricted')
            row['selection_code'] = selection.lower()
        elif kind == 'programs':
            program, assistance, created, closes, slots, status = values
            row = dict(program=program, assistance=assistance, created=created, closes=closes,
                slots=slots, status=status)
        else:
            member, program, assistance, received_on, reference, status = values
            identity = member_rows([('', member, '', status)])[0]
            row = dict(member=member, program=program, assistance=assistance, received_on=received_on,
                reference=reference, status=status, initials=identity['initials'], tone=identity['tone'])
        row['status_code'] = status.lower().replace(' ', '-')
        assistance = row.get('assistance', '').lower()
        row['assistance_icon'] = ('medical' if 'medical' in assistance or 'health' in assistance
            else 'food' if 'food' in assistance or 'nutrition' in assistance
            else 'device' if 'device' in assistance else 'support')
        result.append(row)
    return result
