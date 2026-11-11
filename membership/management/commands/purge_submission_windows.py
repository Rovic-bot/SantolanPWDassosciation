from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from membership.models import SubmissionWindow


class Command(BaseCommand):
    help = 'Remove expired submission counters without deleting application history.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(seconds=settings.MEMBERSHIP_SUBMISSION_WINDOW_SECONDS)
        count, _ = SubmissionWindow.objects.filter(started_at__lte=cutoff).delete()
        self.stdout.write(f'Removed {count} expired submission counters.')
