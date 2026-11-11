from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import LoginWindow


class Command(BaseCommand):
    help = 'Remove expired login counters; keeps security audit history.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(seconds=settings.LOGIN_WINDOW_SECONDS)
        count, _ = LoginWindow.objects.filter(started_at__lte=cutoff).delete()
        self.stdout.write(f'Removed {count} expired login counters.')
