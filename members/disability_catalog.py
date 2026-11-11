"""Controlled current choices; older classifications retain their original identity."""
from django.db.models import Case, IntegerField, When

NAMES = (
    'Cancer (RA 11215)',
    'Deaf or Hard of Hearing',
    'Intellectual Disability',
    'Learning Disability',
    'Mental Disability',
    'Physical Disability (Orthopedic)',
    'Psychosocial Disability',
    'Rare Disease (RA 10747)',
    'Speech and Language Impairment',
    'Visual Disability',
)


ASSOCIATION_LABELS = {
    'Physical Disability (Orthopedic)': 'Physical / Orthopedic',
    'Learning Disability': 'Learning and Behavioral',
    'Speech and Language Impairment': 'Speech',
    'Deaf or Hard of Hearing': 'Hearing',
    'Psychosocial Disability': 'Psychosocial',
    'Intellectual Disability': 'Intellectual',
    'Cancer (RA 11215)': 'Cancer (R.A. 11215)',
    'Mental Disability': 'Mental Disability',
    'Visual Disability': 'Visual Disability',
    'Rare Disease (RA 10747)': 'Rare Disease (R.A. 10747)',
}


def association_types(label):
    """Resolve an exact Association choice to its existing catalog identity."""
    from .models import DisabilityType
    names = {label: name for name, label in ASSOCIATION_LABELS.items()}
    return DisabilityType.objects.filter(name=names.get(label, label), is_active=True)


def current_types():
    from .models import DisabilityType
    return DisabilityType.objects.filter(name__in=NAMES).order_by(
        Case(*[When(name=name, then=index) for index, name in enumerate(NAMES)],
             output_field=IntegerField()))


def retained_types(ids):
    from .models import DisabilityType
    return DisabilityType.objects.filter(pk__in=ids).exclude(name__in=NAMES)
