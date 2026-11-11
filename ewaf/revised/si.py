"""Owner-confirmed SI rubric, 2026-10-26; unresolved findings never mean No."""
from django.core.exceptions import ValidationError

METHOD = 'four_ps_indigency_v1'
LABEL = '4Ps and Certificate of Indigency: both = 5; either one = 2.5; neither = 0'
LEGACY_DEFINITIONS = {'si_occasional', 'si_recurrent', 'si_critical'}


def score(findings):
    if (not isinstance(findings, dict) or set(findings) != {'four_ps', 'indigency'}
            or any(type(value) is not bool for value in findings.values())):
        raise ValidationError('Review both 4Ps membership and the Certificate of Indigency as Yes or No. Unanswered findings are incomplete.')
    return ('0', '2.5', '5')[sum(findings.values())]


def document_rule(policy):
    return policy.get('si_rubric') == METHOD
