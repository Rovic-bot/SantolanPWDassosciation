from django.core.management.base import BaseCommand, CommandError
from assistance.referral_models import ReferralEmail
from assistance.referral_mail import deliver_email


class Command(BaseCommand):
    help = 'Send queued referral emails. Failed or unconfirmed attempts require a staff-reviewed retry.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 500:
            raise CommandError('Use a limit from 1 to 500.')
        keys = list(ReferralEmail.objects.filter(state='queued').order_by('created_at').values_list('pk', flat=True)[:limit])
        accepted = sum(bool(deliver_email(key)) for key in keys)
        self.stdout.write(f'Processed {len(keys)} queued messages; backend accepted {accepted}. See the inbox for delivery details.')
