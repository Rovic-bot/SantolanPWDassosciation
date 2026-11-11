"""Frozen synthetic input contract and dataset-wide calculation for the new version.

No member/profile fallback and no operational evidence adapter exists here. Retained
configurations and pools are immutable canonical JSON, identified by SHA-256.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json

from .math import (METHOD, CRITERIA, DEFAULTS, PRECISION, RANKING, CalculationError,
                   ahp, require_consistency, number, packed, display, proposal,
                   validate_weights, classification, ranks)

SOURCE_FILE = 'EWAF_Computation_Download/Computation_Updated_HI_SI_ES_PA_HM.docx'
SOURCE_SHA256 = 'b8b2af991278a19f2a42bce7e84100d06ae86541f691372cc715415c0002d6eb'
NORMALIZATION = 'dataset-minmax-v1'
DIRECTIONS = ('inverse', 'increasing', 'increasing', 'inverse', 'increasing')
ES = {'Full-Time Worker': 1, 'Part-Time Worker': 2, 'Seasonal Worker': 3, 'Unemployed': 4}
SOURCES = ('accepted_household_income', 'accepted_numeric_si_assessment',
           'accepted_employment_category', 'confirmed_nonvoid_actual_releases', 'accepted_household_count')
MATRIX_LABEL = 'Illustrative reconstructed matrix.'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return sha256(canonical(value).encode()).hexdigest()


def pack_math(value):
    if isinstance(value, Fraction):
        return packed(value)
    if isinstance(value, (tuple, list)):
        return [pack_math(item) for item in value]
    if isinstance(value, dict):
        return {key: pack_math(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class Configuration:
    snapshot: str

    @property
    def data(self):
        return json.loads(self.snapshot)

    @property
    def digest(self):
        return sha256(self.snapshot.encode()).hexdigest()


def configure(mode='DOCUMENT_EXAMPLE', proposed=None, *, classify=True):
    if type(classify) is not bool:
        raise CalculationError('Classification choice must be explicit.')
    if mode == 'DOCUMENT_EXAMPLE':
        if proposed is not None:
            raise CalculationError('The document example cannot accept substituted weight provenance.')
        q = (*tuple(number(value) / 100 for value in DEFAULTS), Fraction(1222, 10000))
        # This is the only reconstruction path: fixed document fixture, never slider values.
        validation = ahp(tuple(tuple(x / y for y in q) for x in q))
        require_consistency(validation)
        weights = validation['weights']
        provenance = MATRIX_LABEL
    elif mode == 'DRAFT_SENSITIVITY':
        weights = proposal(proposed)
        validation = None
        provenance = 'Manually proposed percentages; not AHP-derived; no operational authorization.'
        proposed = {code: display(weights[i] * 100) for i, code in enumerate(CRITERIA[:4])}
    else:
        raise CalculationError('Only the document demonstration and draft sensitivity modes are available.')
    return Configuration(canonical({'method': METHOD, 'mode': mode, 'criteria': list(CRITERIA),
        'normalization': NORMALIZATION, 'directions': list(DIRECTIONS), 'weights': pack_math(weights),
        'weight_provenance': provenance, 'ahp': pack_math(validation), 'proposal': proposed,
        'classification': 'demonstration-bands-v1' if classify else None,
        'ranking': RANKING, 'precision': PRECISION, 'source': SOURCE_FILE,
        'source_sha256': SOURCE_SHA256, 'official': False}))


def check_configuration(config):
    data = config.data
    expected = configure(data.get('mode'), data.get('proposal'), classify=data.get('classification') is not None)
    if data != expected.data:
        raise CalculationError('Configuration or weight provenance mismatch. Create a new draft.')
    return data


@dataclass(frozen=True)
class FrozenPool:
    snapshot: str

    @property
    def data(self):
        return json.loads(self.snapshot)

    @property
    def digest(self):
        return sha256(self.snapshot.encode()).hexdigest()


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError) as error:
        raise CalculationError('The frozen assessment cutoff requires an explicit timezone.') from error


def freeze_pool(*, program, version, cutoff, expected_ids, applicants, unresolved_ids=()):
    """Validate the complete eligible inventory, retaining every input's provenance.

    This adapter is explicitly synthetic. Official capture must obtain the inventory
    and accepted inputs from authorized services, which are not yet integrated.
    """
    if not isinstance(program, str) or not program.strip() or type(version) is not int or version < 1:
        raise CalculationError('A frozen pool requires a program/context and positive input version.')
    at = timestamp(cutoff)
    if unresolved_ids:
        raise CalculationError('Unresolved in-scope applications block the complete pool.')
    if not applicants:
        raise CalculationError('The eligible evaluation pool is empty.')
    if len(applicants) > 2000:
        raise CalculationError('The engineering pool limit is 2,000 applicants.')
    ids = [row.get('id') for row in applicants]
    if any(not isinstance(key, str) or not key.strip() or len(key) > 100 for key in ids):
        raise CalculationError('Every applicant needs a unique frozen input identifier.')
    if len(set(ids)) != len(ids) or len(set(expected_ids)) != len(expected_ids) or set(ids) != set(expected_ids):
        raise CalculationError('The complete frozen eligible inventory must match the input pool exactly.')
    rows = []
    for row in applicants:
        if row.get('eligibility') != 'ACCEPTED_ELIGIBLE' or set(row.get('inputs', {})) != set(CRITERIA):
            raise CalculationError(f'{row["id"]}: accepted eligibility and all five inputs are required.')
        inputs = {}
        for code, source in zip(CRITERIA, SOURCES):
            item = row['inputs'][code]
            if not isinstance(item, dict) or item.get('state') != 'ACCEPTED' or item.get('disputed') is not False or item.get('stale') is not False:
                raise CalculationError(f'{row["id"]}/{code}: missing, disputed or stale accepted evidence blocks calculation.')
            if (item.get('source') != source or not isinstance(item.get('evidence_id'), str)
                    or not item['evidence_id'].strip() or type(item.get('evidence_version')) is not int
                    or item['evidence_version'] < 1 or not item.get('period')):
                raise CalculationError(f'{row["id"]}/{code}: accepted source, evidence version and assessment period are required.')
            if timestamp(item.get('accepted_at')) > at or item.get('valid_until') and timestamp(item['valid_until']) < at:
                raise CalculationError(f'{row["id"]}/{code}: evidence is outside the frozen assessment cutoff.')
            raw = item.get('value')
            if code == 'ES':
                if not isinstance(raw, str) or raw not in ES:
                    raise CalculationError('ES: unlisted or unresolved employment category; no encoding is assumed.')
                encoded = Fraction(ES[raw])
            else:
                encoded = number(raw)
                if code in ('HI', 'PA', 'HM') and encoded < 0 or code in ('PA', 'HM') and encoded.denominator != 1:
                    raise CalculationError(f'{code}: expected a nonnegative income/count, with whole counts for PA and HM.')
            raw_text = format(raw, 'f') if isinstance(raw, Decimal) else str(raw)
            inputs[code] = {**item, 'value': raw_text, 'encoded': str(encoded)}
        rows.append({'id': row['id'], 'eligibility': row['eligibility'], 'inputs': inputs})
    return FrozenPool(canonical({'synthetic': True, 'program': program, 'version': version,
        'cutoff': cutoff, 'expected_ids': list(expected_ids), 'applicants': rows, 'unresolved_ids': []}))


def check_pool(pool):
    data = pool.data
    if data.get('synthetic') is not True:
        raise CalculationError('The accepted-evidence handoff for official runs is not implemented.')
    expected = freeze_pool(**{key: data[key] for key in ('program', 'version', 'cutoff', 'expected_ids', 'applicants', 'unresolved_ids')})
    if data != expected.data:
        raise CalculationError('Frozen input or encoding mismatch. Retain a new pool version.')
    return data


def calculate(pool, config, *, capacity=None):
    config_data, pool_data = check_configuration(config), check_pool(pool)
    weights = tuple(Fraction(item['exact']) for item in config_data['weights'])
    validate_weights(weights, positive=config_data['mode'] == 'DOCUMENT_EXAMPLE')
    applicants = pool_data['applicants']
    values = [tuple(Fraction(row['inputs'][code]['encoded']) for code in CRITERIA) for row in applicants]
    lower = tuple(min(row[j] for row in values) for j in range(5))
    upper = tuple(max(row[j] for row in values) for j in range(5))
    constant = [code for code, lo, hi in zip(CRITERIA, lower, upper) if lo == hi]
    if constant:
        raise CalculationError('Constant column (U == L): ' + ', '.join(constant) + '. Calculation stopped; an explicit approved rule is required.')
    calculated, scores = [], []
    for applicant, row in zip(applicants, values):
        traces = []
        for j, code in enumerate(CRITERIA):
            normalized = ((upper[j] - row[j]) if DIRECTIONS[j] == 'inverse' else (row[j] - lower[j])) / (upper[j] - lower[j])
            contribution = normalized * weights[j]
            traces.append({'criterion': code, 'input': applicant['inputs'][code],
                'encoded': packed(row[j]), 'lower': packed(lower[j]), 'upper': packed(upper[j]),
                'direction': DIRECTIONS[j], 'normalized': packed(normalized), 'weight': packed(weights[j]),
                'contribution_0_1': packed(contribution), 'contribution_points': packed(100 * contribution)})
        score = sum(Fraction(trace['contribution_0_1']['exact']) for trace in traces)
        scores.append(score * 100)
        calculated.append({'applicant': applicant['id'], 'traces': traces, 'score_0_1': packed(score),
            'score_0_100': packed(score * 100), 'display_score': display(score * 100),
            'classification': classification(score * 100) if config_data['classification'] else None,
            'human_decision': 'Not recorded — synthetic demonstration only'})
    ranking = ranks(scores, capacity)
    for index, row in enumerate(calculated):
        row.update(ranking[index])
    calculated.sort(key=lambda row: row['rank'])
    return {'method': METHOD, 'mode': config_data['mode'], 'synthetic': True, 'official': False,
        'criteria': list(CRITERIA), 'configuration_digest': config.digest, 'pool_digest': pool.digest,
        'normalization': NORMALIZATION, 'directions': list(DIRECTIONS),
        'bounds': [{'criterion': code, 'lower': packed(lo), 'upper': packed(hi)} for code, lo, hi in zip(CRITERIA, lower, upper)],
        'precision': PRECISION, 'ranking': RANKING, 'capacity_example': capacity,
        'capacity_boundary_tie': any(row['capacity_boundary_tie'] for row in calculated), 'applicants': calculated}
