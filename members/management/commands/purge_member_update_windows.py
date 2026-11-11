from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from members.update_models import MemberUpdateWindow


class Command(BaseCommand):
    help = 'Remove expired member-update rate counters; retain requests, verification and audit history.'

    def handle(self, *args, **options):
        count, _ = MemberUpdateWindow.objects.filter(started_at__lte=timezone.now() - timedelta(hours=1)).delete()
        self.stdout.write(f'Removed {count} expired member-update counters.')
