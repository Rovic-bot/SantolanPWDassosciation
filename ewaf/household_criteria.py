"""Versioned household criteria; historical ND and income definitions stay intact."""
CRITERIA = ('HI', 'SI', 'ES', 'PA', 'HM')
LEGACY_CRITERIA = ('SI', 'ES', 'PA', 'ND')
PAIRS = tuple(f'{a}:{b}' for i, a in enumerate(CRITERIA) for b in CRITERIA[i + 1:])
ENGINE = 'ewaf-operational-household-five-1'
NAMES = {'SES': 'Socioeconomic Status (income-based proxy)', 'HI': 'Household monthly income', 'SI': 'Socioeconomic Indicator',
         'ES': 'Employment Status', 'PA': 'Previous Assistance Received',
         'HM': 'Number of Household members', 'ND': 'Number of Dependents'}
SOURCES = {'HI': 'household_monthly_income', 'SI': 'four_ps_membership',
           'ES': 'employment_status', 'PA': 'successful_releases', 'HM': 'household_member_count'}


def criteria_for(policy):
    from .dataset_methods import is_ses, SES_CRITERIA
    if is_ses(policy):
        return SES_CRITERIA
    return LEGACY_CRITERIA if set(policy.get('criteria', {})) == set(LEGACY_CRITERIA) else CRITERIA


def pairs_for(criteria):
    return tuple(f'{a}:{b}' for i, a in enumerate(criteria) for b in criteria[i + 1:])


def engine_for(policy):
    from .dataset_methods import is_dataset
    if is_dataset(policy):
        return policy['method']
    return 'ewaf-operational-four-1' if criteria_for(policy) == LEGACY_CRITERIA else ENGINE
