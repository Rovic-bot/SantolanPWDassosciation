"""Checksum-pinned source registry, not an upload/path-based fixture loader."""
import hashlib
from pathlib import Path
from types import MappingProxyType
from .ranking_diagnostics import FixtureIssue, LIMITS, parse_fixture_json

# Any fixture revision requires source review and a new matching checksum here.
FIXTURES = MappingProxyType({'high-first-v1': 'cc24ee3f9817cdc7c8f7895cea880fb5d19cfdf9e93d8453137014b2c239e20e', 'low-first-v1': 'e9353f7ea7d56601863845bfc9c780faf9b110a8c670c8567938026cc44a1a94', 'precision-v1': '5c43cbae43b52e4f42a2077da04ef6415d90b3833ca8f52eddcc56294b052610', 'incomplete-v1': '21e4b237096b23dc612a64896b8f283754002bb9fcd598b76dce3b40df3e2b6c'})


def load_fixture(name):
    if type(name) is not str or name not in FIXTURES:
        raise FixtureIssue('FIXTURE_NOT_ALLOWLISTED')
    path = Path(__file__).resolve().parent / 'tests_data' / 'g16' / (name + '.json')
    try:
        with path.open('rb') as stream:
            data = stream.read(LIMITS['bytes'] + 1)
    except OSError:
        raise FixtureIssue('FIXTURE_UNAVAILABLE') from None
    if len(data) > LIMITS['bytes']:
        raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
    if hashlib.sha256(data).hexdigest() != FIXTURES[name]:
        raise FixtureIssue('FIXTURE_CHECKSUM_MISMATCH')
    return parse_fixture_json(data)
