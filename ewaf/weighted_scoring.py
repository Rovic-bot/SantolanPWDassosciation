"""Pure synthetic calculation and exact replay of G14 mathematical evidence."""
import json
from decimal import Decimal, DecimalException, localcontext
from .ahp_validation import validate_ahp, ENGINE as AHP_ENGINE, PROFILE as AHP_PROFILE
from .normalization import (CRITERIA, ENGINE, PROFILE, SETTINGS, NumericIssue,
                            arithmetic_context, number, decimal_text, normalize)


def replay_weights(judgments, validation):
    replay = validate_ahp(judgments)
    if (replay != validation or replay['engine'] != AHP_ENGINE or replay['profile'] != AHP_PROFILE or
            not replay['complete'] or not replay['structurally_valid'] or replay['consistency'] != 'PASSED'):
        raise NumericIssue('WEIGHT_SOURCE_INVALID')
    return replay['calculation']['weights']


def bounded_fixture(value):
    def visit(node, depth=0):
        if depth > 6 or type(node) not in (dict, list, str, int, type(None), bool, float):
            raise NumericIssue('PAYLOAD_RESOURCE_LIMIT')
        if isinstance(node, (dict, list)):
            if len(node) > 30 or isinstance(node, dict) and any(not isinstance(key, str) or len(key) > 200 for key in node):
                raise NumericIssue('PAYLOAD_RESOURCE_LIMIT')
            for item in (node.values() if isinstance(node, dict) else node):
                visit(item, depth + 1)
        elif isinstance(node, str) and len(node) > 1100 or type(node) is int and node.bit_length() > 400:
            raise NumericIssue('PAYLOAD_RESOURCE_LIMIT')
    visit(value)
    if len(json.dumps(value)) > 32768:
        raise NumericIssue('PAYLOAD_RESOURCE_LIMIT')


def calculate_values(*, criteria, inputs, definitions, judgments, validation):
    """Pure numerical kernel, with no identities, source authority or persistence."""
    result = {'engine': ENGINE, 'profile': PROFILE, 'settings': dict(SETTINGS), 'criteria': list(CRITERIA),
              'complete': False, 'traces': [], 'score_0_1': None, 'score_0_100': None,
              'weight_sum_residual': None, 'reasons': []}
    if criteria != list(CRITERIA) or not isinstance(inputs, dict) or set(inputs) != set(CRITERIA) or not isinstance(definitions, dict) or set(definitions) != set(CRITERIA):
        result['reasons'] = ['CRITERION_ORDER_INVALID']
        return result
    try:
        bounded_fixture({'inputs': inputs, 'definitions': definitions})
        weights = replay_weights(judgments, validation)
        with localcontext(arithmetic_context()):
            parsed = {key: number(weights[key], calculated=True) for key in CRITERIA}
            residual = sum(parsed.values(), Decimal(0)) - 1
            result['weight_sum_residual'] = decimal_text(residual)
            if any(w <= 0 for w in parsed.values()) or abs(residual) > Decimal(SETTINGS['weight_sum_tolerance']):
                raise NumericIssue('WEIGHT_VECTOR_INVALID')
            total = Decimal(0)
            for key in CRITERIA:
                entry, definition = inputs[key], definitions[key]
                if not isinstance(entry, dict) or not isinstance(definition, dict):
                    raise NumericIssue('INVALID_STRUCTURE')
                trace = {'criterion': key, 'weight': weights[key], 'contribution': None,
                         'source_type': entry.get('source_type'), 'unit': entry.get('unit'), 'reasons': [],
                         'encoding': definition.get('encoding'), 'category': entry.get('value') if definition.get('encoding') is not None else None}
                result['traces'].append(trace)
                if (not definition.get('source_type') or not definition.get('unit') or
                        entry.get('source_type') != definition.get('source_type') or entry.get('unit') != definition.get('unit')):
                    trace['reasons'] = ['MEASURE_OR_UNIT_MISMATCH']
                    continue
                raw = entry.get('value')
                encoding = definition.get('encoding')
                if encoding is not None:
                    if not isinstance(encoding, dict) or type(raw) is not str or raw not in encoding:
                        trace['reasons'] = ['ENCODING_UNAVAILABLE']
                        continue
                    raw = encoding[raw]
                bounds = definition.get('bounds')
                if not isinstance(bounds, dict) or bounds.get('method') != 'fixed':
                    trace['reasons'] = ['BOUNDS_PENDING']
                    continue
                normalized = normalize(raw, bounds.get('lower'), bounds.get('upper'), definition.get('direction'))
                trace.update(normalized)
                if normalized['complete']:
                    contribution = parsed[key] * number(normalized['normalized'], calculated=True)
                    trace['contribution'] = decimal_text(contribution)
                    total += contribution
            result['reasons'] = sorted({code for trace in result['traces'] for code in trace['reasons']})
            if not result['reasons']:
                result.update(score_0_1=decimal_text(total), score_0_100=decimal_text(total * 100))
                if not Decimal(0) <= total <= Decimal(1):
                    result['reasons'] = ['SCORE_RANGE_ANOMALY']
                else:
                    result['complete'] = True
    except NumericIssue as error:
        result['reasons'].append(str(error))
    except (DecimalException, KeyError, TypeError, ValueError):
        result['reasons'].append('ARITHMETIC_FAILURE')
    return result


def calculate_synthetic(**kwargs):
    """Preserved synthetic-only interface and diagnostic output contract."""
    result = calculate_values(**kwargs)
    result.update(effective_authorization=False, operational_ready=False,
                  label='DIAGNOSTIC ONLY — NOT AUTHORIZED FOR BENEFICIARY PROCESSING')
    return result
