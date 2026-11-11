"""Reuse a saved ranking across presentation edits and proven identical reviews.

Saved snapshots and scores stay immutable. Current evidence is still captured and
validated; only a complete audit chain can explain an unchanged Eligible recheck.
"""
from copy import deepcopy

from django.utils.dateparse import parse_datetime

from .evidence import digest


def comparable_observation(observation, program_id):
    from programs.models import ProgramLog
    value = deepcopy(observation)
    events = value.get('program_events', [])
    artwork = set(ProgramLog.objects.filter(program_id=program_id,
        pk__in=events, application__isnull=True, action='picture_updated').values_list('pk', flat=True))
    value['program_events'] = [pk for pk in events if pk not in artwork]
    return value


def same_eligibility_facts(before, after):
    """A direct Eligible confirmation adds an attestation, not a qualification."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    old, new = deepcopy(before), deepcopy(after)
    confirmation = {'key': 'admin_review', 'label': 'Administrator review of the submitted application',
                    'required': True, 'result': 'pass'}
    checklist = new.get('checklist')
    if (isinstance(checklist, list) and checklist and checklist[-1] == confirmation
            and old.get('checklist') == checklist[:-1]
            and all(isinstance(item, dict) for item in checklist)
            and not any(item.get('key') == 'admin_review' for item in checklist[:-1])):
        new['checklist'] = checklist[:-1]
    return old == new


def eligibility_recheck(original, current):
    """Return audit witnesses only for Eligible -> identical Eligible reviews."""
    from assistance.models import AssistanceLog
    try:
        if original['status'] != 'ELIGIBLE' or current['status'] != 'ELIGIBLE':
            return None
        before, after = original['case'], current['case']
        if not (before['eligibility'] == after['eligibility'] == 'eligible'
                and before['active'] and after['active'] and before['log_matches'] and after['log_matches']):
            return None
        old_version, new_version = original['application_version'], current['application_version']
        if type(old_version) is not int or type(new_version) is not int or new_version <= old_version:
            return None
        old_source, new_source = deepcopy(original), deepcopy(current)
        for source in (old_source, new_source):
            source.pop('application_version')
            source['case'].pop('digest')
            source['case'].pop('review_log')
        if same_eligibility_facts(old_source['case'], new_source['case']):
            new_source['case'] = deepcopy(old_source['case'])
        if old_source != new_source:
            return None
        first = AssistanceLog.objects.filter(pk=before['review_log'],
            application_id=original['application'], action='eligibility_reviewed').first()
        if not first or digest(first.snapshot['after']) != before['digest']:
            return None
        logs = list(AssistanceLog.objects.filter(application_id=original['application'],
            pk__gt=first.pk, pk__lte=after['review_log']).order_by('pk'))
        if len(logs) != new_version - old_version or not logs or logs[-1].pk != after['review_log']:
            return None
        retained = first.snapshot['after']
        witnesses = []
        for log in logs:
            old, new = log.snapshot['before'], log.snapshot['after']
            if (log.action != 'eligibility_reviewed' or old != retained or not log.actor_id
                    or log.actor_id != new['reviewed_by'] or log.notes != new['review_notes']
                    or new['eligibility'] != 'eligible'):
                return None
            old_time, new_time = parse_datetime(old['reviewed_at']), parse_datetime(new['reviewed_at'])
            if not old_time or not new_time or new_time < old_time:
                return None
            old_facts, new_facts = deepcopy(old), deepcopy(new)
            for facts in (old_facts, new_facts):
                for key in ('review_notes', 'reviewed_at', 'reviewed_by'):
                    facts.pop(key)
            if not same_eligibility_facts(old_facts, new_facts):
                return None
            retained = new
            witnesses.append({'log': log.pk, 'snapshot_digest': digest(log.snapshot)})
        if digest(retained) != after['digest']:
            return None
        return {'application': original['application'], 'original_review': first.pk,
            'original_application_version': old_version, 'current_application_version': new_version,
            'reviews': witnesses}
    except (KeyError, TypeError, ValueError):
        return None


def matches(run, observed):
    from .revised import automatic_inputs
    from .revised.fulfillment import comparison
    original, current = comparison(run.snapshot), comparison(observed)
    for snapshot in (original, current):
        snapshot['observation'] = comparable_observation(snapshot['observation'], run.program_id)
    witnesses = []
    automatic = automatic_inputs.enabled(run.configuration.policy)
    if automatic or run.configuration.uses_dataset_scoring:
        originals = {row['application']: row for row in original['manifest']}
        for row in current['manifest']:
            reference = row['application']
            saved = originals.get(reference)
            if not saved or row['source'] == saved['source']:
                continue
            witness = eligibility_recheck(saved['source'], row['source'])
            if not witness:
                continue
            old_entry, new_entry = original['eligible'].get(reference), current['eligible'].get(reference)
            if not old_entry or not new_entry:
                continue
            # Both entries have already passed capture/replay validation. Only
            # provenance derived from this exact recheck may be substituted.
            candidate = deepcopy(new_entry)
            if automatic:
                candidate['assessments']['member_record']['source_digest'] = old_entry['assessments']['member_record']['source_digest']
            candidate['pr']['eligibility_review'] = deepcopy(old_entry['pr']['eligibility_review'])
            if candidate != old_entry:
                continue
            row['source'] = deepcopy(saved['source'])
            current['eligible'][reference] = candidate
            witnesses.append(witness)
    return original == current, witnesses
