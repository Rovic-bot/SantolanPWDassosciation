"""Short, display-only explanations of existing ranking validation results."""


def mark_input_review(item):
    errors = item.get('readiness_errors', [])
    needs_review = bool(errors or item.get('input_badge') == 'Review needed')
    item['needs_review'] = needs_review
    item['review_summary'] = ''
    if not needs_review:
        return
    reasons = []
    for error in errors:
        message = error.lower()
        if 'qualification' in message:
            reason = 'program qualifications'
        elif 'identity' in message or 'photo' in message:
            reason = 'identity evidence'
        elif 'changed' in message or 'change' in message or 'stale' in message:
            reason = 'updated information'
        elif 'membership' in message or 'prpwd' in message:
            reason = 'membership verification'
        elif 'eligibility' in message:
            reason = 'eligibility'
        elif 'document' in message or 'requirement' in message or 'checklist' in message:
            reason = 'required documents'
        elif 'income' in message or 'employment' in message or 'household' in message or 'scoring' in message:
            reason = 'scoring inputs'
        else:
            reason = 'applicant information'
        if reason not in reasons:
            reasons.append(reason)
    reasons = reasons or ['applicant information']
    if len(reasons) > 3:
        reasons = reasons[:2] + ['other applicant information']
    text = ' and '.join(reasons) if len(reasons) < 3 else ', '.join(reasons[:-1]) + ' and ' + reasons[-1]
    item['review_summary'] = 'Check ' + text + '.'
    item['input_status'] = item['review_summary']
    if item.get('input_state') != 'excluded':
        item.update(input_state='pending', input_badge='Needs review', input_icon='info')


def workspace_notice(*, ready, result, inventory, configuration_pending, missing, problems):
    if result.get('invalid_calculation'):
        return 'This saved ranking could not be verified.'
    count = sum(item['needs_review'] for item in inventory)
    if configuration_pending or missing:
        if count:
            return f'Scoring configuration pending; {count} applicant' + (' also needs' if count == 1 else 's also need') + ' review.'
        return 'Scoring configuration pending.'
    if count:
        return f'{count} applicant' + (' needs' if count == 1 else 's need') + ' review; select a marked row to see why.'
    text = ' '.join([*problems, *result.get('problems', [])]).lower()
    if 'weights changed' in text:
        return 'Scoring weights changed; update the ranking.'
    if 'rule changed' in text:
        return 'Scoring rules changed; update the ranking.'
    if any(word in text for word in ('qualification', 'identity', 'eligibility')):
        return 'Applicant eligibility or evidence needs review.'
    if 'expired' in text or 'validity' in text:
        return 'The ranking or its evidence has expired and needs review.'
    if 'cutoff' in text or 'application period' in text:
        return 'Ranking is waiting for the approved application period or assessment cutoff.'
    if result and not result.get('active'):
        return 'The saved ranking no longer matches current records.'
    if not ready:
        return 'No eligible applicants are ready to rank.' if not inventory else 'Scoring settings or program details need review.'
    return ''
