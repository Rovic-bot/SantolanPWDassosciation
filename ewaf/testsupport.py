"""Synthetic configuration for disposable tests only; never installed as business data."""
from datetime import timedelta
from django.utils import timezone
from .models import Configuration, ApplicationInput


def test_configuration():
    return Configuration.objects.create(name='Synthetic test configuration', si_source='monthly_income',
        pairwise=[[1] * 5 for _ in range(5)],
        encodings={'ES': {'Test employment description': 1}, 'PR': {'Test relevance': 1}},
        bounds={'SI': {'min': 0, 'max': 100000, 'direction': 'inverse'},
                'ES': {'min': 0, 'max': 2, 'direction': 'benefit'},
                'PA': {'min': 0, 'max': 100, 'direction': 'inverse'},
                'ND': {'min': 0, 'max': 20, 'direction': 'benefit'},
                'PR': {'min': 0, 'max': 2, 'direction': 'benefit'}},
        thresholds=[{'minimum': 0, 'label': 'Synthetic lower band'}, {'minimum': 50, 'label': 'Synthetic upper band'}])


def prepare_ranking(program, admin):
    from .services import generate_ranking
    program.registration_closes_at = timezone.now() - timedelta(minutes=1)
    program.save(update_fields=['registration_closes_at'])
    for app in program.applications.all():
        ApplicationInput.objects.get_or_create(application=app, defaults={'relevance': 'Test relevance', 'updated_by': admin})
    return generate_ranking(program.pk, user=admin, configuration=test_configuration(), version=program.version)
