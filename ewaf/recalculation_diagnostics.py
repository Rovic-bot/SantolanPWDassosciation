"""G17 in-memory fixture simulation; no application services, ORM or settings.

simulate_fixture(name) is the supported entry. _Simulation is a private source-
fixture/test seam, not an arbitrary-input calculator or authorization service.
"""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone

from .normalization import CRITERIA
from .ranking_diagnostics import BARRIERS, FixtureIssue, canonical, _evaluate_payload

ENGINE = 'g17-synthetic-history-1'
DOMAIN = 'g17-synthetic-history-v1'
LABEL = 'SIMULATION ONLY — NO OPERATIONAL AUTHORIZATION OR PERSISTENCE'
RULES = {
    'mode': 'ILLUSTRATIVE_ONLY', 'pool': 'COMPLETE_PINNED_POOL',
    'ties': 'EXACT_GROUPS_ONLY', 'repeat': 'REUSE_CURRENT_CONTEXT_APPEND_ATTEMPT',
    'revisions': 'INPUT_CONFIGURATION_EVIDENCE_DATE',
    'expiry': 'INCLUSIVE_ASIA_MANILA_DATE', 'promotion': 'COMPLETE_UNCHANGED_GENERATION',
}
VERSION_KEYS = ('inputs', 'configuration', 'evidence_policy', 'scoring_policy',
                'ranking_policy', 'evidence', 'governance')
FINDINGS = ('EVIDENCE_MAPPING_PENDING', 'EVIDENCE_MAPPING_INVALID', 'PR_FINDINGS_INCOMPLETE',
            'PR_ATTESTATION_REQUIRED', 'REUSABLE_TYPE_MISMATCH', 'ARTIFACT_INTEGRITY_FAILED')
POLICIES = ('admission', 'cutoff', 'revisions', 'evidence', 'normalization', 'ties', 'authority', 'pa_scope')
TRIGGERS = ('INITIAL', 'INPUT_CORRECTION', 'CONFIGURATION_REVISION', 'EVIDENCE_REVIEW',
            'DATE_REEVALUATION', 'RETRY', 'POOL_CHANGE', 'TERMS_CHANGE', 'PA_CHANGE')


def digest(kind, value):
    return hashlib.sha256(canonical([DOMAIN, kind, value]).encode('ascii')).hexdigest()


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise FixtureIssue('G17_SCHEMA_INVALID')


def _identity(value):
    if type(value) is not str or not re.fullmatch(r'SYN-G17-[A-Z0-9-]{1,60}', value):
        raise FixtureIssue('G17_SYNTHETIC_ID_REQUIRED')


def _date(value):
    try:
        if type(value) is not str or date.fromisoformat(value).isoformat() != value:
            raise ValueError
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise FixtureIssue('G17_DATE_INVALID') from None


def _instant(value):
    try:
        if type(value) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
            raise ValueError
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        raise FixtureIssue('G17_TIME_INVALID') from None


def _local_date(at):
    return _instant(at).astimezone(timezone(timedelta(hours=8))).date()


def _seal(kind, payload):
    row = {**payload, 'mode': 'SIMULATION_ONLY', 'label': LABEL,
           'effective_authorization': False, 'operational_ready': False}
    row['digest'] = digest(kind, row)
    # Strings are immutable; every exported object is decoded into a fresh tree.
    return canonical(row)


def _components(snapshot):
    pool, context = snapshot['pool'], snapshot['context']
    contract = pool['contract']
    return {
        'inputs': [{'id': row['id'], 'inputs': row['inputs']} for row in pool['candidates']],
        'configuration': {key: contract[key] for key in ('criteria', 'judgments', 'validation')},
        'scoring_policy': {key: contract[key] for key in ('definitions', 'score_engine', 'score_profile', 'score_settings')},
        'ranking_policy': {key: contract[key] for key in ('direction', 'pool_ids', 'illustrative_capacity', 'scale')},
        'evidence_policy': snapshot['rules'], 'evidence': context['evidence'],
        'governance': {key: context[key] for key in ('eligibility_current', 'terms_current', 'binding_current', 'unresolved')},
    }


def _blockers(snapshot, at):
    context = snapshot['context']
    today = _local_date(at)
    reasons = ['POLICY_UNRESOLVED:' + name for name in context['unresolved']]
    if today != _date(context['evaluation_date']):
        reasons.append('EVALUATION_DATE_CHANGED')
    for field, code in (('eligibility_current', 'ELIGIBILITY_STALE'),
                        ('terms_current', 'TERMS_CHANGED'), ('binding_current', 'BINDING_INVALID')):
        if not context[field]:
            reasons.append(code)
    for findings in context['evidence'].values():
        for row in findings.values():
            if row['state'] != 'VERIFIED':
                reasons.append({'MISSING': 'CRITERION_MISSING', 'REJECTED': 'CRITERION_REJECTED'}.get(
                    row['state'], 'CRITERION_NOT_VERIFIED'))
            if not row['source_current']:
                reasons.append('SOURCE_CHANGED')
            if row['disputed']:
                reasons.append('EVIDENCE_DISPUTED')
            if row['expires_on'] is not None and _date(row['expires_on']) < today:
                reasons.append('EVIDENCE_EXPIRED')
            reasons.extend(row['findings'])
    return sorted(set(reasons))


class _Simulation:
    """Private, bounded, single-process simulation. No durable or thread-safe API."""

    def __init__(self, source):
        from .recalculation_fixtures import load_pool, POOLS
        _fields(source, 'schema_version scenario_id scope rules actors contexts events')
        if type(source['schema_version']) is not int or source['schema_version'] != 1:
            raise FixtureIssue('G17_VERSION_UNSUPPORTED')
        _identity(source['scenario_id'])
        _identity(source['scope'])
        if source['rules'] != RULES:
            raise FixtureIssue('G17_SIMULATION_RULES_UNRESOLVED')
        if (type(source['actors']) is not dict or not 1 <= len(source['actors']) <= 8 or
                type(source['contexts']) is not dict or not 1 <= len(source['contexts']) <= 16 or
                type(source['events']) is not list or not 1 <= len(source['events']) <= 64):
            raise FixtureIssue('G17_RESOURCE_LIMIT')
        self._source = canonical(source)
        self._scope = source['scope']
        self._actors = canonical(source['actors'])
        for key, actor in source['actors'].items():
            _identity(key)
            _fields(actor, 'scope active capability')
            _identity(actor['scope'])
            if type(actor['active']) is not bool or actor['capability'] not in ('SIMULATE', 'READ_ONLY'):
                raise FixtureIssue('G17_ACTOR_INVALID')
        self._contexts = {}
        bindings = {}
        for key, context in source['contexts'].items():
            _identity(key)
            _fields(context, 'pool_fixture versions evidence eligibility_current terms_current binding_current unresolved evaluation_date')
            _fields(context['versions'], ' '.join(VERSION_KEYS))
            for value in context['versions'].values():
                _identity(value)
            for field in ('eligibility_current', 'terms_current', 'binding_current'):
                if type(context[field]) is not bool:
                    raise FixtureIssue('G17_SCHEMA_INVALID')
            if (type(context['unresolved']) is not list or len(context['unresolved']) > len(POLICIES) or
                    any(type(item) is not str or item not in POLICIES for item in context['unresolved'])):
                raise FixtureIssue('G17_SCHEMA_INVALID')
            _date(context['evaluation_date'])
            pool = load_pool(context['pool_fixture'])
            _fields(context['evidence'], ' '.join(pool['contract']['pool_ids']))
            for findings in context['evidence'].values():
                _fields(findings, ' '.join(CRITERIA))
                for row in findings.values():
                    _fields(row, 'state source_current disputed expires_on findings')
                    if (row['state'] not in ('MISSING', 'DECLARED', 'NEEDS_REVIEW', 'VERIFIED', 'REJECTED') or
                            type(row['source_current']) is not bool or type(row['disputed']) is not bool or
                            type(row['findings']) is not list or len(row['findings']) > len(FINDINGS) or
                            any(type(item) is not str or item not in FINDINGS for item in row['findings'])):
                        raise FixtureIssue('G17_EVIDENCE_INVALID')
                    if row['expires_on'] is not None:
                        _date(row['expires_on'])
            snapshot = {'context': context, 'pool': pool, 'pool_checksum': POOLS[context['pool_fixture']],
                        'rules': source['rules'], 'scope': self._scope, 'evaluation_timezone': 'Asia/Manila'}
            # A version label cannot secretly denote two different contents.
            for kind, content in _components(snapshot).items():
                identity = (kind, context['versions'][kind])
                fingerprint = digest(kind, content)
                if identity in bindings and bindings[identity] != fingerprint:
                    raise FixtureIssue('G17_VERSION_CONTENT_CONFLICT')
                bindings[identity] = fingerprint
            self._contexts[key] = canonical(snapshot)
        self._attempts = ()
        self._results = ()
        self._audit = ()
        self._pending = {}
        self._finished = {}
        self._observed = None
        self._generation = 0
        self._current = None
        self._last = None
        self._time = None

    def _snapshot(self, key):
        if type(key) is not str or key not in self._contexts:
            raise FixtureIssue('G17_CONTEXT_UNKNOWN')
        return json.loads(self._contexts[key])

    def _audit_event(self, event, outcome, reasons=(), **extra):
        row = {'sequence': len(self._audit) + 1, 'event': event, 'outcome': outcome,
               'reasons': sorted(set(reasons)), 'generation': self._generation,
               'actor': event.get('actor', 'SYN-G17-SIMULATOR'),
               'reason': event.get('reason', 'Explicit fixture event; no runtime actor.'),
               'simulated_current_result': self._current, **extra}
        self._audit += (_seal('audit', row),)
        return json.loads(self._audit[-1])

    def _fresh(self, at):
        if self._current:
            row = json.loads(self._results[self._current - 1])
            if self._observed != row['context_digest'] or _blockers(row['snapshot'], at):
                self._current = None

    def _transition_reasons(self, snapshot, trigger):
        if trigger in ('POOL_CHANGE', 'TERMS_CHANGE', 'PA_CHANGE'):
            return [{'POOL_CHANGE': 'POOL_CHANGE_POLICY_UNRESOLVED', 'TERMS_CHANGE': 'G06_B2_B3_UNAVAILABLE',
                     'PA_CHANGE': 'PA_SCOPE_POLICY_UNRESOLVED'}[trigger]]
        if self._last is None:
            return [] if trigger in ('INITIAL', 'RETRY') else ['INITIAL_RESULT_REQUIRED']
        old = json.loads(self._results[self._last - 1])['snapshot']
        old_parts, new_parts = _components(old), _components(snapshot)
        changed = {key for key in VERSION_KEYS if old_parts[key] != new_parts[key] or
                   old['context']['versions'][key] != snapshot['context']['versions'][key]}
        if old['pool']['contract']['pool_ids'] != snapshot['pool']['contract']['pool_ids']:
            return ['POOL_CHANGE_POLICY_UNRESOLVED']
        if old['context']['evaluation_date'] != snapshot['context']['evaluation_date']:
            changed.add('evaluation_date')
        allowed = {'INPUT_CORRECTION': {'inputs', 'evidence'},
                   'CONFIGURATION_REVISION': {'configuration', 'scoring_policy', 'ranking_policy'},
                   'EVIDENCE_REVIEW': {'evidence', 'evidence_policy', 'governance'},
                   'DATE_REEVALUATION': {'evaluation_date'}, 'RETRY': set(), 'INITIAL': set()}
        if trigger == 'INITIAL' or not changed <= allowed[trigger] or not changed and trigger != 'RETRY':
            return ['RECALCULATION_TRIGGER_MISMATCH']
        return []

    def step(self, event):
        """Explicit fixture event only. Caller data never becomes stored aliases."""
        if type(event) is not dict or event.get('type') not in ('OBSERVE', 'BEGIN', 'FINISH'):
            raise FixtureIssue('G17_EVENT_INVALID')
        fields = {'OBSERVE': 'type context at', 'BEGIN': 'type context actor reason trigger at',
                  'FINISH': 'type attempt at'}
        _fields(event, fields[event['type']])
        event = json.loads(canonical(event))
        instant = _instant(event['at'])
        if self._time is not None and instant < self._time:
            raise FixtureIssue('G17_TIME_REVERSED')
        if len(self._audit) >= 64:
            raise FixtureIssue('G17_RESOURCE_LIMIT')
        if event['type'] in ('OBSERVE', 'BEGIN'):
            snapshot = self._snapshot(event['context'])
        if event['type'] == 'BEGIN':
            _identity(event['actor'])
            if type(event['reason']) is not str or not 1 <= len(event['reason'].strip()) <= 200:
                raise FixtureIssue('G17_REASON_REQUIRED')
            if type(event['trigger']) is not str or event['trigger'] not in TRIGGERS:
                raise FixtureIssue('G17_TRIGGER_INVALID')
        if event['type'] == 'FINISH' and (type(event['attempt']) is not int or
                not 1 <= event['attempt'] <= len(self._attempts)):
            raise FixtureIssue('G17_ATTEMPT_UNKNOWN')
        self._time = instant
        self._fresh(event['at'])
        if event['type'] == 'OBSERVE':
            context_digest = digest('context', snapshot)
            before = self._observed
            if context_digest != before:
                self._generation += 1
                self._observed = context_digest
                self._current = None
            return self._audit_event(event, 'SIMULATED_SOURCE_OBSERVED', before_context=before,
                                     after_context=context_digest, versions=snapshot['context']['versions'])
        if event['type'] == 'BEGIN':
            return self._begin(event, snapshot)
        return self._finish(event)

    def _begin(self, event, snapshot):
        actor = json.loads(self._actors).get(event['actor'])
        number = len(self._attempts) + 1
        context_digest = digest('context', snapshot)
        row = {'id': number, 'actor': event['actor'], 'reason': event['reason'], 'at': event['at'],
               'trigger': event['trigger'], 'requested_context': event['context'],
               'generation': self._generation, 'context_digest': context_digest,
               'previous_result': self._last, 'result': None, 'reasons': []}
        if not actor or not actor['active'] or actor['capability'] != 'SIMULATE' or actor['scope'] != self._scope:
            row.update(outcome='SIMULATED_DENIED', reasons=['SIMULATED_PERMISSION_DENIED'])
        else:
            row['versions'] = snapshot['context']['versions']
            reasons = _blockers(snapshot, event['at'])
            if self._observed != context_digest:
                reasons.append('EXPECTED_CONTEXT_STALE')
            if not reasons and self._current and event['trigger'] not in ('POOL_CHANGE', 'TERMS_CHANGE', 'PA_CHANGE'):
                row.update(outcome='SIMULATED_REUSED', result=self._current)
            else:
                reasons.extend(self._transition_reasons(snapshot, event['trigger']))
                if reasons:
                    row.update(outcome='SIMULATED_BLOCKED', reasons=sorted(set(reasons)))
                else:
                    # G16's private SOURCE-FIXTURE validation seam, only after our
                    # pinned loader. Never expose this seam as an applicant API.
                    comparison = _evaluate_payload(snapshot['pool'])
                    if not comparison['complete'] or comparison['reasons']:
                        row.update(outcome='SIMULATED_BLOCKED', reasons=sorted({
                            entry['code'] for entry in comparison['reasons']} | {'CALCULATION_INCOMPLETE'}))
                    else:
                        row.update(outcome='SIMULATED_PENDING_RECHECK', snapshot=snapshot, comparison=comparison)
                        self._pending[number] = True
        self._attempts += (_seal('attempt', row),)
        return self._audit_event(event, row['outcome'], row['reasons'], attempt=number,
                                 versions=row.get('versions'), result=row['result'])

    def _finish(self, event):
        number = event['attempt']
        row = json.loads(self._attempts[number - 1])
        if number in self._finished:
            # Repeat completion records an observation, never restores old currentness.
            return self._audit_event(event, 'SIMULATED_FINISH_REPEATED', attempt=number,
                                     original_outcome=self._finished[number], actor=row['actor'],
                                     reason=row['reason'], versions=row.get('versions'))
        if number not in self._pending:
            return self._audit_event(event, 'SIMULATED_BLOCKED', ['ATTEMPT_NOT_PENDING'], attempt=number,
                                     actor=row['actor'], reason=row['reason'], versions=row.get('versions'))
        reasons = _blockers(row['snapshot'], event['at'])
        if row['generation'] != self._generation or row['context_digest'] != self._observed:
            reasons.append('SOURCE_CHANGED_DURING_CALCULATION')
        result_number = None
        if reasons:
            outcome = 'SIMULATED_STALE'
        elif self._current:
            outcome, result_number = 'SIMULATED_REUSED', self._current
        else:
            result_number = len(self._results) + 1
            result = {'id': result_number, 'previous_result': self._last, 'attempt': number,
                      'scope': self._scope, 'actor': row['actor'], 'reason': row['reason'],
                      'at': event['at'], 'generation': self._generation,
                      'context_digest': row['context_digest'], 'snapshot': row['snapshot'],
                      'comparison': row['comparison']}
            self._results += (_seal('result', result),)
            self._current = self._last = result_number
            outcome = 'SIMULATED_PROMOTED'
        del self._pending[number]
        self._finished[number] = outcome
        return self._audit_event(event, outcome, reasons, attempt=number, result=result_number,
                                 versions=row['snapshot']['context']['versions'], actor=row['actor'], reason=row['reason'])

    def report(self):
        last = json.loads(self._audit[-1])['outcome'] if self._audit else None
        return json.loads(_seal('report', {
            'schema_version': 1, 'engine': ENGINE, 'scenario_id': json.loads(self._source)['scenario_id'],
            'source_digest': digest('scenario', json.loads(self._source)), 'rules': dict(RULES),
            'barriers': [*BARRIERS, 'OPERATIONAL_RECALCULATION_UNAVAILABLE'],
            'complete': not self._pending and last in ('SIMULATED_PROMOTED', 'SIMULATED_REUSED'),
            'simulated_current_result': self._current, 'pending_attempts': sorted(self._pending),
            'attempts': [json.loads(row) for row in self._attempts],
            'results': [json.loads(row) for row in self._results],
            'audit': [json.loads(row) for row in self._audit],
        }))


def simulate_fixture(name):
    """Replay a checksum-pinned G17 scenario name; no arbitrary input/upload API."""
    from .recalculation_fixtures import load_scenario
    try:
        source = load_scenario(name)
        simulation = _Simulation(source)
        for event in source['events']:
            simulation.step(event)
        return simulation.report()
    except FixtureIssue as error:
        return json.loads(_seal('invalid-scenario', {
            'schema_version': 1, 'engine': ENGINE, 'complete': False,
            'barriers': [*BARRIERS, 'OPERATIONAL_RECALCULATION_UNAVAILABLE'],
            'reasons': [str(error)], 'simulated_current_result': None,
            'attempts': [], 'results': [], 'audit': [], 'pending_attempts': [],
        }))
