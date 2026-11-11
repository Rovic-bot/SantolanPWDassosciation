"""Versioned policy-review artifacts for the new dataset engine only.

No ORM, approval writer, weight approval, program assignment or operational dispatch
is provided. A draft and a successful synthetic example cannot authorize scoring.
"""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re

from . import engine
from .fixtures import example_pool
from .math import CalculationError, CRITERIA, METHOD, packed


POLICY_ID = 'shared-hi-si-es-pa-hm'
DRAFT_STATUS = 'DRAFT_FOR_REVIEW'
DOCUMENT_RULES_DIGEST = '3ee945d74bc698efede19317fb8910d6ead73d454e6932cee302930e460eaff3'
CATALOG = {
    1: ('shared-v1-draft-1.json', 'cbb94d36ed7d779292a5b7b090b21e19b05c4dc8e220b56e9ecb6cc810af5fb7'),
}
BINDING_BLOCKER = (
    'PROGRAM_POLICY_BINDING',
    'Each new-method program must bind an immutable approved policy ID, revision and content digest '
    'with its authorized weight-version reference. A shared draft or mutable latest-version pointer '
    'cannot be assigned; no approved binding is created by this draft.',
)


def _validate(data):
    required = {'schema_version', 'policy_id', 'revision', 'version', 'previous_digest', 'status',
                'method', 'authorization', 'weight_authorization_reference', 'source',
                'document_rules', 'proposals', 'unresolved_decisions', 'readiness_contract',
                'versioning_contract'}
    if not isinstance(data, dict) or set(data) != required:
        raise CalculationError('Use the complete versioned draft schema.')
    revision = data['revision']
    if (data['schema_version'] != 1 or data['policy_id'] != POLICY_ID or data['method'] != METHOD
            or type(revision) is not int or revision < 1
            or data['version'] != f'HI-SI-ES-PA-HM-DRAFT-{revision:03d}'
            or data['status'] != DRAFT_STATUS or data['authorization'] is not None
            or data['weight_authorization_reference'] is not None):
        raise CalculationError('Only an unapproved new-method draft is supported; no authority may be fabricated.')
    predecessor = data['previous_digest']
    if (revision == 1 and predecessor is not None or revision > 1
            and (not isinstance(predecessor, str) or not re.fullmatch('[0-9a-f]{64}', predecessor))):
        raise CalculationError('A new draft revision must retain its predecessor digest.')
    try:
        rules = data['document_rules']
        if (data['source']['path'] != engine.SOURCE_FILE or data['source']['sha256'] != engine.SOURCE_SHA256
                or rules['criteria'] != list(CRITERIA)
                or rules['employment_encoding']['mapping'] != engine.ES
                or rules['normalization']['method'] != engine.NORMALIZATION
                or rules['normalization']['bounds_source'] != 'complete_accepted_eligible_pool_at_evaluation'
                or rules['normalization']['numerical_bounds'] is not None
                or rules['directions']['values'] != dict(zip(CRITERIA, engine.DIRECTIONS))
                or engine.fingerprint(rules) != DOCUMENT_RULES_DIGEST):
            raise CalculationError('Retain the document rules and evaluation-time dataset bounds in this draft.')
        proposals = data['proposals']
        if set(proposals) != {'si_rubric', 'assessment_periods', 'household_definition', 'pa_scope', 'ranking_convention'}:
            raise CalculationError('Retain each proposed policy choice for review.')
        decisions = data['unresolved_decisions']
        codes = [item['code'] for item in decisions]
        if (not decisions or len(set(codes)) != len(codes)
                or any(item['status'] != 'OPEN' or not item['question'].strip() for item in decisions)
                or any(item['status'] != 'PROPOSED_NOT_AUTHORIZED' or item['decision'] not in codes
                       for item in proposals.values())):
            raise CalculationError('Proposals and unresolved decisions cannot be marked authorized by a draft.')
    except (KeyError, TypeError, AttributeError) as error:
        raise CalculationError('Incomplete policy source, proposal or decision metadata.') from error


@dataclass(frozen=True)
class PolicyDraft:
    snapshot: str

    def __post_init__(self):
        try:
            data = json.loads(self.snapshot)
        except (ValueError, TypeError) as error:
            raise CalculationError('Invalid policy snapshot.') from error
        _validate(data)
        if engine.canonical(data) != self.snapshot:
            raise CalculationError('Use a canonical immutable policy snapshot.')

    @property
    def data(self):
        return json.loads(self.snapshot)

    @property
    def digest(self):
        return sha256(self.snapshot.encode()).hexdigest()

    @property
    def reference(self):
        data = self.data
        return {'policy_id': data['policy_id'], 'revision': data['revision'], 'digest': self.digest}


def load_draft(revision=1):
    """An explicit retained revision, never a mutable latest-policy lookup."""
    if type(revision) is not int or revision not in CATALOG:
        raise CalculationError('Unknown retained policy draft revision.')
    filename, expected = CATALOG[revision]
    raw = (Path(__file__).with_name('policies') / filename).read_bytes()
    # Permit checkout newline conversion while preserving the artifact's content.
    if sha256(raw.replace(b'\r\n', b'\n')).hexdigest() != expected:
        raise CalculationError('Retained policy content changed. Create a new revision instead of overwriting it.')
    return PolicyDraft(engine.canonical(json.loads(raw)))


def revise_proposal(draft, *, expected_digest, name, description):
    """Return a new review-only snapshot; do not write a file or rebind a program."""
    if expected_digest != draft.digest:
        raise CalculationError('The draft changed. Review the current snapshot before proposing a revision.')
    data = draft.data
    if name not in data['proposals'] or not isinstance(description, str) or not description.strip():
        raise CalculationError('Choose an existing proposal and supply its revised description.')
    if len(description) > 4000:
        raise CalculationError('Keep a proposed description within 4,000 characters.')
    data['proposals'][name]['description'] = description.strip()
    data['previous_digest'] = draft.digest
    data['revision'] += 1
    data['version'] = f'HI-SI-ES-PA-HM-DRAFT-{data["revision"]:03d}'
    return PolicyDraft(engine.canonical(data))


def policy_readiness(draft):
    """Policy can be reviewed before any applicant pool or numerical bounds exist."""
    data = draft.data
    return {'status': 'BLOCKED_DRAFT', 'ready': False, 'reference': draft.reference,
            'numerical_bounds_required_before_opening': False,
            'decisions': data['unresolved_decisions'],
            'authorization': None, 'weight_authorization_reference': None,
            'program_binding': {'ready': False, 'code': BINDING_BLOCKER[0], 'message': BINDING_BLOCKER[1]},
            'integration': 'Accepted-evidence capture and explicit operational enablement remain required.'}


def applicant_data_readiness(pool=None):
    """Separate arithmetic readiness for synthetic data from policy authorization.

    Actual accepted-evidence capture is not implemented. No real member input can
    be certified by this function; its successful state is expressly synthetic.
    """
    result = {'status': 'NOT_EVALUATED', 'ready': False, 'official_ready': False,
              'bounds': None, 'issues': [], 'pool_digest': None}
    if pool is None:
        return result
    result.update(status='BLOCKED', pool_digest=pool.digest)
    try:
        data = engine.check_pool(pool)
        for row in data['applicants']:
            if row['inputs']['PA'].get('history_complete') is not True:
                raise CalculationError('Incomplete PA history cannot establish a zero or accepted release count.')
        values = [[Fraction(row['inputs'][code]['encoded']) for row in data['applicants']] for code in CRITERIA]
        constant = [code for code, column in zip(CRITERIA, values) if min(column) == max(column)]
        result['bounds'] = [{'criterion': code, 'lower': packed(min(column)), 'upper': packed(max(column))}
                            for code, column in zip(CRITERIA, values)]
        if constant:
            raise CalculationError('Constant-value columns require an authorized rule: ' + ', '.join(constant))
    except (CalculationError, KeyError, TypeError, ValueError) as error:
        result['issues'] = [str(error)]
    else:
        result.update(status='SYNTHETIC_READY', ready=True)
    return result


def synthetic_pool():
    """Document inputs with explicitly fictional complete history for this demo."""
    data = example_pool('SYNTHETIC-SHARED-POLICY-DRAFT').data
    for row in data['applicants']:
        row['inputs']['PA']['history_complete'] = True
        row['inputs']['PA']['coverage_note'] = 'Synthetic fixture assumption, not verified member history.'
    return engine.freeze_pool(**{key: data[key] for key in
        ('program', 'version', 'cutoff', 'expected_ids', 'applicants', 'unresolved_ids')})


@dataclass(frozen=True)
class PolicyDemonstration:
    snapshot: str

    @property
    def data(self):
        return json.loads(self.snapshot)

    @property
    def digest(self):
        return sha256(self.snapshot.encode()).hexdigest()


def demonstrate(draft, *, pool=None, capacity=None):
    pool = synthetic_pool() if pool is None else pool
    readiness = applicant_data_readiness(pool)
    if not readiness['ready']:
        raise CalculationError('; '.join(readiness['issues']) or 'A complete synthetic accepted pool is required.')
    configuration = engine.configure(classify=False)
    result = engine.calculate(pool, configuration, capacity=capacity)
    return PolicyDemonstration(engine.canonical({
        'synthetic': True, 'official': False, 'policy_snapshot': draft.data, 'policy_reference': draft.reference,
        'policy_readiness': policy_readiness(draft), 'applicant_data_readiness': readiness,
        'configuration': configuration.data, 'pool': pool.data, 'result': result,
        'weight_note': 'Unchanged document-example weights only; no weight approval is performed.',
        'si_note': 'Document SI values 4, 3 and 1 are assumed synthetic assessments; the proposed rubric did not derive them.',
        'ranking_note': 'Competition ranks demonstrate a proposed convention; no beneficiary is selected.'}))


def replay(demonstration):
    """Replay retained snapshots, without consulting the current shared draft."""
    data = demonstration.data
    draft = PolicyDraft(engine.canonical(data['policy_snapshot']))
    pool = engine.FrozenPool(engine.canonical(data['pool']))
    reproduced = demonstrate(draft, pool=pool, capacity=data['result']['capacity_example'])
    if reproduced.snapshot != demonstration.snapshot:
        raise CalculationError('The retained policy demonstration does not replay exactly.')
    return reproduced
