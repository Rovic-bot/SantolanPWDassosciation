"""G17 checksum-pinned source examples; no paths/uploads or database identifiers."""
import hashlib
from pathlib import Path
from types import MappingProxyType

from .ranking_diagnostics import FixtureIssue, LIMITS, parse_fixture_json

POOLS = MappingProxyType({
    'base-v1': 'cc24ee3f9817cdc7c8f7895cea880fb5d19cfdf9e93d8453137014b2c239e20e',
    'precision-v1': '5c43cbae43b52e4f42a2077da04ef6415d90b3833ca8f52eddcc56294b052610',
    'corrected-v2': '2448659c7949bc1817dc9a63be4407db215e94de721688034d5b0cc85d7258da',
    'configuration-v2': 'eac98c32423c16683af90522977ea7fcd7287ea71d4892c55c62c29567e5e056',
    'incomplete-v2': 'dfa19e5727815c14ab0a2a2a76e6880d9b33f685d4f6b5777067c0ee00b2ab2f',
})
SCENARIOS = MappingProxyType({
    'history-v1': 'e67d86c1384acb6505915ea4fc4dc6c6ce8ed0e4756391b55f880a39c71f92c9',
    'repeat-v1': 'ae082dc05f61ee98eb6d39135cbf706db4820bc0137fa9a0dc05fa0d6059e846',
    'stale-v1': '47eb816821313b56cc887001d99951fc62231d6a4adfab4fb266a0d4ccaf9d7a',
    'incomplete-v1': '305ee8c63ed743b4960fb55099ebaed346605f8a40dcd3733cb81fcfbc899f49',
    'unresolved-v1': '6050bec1092c2ff126c0c615e78f0cfc828c93842738120738a83fdabc0ba9e1',
    'unauthorized-v1': 'faf184011c9fd5abdd7db2e3d260b7576d5aa77fd8f31008af5fc404dfc3124b',
    'precision-v1': 'f8a60fc696a62b8f93ac45c11ebc76df158441d32c87e26554880165323037f6',
})


def _load(name, registry, prefix=''):
    if type(name) is not str or name not in registry:
        raise FixtureIssue('G17_FIXTURE_NOT_ALLOWLISTED')
    path = Path(__file__).resolve().parent / 'tests_data/g17' / (prefix + name + '.json')
    try:
        with path.open('rb') as stream:
            data = stream.read(LIMITS['bytes'] + 1)
    except OSError:
        raise FixtureIssue('G17_FIXTURE_UNAVAILABLE') from None
    if len(data) > LIMITS['bytes']:
        raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
    if hashlib.sha256(data).hexdigest() != registry[name]:
        raise FixtureIssue('G17_FIXTURE_CHECKSUM_MISMATCH')
    return parse_fixture_json(data)


def load_pool(name):
    return _load(name, POOLS, 'pool-')


def load_scenario(name):
    return _load(name, SCENARIOS)
