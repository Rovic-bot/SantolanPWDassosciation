from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from events.models import VerificationWindow


class Command(BaseCommand):
    help = 'Remove expired event verification counters without removing event history.'

    def handle(self, *args, **options):
        count, _ = VerificationWindow.objects.filter(
            started_at__lte=timezone.now() - timedelta(seconds=settings.EVENT_VERIFICATION_WINDOW_SECONDS)).delete()
        self.stdout.write(f'Removed {count} expired verification counters.')
