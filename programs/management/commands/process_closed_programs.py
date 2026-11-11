from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Retired: automatic applicant-list publication is not authorized.'

    def handle(self, *args, **options):
        raise CommandError('Automatic program-result publication is disabled. Authorized masked result publication belongs to revised stage nine.')
