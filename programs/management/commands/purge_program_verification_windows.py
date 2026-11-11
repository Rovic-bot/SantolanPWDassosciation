from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from programs.models import VerificationWindow


class Command(BaseCommand):
    help = 'Remove expired program verification counters without removing program history.'

    def handle(self, *args, **options):
        count, _ = VerificationWindow.objects.filter(
            started_at__lte=timezone.now() - timedelta(seconds=settings.PROGRAM_VERIFICATION_WINDOW_SECONDS)).delete()
        self.stdout.write(f'Removed {count} expired verification counters.')
