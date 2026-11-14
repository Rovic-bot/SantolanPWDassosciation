"""Build the pinned, offline PSGC catalogue from Tenasia/ph-psgc 2026-Q2.

Usage: python scripts/build_registration_addresses.py /path/to/ph-psgc
Only public geographic names/codes are copied; no map points or personal data.
"""
from collections import Counter
import json
from pathlib import Path
import sys


def build(source):
    target = Path(__file__).resolve().parent.parent / 'static/data/psgc-2026-q2'
    target.mkdir(parents=True, exist_ok=True)
    index = json.loads((source / 'psgc/index.json').read_text(encoding='utf-8'))
    cities, regions = [], []
    for region in index['regions']:
        regions.append({'code': region['code'], 'name': region['name']})
        for area in region['provinces'] + region['independent']:
            data = json.loads((source / f"psgc/areas/{area['code']}.json").read_text(encoding='utf-8'))
            province = area['name'] if data['kind'] == 'province' else ''
            for city in data['cities']:
                cities.append({'code': city['code'], 'name': city['name'], 'province': province,
                               'region': region['name'], 'region_code': region['code']})
                (target / f"{city['code']}.json").write_text(json.dumps(city['barangays'], ensure_ascii=False,
                    separators=(',', ':')) + '\n', encoding='utf-8')
    duplicates = Counter(city['name'].casefold() for city in cities)
    for city in cities:
        city['value'] = city['name']
        if duplicates[city['name'].casefold()] > 1:
            city['value'] += f" ({city['province'] or city['region']})"
        assert len(city['value']) <= 100
    assert len(regions) == 18 and len(cities) == 1642
    catalogue = {'source': index['source'], 'source_url': index['source_url'],
        'version': '2026-Q2', 'published': index['published'], 'regions': regions, 'cities': cities}
    (target / 'index.json').write_text(json.dumps(catalogue, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    (target / 'SOURCE.txt').write_text(
        'Source: Philippine Statistics Authority (PSA), Philippine Standard Geographic Code, 30 June 2026.\n'
        'https://psa.gov.ph/classification/psgc\n'
        'JSON transcription: https://github.com/Tenasia/ph-psgc/tree/2026-Q2\n'
        'Pinned source commit: 3d7528b6625e4e7990ac1b96d89505a6bab157ec\n'
        'PSA requires source attribution. Only geographic codes and names are included; no map points.\n',
        encoding='utf-8')
    print(f'Built {len(regions)} regions and {len(cities)} cities/municipalities.')


if __name__ == '__main__':
    build(Path(sys.argv[1]).resolve())
