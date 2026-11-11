from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from events.annual_calendar import publish_annual_calendar


class Command(BaseCommand):
    help = 'Publish the approved twelve-month annual calendar once; preserve existing calendar edits and publication states.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Administrator authorizing calendar publication.')
        parser.add_argument('--notes', required=True, help='Recorded publication reason.')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
            created, retained = publish_annual_calendar(user=user, notes=options['notes'])
        except (get_user_model().DoesNotExist, PermissionDenied, ValidationError, IntegrityError) as error:
            raise CommandError('Calendar installation failed without partial publication: ' + str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Published {len(created)} annual observances; retained {len(retained)} existing cards.'))
