"""Document Table 11 only. These values confer no evidence acceptance on real members."""
from .engine import CRITERIA, SOURCES, freeze_pool


def example_pool(program='SYNTHETIC-DOCUMENT-EXAMPLE', version=1):
    applicants = []
    for key, values in (('A', ('5000', '4', 'Seasonal Worker', '1', '4')),
                        ('B', ('12500', '3', 'Unemployed', '0', '2')),
                        ('C', ('20000', '1', 'Full-Time Worker', '3', '6'))):
        applicants.append({'id': key, 'eligibility': 'ACCEPTED_ELIGIBLE', 'inputs': {
            code: {'value': value, 'state': 'ACCEPTED', 'disputed': False, 'stale': False,
                   'source': source, 'evidence_id': f'SYNTHETIC-{key}-{code}', 'evidence_version': version,
                   'period': 'Document example assumption; not an actual assessment period',
                   'accepted_at': '2026-10-25T00:00:00+00:00', 'valid_until': None}
            for code, value, source in zip(CRITERIA, values, SOURCES)}})
    return freeze_pool(program=program, version=version, cutoff='2026-10-25T00:00:00+00:00',
                       expected_ids=['A', 'B', 'C'], applicants=applicants)
