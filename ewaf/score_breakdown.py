"""Read-only explanations of retained operational calculation traces.

Never derive inputs from today's member profile or generate replacement scores.
Fractions preserve the stored numbers when converting contributions to points.
"""
from fractions import Fraction
from collections import Counter

from django.template.defaultfilters import floatformat

from .household_criteria import CRITERIA as DISPLAY_CRITERIA, NAMES
from .operational_services import ordered


def display(value, places=2):
    """Round the displayed number half-even, without an ambient decimal context."""
    value = Fraction(value)
    units, remainder = divmod(abs(value.numerator) * 10 ** places, value.denominator)
    if remainder * 2 > value.denominator or remainder * 2 == value.denominator and units % 2:
        units += 1
    integer, fraction = divmod(units, 10 ** places)
    sign = '-' if value < 0 else ''
    return f'{sign}{integer}.{fraction:0{places}d}'


def exact(value):
    return str(value['exact'] if isinstance(value, dict) else value)


def numeric(value):
    return Fraction(exact(value))


def criterion_rows(run, result):
    from .revised.automatic_inputs import enabled as automatic
    accepted = run.snapshot['eligible'][result['application']]['inputs']
    configuration = run.configuration
    evidence = (configuration.evidence_policy.snapshot.get('criteria', {})
                if configuration.evidence_policy_id else {})
    rows = []
    for trace in result['traces']:
        code = trace['criterion']
        captured = accepted[code]
        rule = configuration.policy['criteria'][code]
        raw = captured['value']
        encoded = exact(trace['input'] if 'input' in trace else trace['value'])
        lower = exact(trace['minimum'] if 'minimum' in trace else trace['lower'])
        if 'normalization_minimum' in trace:
            lower = exact(trace['normalization_minimum'])
        upper = exact(trace['maximum'] if 'maximum' in trace else trace['upper'])
        normalized = numeric(trace['normalized'])
        contribution = numeric(trace['contribution'])
        weight = numeric(trace['weight'])
        inverse = trace['direction'] == 'inverse'
        numerator = f'{upper} − {encoded}' if inverse else f'{encoded} − {lower}'
        labels = evidence.get(code, {}).get('categories', {})
        label = labels.get(str(raw), str(raw))
        rows.append({
            'code': code, 'name': NAMES.get(code, code), 'raw': str(raw), 'input_label': label,
            'included': True,
            'source_note': ('Monthly income under this saved configuration.'
                            if code == 'SI' and captured.get('source_type') == 'monthly_income' else ''),
            'unit': captured.get('unit', trace.get('unit', '')),
            'encoded': encoded, 'lower': lower, 'upper': upper,
            'bounds_from_pool': 'minimum' in trace and 'normalization_minimum' not in trace, 'inverse': inverse,
            'period': rule.get('observation_period', ''),
            'direction_label': 'Lower values score higher' if inverse else 'Higher values score higher',
            'formula': f'({numerator}) ÷ ({upper} − {lower})',
            'normalized': exact(trace['normalized']), 'normalized_display': display(normalized, 4),
            'normalized_percent': display(normalized * 100),
            'weight': exact(trace['weight']), 'weight_percent': display(weight * 100),
            'weight_display': display(weight, 6),
            'contribution': exact(trace['contribution']), 'points': display(contribution * 100),
            'normalized_value': normalized, 'contribution_value': contribution,
        })
        if 'ses_formula' in trace:
            rows[-1].update(name='Income-based SES with a verified 4Ps adjustment',
                source_note='Accepted household monthly income H; household 4Ps is a reviewed adjustment, not a fifth criterion.',
                direction_label='Lower income raises income need; reviewed 4Ps applies a 0.90 or 1.00 multiplier.',
                formula=f'(({numerator}) ÷ ({upper} − {lower})) × {exact(trace["multiplier"])}',
                composite_ses=True, income_need=exact(trace['income_need']),
                income_need_display=display(numeric(trace['income_need']), 4),
                participation='Verified Yes' if trace['household_four_ps'] == 1 else 'Verified No',
                multiplier=exact(trace['multiplier']), formula_version=trace['ses_formula']['version'])
            if automatic(configuration.policy):
                rows[-1].update(name='Income-based SES with household 4Ps adjustment',
                    source_note='Household monthly income and 4Ps status captured from the approved member record.',
                    participation='Recorded Yes' if trace['household_four_ps'] == 1 else 'Recorded No')
        if trace.get('constant_rule') == 'zero_contribution_v1':
            rows[-1].update(formula='Equal values: normalized value = 0; contribution = 0',
                zero_constant=True, direction_label='Equal values contribute zero under this saved policy.')
        if trace.get('constant_rule') == 'full_contribution_v1':
            rows[-1].update(formula=('Equal income: I = 1; SES = 1 × ' + exact(trace['multiplier'])
                if 'ses_formula' in trace else 'Equal values: normalized value = 1'),
                full_constant=True, direction_label='Equal values receive full normalized credit; the existing SES adjustment still applies.')
        if code == 'HM' and 'normalization_minimum' in trace:
            rows[-1].update(source_note='Baseline: 1 household member. Maximum: the largest household in this program\'s eligible scoring pool.',
                direction_label='1 household member scores 0; larger households score higher.')
            if numeric(trace['maximum']) == 1:
                rows[-1]['formula'] = 'Every household has 1 member: normalized value = 0'
    largest = max(row['contribution_value'] for row in rows)
    highest = max(row['normalized_value'] for row in rows)
    for row in rows:
        row['largest_contribution'] = largest > 0 and row['contribution_value'] == largest
        row['highest_normalized'] = highest > 0 and row['normalized_value'] == highest
    return rows


def build_breakdown(run, members):
    """Call only after the saved run passes its existing integrity replay."""
    references = {row['application']: row['reference'] for row in run.snapshot['manifest']}
    results = []
    from .dataset_methods import is_ses, SES_CRITERIA
    display_criteria = SES_CRITERIA if is_ses(run.configuration.policy) else DISPLAY_CRITERIA
    # Compare exact contributions in the whole saved pool, never a filtered page.
    frequencies = {}
    for calculation in run.calculations.values():
        for trace in calculation['traces']:
            frequencies.setdefault(trace['criterion'], Counter())[numeric(trace['contribution'])] += 1
    comparisons = {}
    for code, counts in frequencies.items():
        below, size = 0, sum(counts.values())
        comparisons[code] = {}
        for points, count in sorted(counts.items()):
            comparisons[code][points] = {'pool_higher': size - below - count,
                'pool_equal': count - 1, 'pool_lower': below}
            below += count
    for result in ordered(run):
        traces = criterion_rows(run, result)
        for trace in traces:
            trace.update(comparisons[trace['code']][trace['contribution_value']])
            trace['pool_position'] = (
                'Same points for everyone' if not trace['pool_higher'] and not trace['pool_lower'] else
                'Highest points in this pool' if not trace['pool_higher'] else
                'Lowest points in this pool' if not trace['pool_lower'] else
                'Between the highest and lowest points')
        by_code = {trace['code']: trace for trace in traces}
        display_traces = [by_code.get(code, {'code': code, 'name': NAMES[code], 'included': False})
                          for code in display_criteria]
        legacy_traces = [trace for trace in traces if trace['code'] not in display_criteria]
        missing = [trace for trace in display_traces if not trace['included']]
        displayed_points = sum((trace['contribution_value'] for trace in display_traces
                                if trace['included']), Fraction(0)) * 100
        legacy_points = sum((trace['contribution_value'] for trace in legacy_traces), Fraction(0)) * 100
        total = Fraction(result.get('score_exact', result['score_0_1']))
        leaders = [row for row in traces if row['largest_contribution']]
        best = [row for row in traces if row['highest_normalized']]
        share = (sum(row['contribution_value'] for row in leaders) / total * 100) if total else Fraction(0)
        results.append({
            'application': result['application'], 'reference': references[result['application']],
            'member_name': members.get(result['application'], 'Applicant'),
            'rank': result['comparison']['higher'] + 1,
            'higher': result['comparison']['higher'], 'tied_others': result['comparison']['equal'] - 1,
            'lower': len(run.calculations) - result['comparison']['higher'] - result['comparison']['equal'],
            'score': result.get('score_display') or str(floatformat(result['score_0_100'], 2)),
            'score_exact': result.get('score_exact', result['score_0_1']),
            'score_0_100': result['score_0_100'], 'traces': traces,
            'display_traces': display_traces, 'legacy_traces': legacy_traces,
            'missing_criterion_names': ', '.join(f"{trace['name']} ({trace['code']})" for trace in missing),
            'displayed_points': display(displayed_points), 'legacy_points': display(legacy_points),
            'legacy_codes': ', '.join(trace['code'] for trace in legacy_traces),
            'leaders': leaders, 'leader_names': ', '.join(row['code'] for row in leaders),
            'leader_points': leaders[0]['points'] if leaders else '0.00',
            'leader_share': display(share),
            'best_names': ', '.join(row['code'] for row in best),
            'best_score': best[0]['normalized_percent'] if best else '0.00',
        })
    return results


def calculation_guide(run, rows):
    """Describe the validated saved method; never infer it from criterion count."""
    from . import dataset_methods as methods
    traces = rows[0]['traces'] if rows else []
    policy = run.configuration.policy
    from .revised.automatic_inputs import enabled as automatic
    current_records = automatic(policy)
    from .revised import rolling_pool
    from .shared_calculation_rules import retained, FULL_CONSTANTS
    saved_rules = retained(run.snapshot, run.configuration)
    constant_rule = (saved_rules or policy).get('constant_rule')
    codes = [trace['code'] for trace in traces]
    method = policy.get('method', run.snapshot.get('engine', ''))
    encoding = policy.get('criteria', {}).get('ES', {}).get('encoding', {})
    if methods.is_dataset(policy):
        from .employment_scoring import encoding as employment_encoding
        encoding = employment_encoding(run.snapshot)
    return {'criteria': traces, 'codes': ', '.join(codes), 'count': len(codes),
        'method': method, 'method_label': methods.LABELS.get(method, 'Historical ' + ' / '.join(codes)),
        'pool_bounds': bool(traces) and all(trace['bounds_from_pool'] for trace in traces),
        'composite': methods.is_composite(policy), 'income_only': method == methods.SES,
        'employment_encoding': list(encoding.items()),
        'automatic_inputs': current_records,
        'rolling_pool': rolling_pool.enabled(policy),
        'ranking_window': run.snapshot.get(rolling_pool.KEY),
        'zero_constants': constant_rule == rolling_pool.ZERO_CONSTANTS,
        'full_constants': constant_rule == FULL_CONSTANTS,
        'shared_calculation_rules': saved_rules,
        'income_months': None if current_records else policy.get('income_months'), 'income_sources': policy.get('income_sources'),
        'formula_version': policy.get('ses_formula', {}).get('version')}
