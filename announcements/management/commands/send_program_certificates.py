from django.core.management.base import BaseCommand, CommandError

from announcements.certificate_delivery import deliver_pending, REASONS
from announcements.certificate_mail import setup_problem


class Command(BaseCommand):
    help = 'Deliver queued selection certificates, including jobs retained after a restart.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        if setup_problem():
            raise CommandError(REASONS[setup_problem()])
        if options['limit'] < 1:
            raise CommandError('The limit must be positive.')
        count = deliver_pending(limit=options['limit'])
        self.stdout.write(f'Processed {count} queued certificate emails.')
