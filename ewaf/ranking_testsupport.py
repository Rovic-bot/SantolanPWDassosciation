"""Invented mathematical test data only. No database, names or record references."""
from copy import deepcopy
from .ahp_validation import PAIRS, validate_ahp
from .normalization import CRITERIA, ENGINE, PROFILE, SETTINGS
from .weighted_scoring import calculate_synthetic
from .ranking_diagnostics import content_digest


def build_fixture(direction='HIGH_FIRST', values=('0', '0.5', '0.5', '1'), *, precision=False):
    judgments = {'criteria': list(CRITERIA), 'mode': 'pairs', 'values': {key: '1' for key in PAIRS}}
    if precision:
        judgments['values']['SI:ES'] = '2'
    identities = ['SYN-G16-' + chr(65 + index) for index in range(len(values))]
    contract = {'criteria': list(CRITERIA), 'judgments': judgments, 'validation': validate_ahp(judgments),
                'score_engine': ENGINE, 'score_profile': PROFILE, 'score_settings': dict(SETTINGS),
                'scale': '0-1', 'direction': direction, 'pool_ids': identities,
                'context': {'scenario': 'SYN-G16-EXAMPLE', 'evaluation': 'SYNTHETIC-EPOCH-1'},
                'illustrative_capacity': 2,
                'definitions': {code: {'source_type': 'synthetic', 'unit': 'fixture',
                    'direction': 'benefit', 'bounds': {'method': 'fixed', 'lower': '0', 'upper': '1'},
                    'encoding': None} for code in CRITERIA}}
    candidates = [{'id': identity, 'inputs': {code: {'value': value, 'source_type': 'synthetic',
                    'unit': 'fixture'} for code in CRITERIA}} for identity, value in zip(identities, values)]
    fixture = {'schema_version': 1, 'fixture_id': 'SYN-G16-EXAMPLE', 'revision': 1,
               'contract': contract, 'candidates': candidates}
    return reseal(fixture)


def reseal(fixture):
    """Explicit test-only source builder. Not a trust or authorization function."""
    contract = fixture['contract']
    fixture['contract_digest'] = content_digest('contract', contract)
    manifest = []
    for candidate in fixture['candidates']:
        candidate['contract_digest'] = fixture['contract_digest']
        candidate['calculation'] = calculate_synthetic(criteria=contract['criteria'], inputs=candidate['inputs'],
            definitions=contract['definitions'], judgments=contract['judgments'], validation=contract['validation'])
        candidate['input_digest'] = content_digest('inputs', candidate['inputs'])
        candidate['calculation_digest'] = content_digest('calculation', candidate['calculation'])
        manifest.append({key: candidate[key] for key in ('id', 'input_digest', 'calculation_digest')})
    fixture['manifest'] = sorted(manifest, key=lambda row: row['id'])
    fixture['manifest_digest'] = content_digest('manifest', fixture['manifest'])
    return deepcopy(fixture)
