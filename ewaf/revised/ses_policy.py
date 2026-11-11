"""New income-based SES policy content; historical proposal text stays unchanged."""
from copy import deepcopy
from ewaf.dataset_methods import SES, SES_DESCRIPTION

DECISIONS = {'A': ('WEIGHT_AUTHORITY',), 'B': ('SES_INCOME_ASSESSMENT_AUTHORITY',),
    'C': ('DOCUMENT_RULE_ADOPTION', 'CONSTANT_COLUMNS', 'INCOME_SOURCE_RULES', 'EMPLOYMENT_UNLISTED',
          'EVIDENCE_ACCEPTANCE', 'HISTORY_COMPLETENESS', 'ASSESSMENT_PERIODS', 'HOUSEHOLD_DEFINITION',
          'PA_SCOPE_AND_HISTORY', 'RANKING_AND_TIES', 'COMPLETE_POOL_AND_CORRECTIONS',
          'PRECISION_AND_CLASSIFICATION', 'POLICY_AUTHORITY_AND_EFFECTIVITY')}


def specifications(base):
    result = {key: deepcopy(value) for key, value in base.items()
        if not key.startswith('si_') and key not in ('evidence_HI', 'evidence_SI')}
    result['ses_measure'] = ('B', 'SES income-based proxy', {'accepted_household_income': SES_DESCRIPTION})
    result['ses_authority'] = ('B', 'Authority and qualifications for accepting household income', None)
    result['ses_review_procedure'] = ('B', 'Income and evidence discrepancies: period review, resolution and accepted-income provenance', None)
    result['method_rules'] = ('C', 'Four-criterion document rules', {'dataset_ses_v1':
        'ES: Full-Time Worker=1; Part-Time Worker=2; Seasonal Worker=3; Unemployed=4. '
        'SES/PA=(max-x)/(max-min); ES/HM=(x-min)/(max-min). Exactly four weighted contributions times 100.'})
    result['input_domain'] = ('C', 'Accepted numerical domains', {'ses_values':
        'SES: finite nonnegative accepted average household income in PHP, without per-person or expense adjustments. '
        'ES: four supported categories. PA: nonnegative actual-release count. HM: positive whole-person count. '
        'Documents do not add points; missing or disputed evidence blocks acceptance.'})
    result['income_period'] = ('C', 'Income assessment period', {'before_close':
        'Complete calendar months immediately before the approved application-closing month'})
    result['income_months'] = ('C', 'Number of complete calendar months for accepted SES income', 'integer')
    result['evidence_SES'] = ('C', 'SES: authorized income evidence and permitted alternatives', 'documents')
    return result


def initial_content(base):
    specs = specifications(base)
    choices = {key: {'value': '', 'specified': False} for key in specs}
    for key, value in {'ses_measure': 'accepted_household_income', 'method_rules': 'dataset_ses_v1',
                       'input_domain': 'ses_values', 'constant_rule': 'block'}.items():
        choices[key] = {'value': value, 'specified': True}
    proposals = {key: next(iter(options.values())) if isinstance(options, dict) else 'Unspecified'
        for key, (_, _, options) in specs.items()}
    proposals.update(income_months='Unspecified; use the authorized complete-calendar-month period.',
        pa_months='Unspecified; use the authorized release-history window.',
        income_sources='Specify included/excluded income sources, gross/net basis and treatment of irregular amounts.',
        ses_review_procedure='Review dates, circumstances and contradictions. Accepted PHP 100,000 remains PHP 100,000; '
            '4Ps/indigency evidence adds no points. Unresolved discrepancies remain Needs Review. '
            'Absence of optional documents is not an automatic SES failure; use approved evidence alternatives.')
    return {'method': SES, 'choices': choices, 'proposals': proposals, 'evidence_catalog': {},
        'ses_definition': SES_DESCRIPTION, 'decision_groups': deepcopy(DECISIONS)}
