"""Bounded documentary completeness only; no field can confer authority."""
from .ranking_diagnostics import BARRIERS, content_digest

DECISIONS = ('admission_exclusion', 'direction_authorization', 'cutoff', 'tie_conventions',
             'capacity_reservations', 'exceptions', 'recalculation_stale_pool',
             'human_decision_authority', 'operational_authorization')


def policy_completeness(proposal=None):
    """Optional private references are proposals, never accepted rules or values."""
    if proposal is None:
        proposal = {'schema_version': 1, 'references': {key: None for key in DECISIONS}}
    valid = (type(proposal) is dict and set(proposal) == {'schema_version', 'references'} and
             type(proposal['schema_version']) is int and proposal['schema_version'] == 1 and
             type(proposal['references']) is dict and set(proposal['references']) == set(DECISIONS))
    if valid:
        valid = all(value is None or type(value) is str and 0 < len(value.strip()) <= 200
                    for value in proposal['references'].values())
    findings = [{'decision': key, 'status': 'PENDING_ASSOCIATION_DECISION',
                 'documentary_reference_present': bool(proposal['references'][key]) if valid else False}
                for key in DECISIONS]
    return {'schema_version': 1, 'valid_schema': valid, 'effective_authorization': False,
            'operational_ready': False, 'findings': findings,
            'reasons': ([] if valid else ['RANKING_POLICY_SCHEMA_INVALID']) +
                       ['RANKING_POLICY_PENDING', *BARRIERS],
            'proposal_digest': content_digest('policy-proposal', proposal) if valid else None}
