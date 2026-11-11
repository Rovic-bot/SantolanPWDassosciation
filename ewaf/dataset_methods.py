"""Explicit dataset signatures; criterion count never identifies a method."""
from django.core.exceptions import ValidationError

HOUSEHOLD = 'ewaf-hi-si-es-pa-hm-dataset-v1'
SES = 'ewaf-ses-es-pa-hm-dataset-v1'
COMPOSITE = 'ewaf-ses-4ps-es-pa-hm-dataset-v1'
SES_METHODS = (SES, COMPOSITE)
SES_CRITERIA = ('SES', 'ES', 'PA', 'HM')
SES_SOURCE = 'accepted_ses_household_vault_v1'
COMPOSITE_SOURCE = 'accepted_ses_household_4ps_vault_v1'
SES_DESCRIPTION = ('SES is an income-based proxy: accepted average household monthly income in PHP. '
    '4Ps information and Certificates of Indigency support verification; they do not add points or override accepted income.')
SIGNATURES = {HOUSEHOLD: ('HI', 'SI', 'ES', 'PA', 'HM'), SES: SES_CRITERIA}
SIGNATURES[COMPOSITE] = SES_CRITERIA
LABELS = {HOUSEHOLD: 'HI / SI / ES / PA / HM', SES: 'SES / ES / PA / HM — income-based SES'}
LABELS[COMPOSITE] = 'SES / ES / PA / HM — income-based SES with a verified 4Ps adjustment'
COMPOSITE_DESCRIPTION = ('Income-based SES with a verified 4Ps adjustment. '
    'SES = income need × (0.90 + 0.10 × P), where P is 1 for Verified Yes and 0 for Verified No. '
    'Unresolved household participation blocks acceptance. Indigency certificates and document quantity add no bonus.')


def method_of(policy):
    return policy.get('method', HOUSEHOLD)


def criteria(policy):
    method = method_of(policy) if isinstance(policy, dict) else policy
    if method not in SIGNATURES:
        raise ValidationError('Unsupported dataset method; select its exact criterion signature.')
    return SIGNATURES[method]


def directions(policy):
    return tuple('inverse' if code in ('SES', 'HI', 'PA') else 'increasing' for code in criteria(policy))


def is_ses(policy):
    return isinstance(policy, dict) and policy.get('method') in SES_METHODS


def is_composite(policy):
    return isinstance(policy, dict) and policy.get('method') == COMPOSITE


def ses_description(policy):
    method = method_of(policy) if isinstance(policy, dict) else policy
    return COMPOSITE_DESCRIPTION if method == COMPOSITE else SES_DESCRIPTION


def compatible_weight_methods(method):
    # Reuse of an income-only SES vector needs explicit new policy approval.
    # This never adopts its old scoring formula or relabels a different signature.
    return (COMPOSITE, SES) if method == COMPOSITE else (method,)


def is_dataset(policy):
    return isinstance(policy, dict) and policy.get('method') in SIGNATURES
