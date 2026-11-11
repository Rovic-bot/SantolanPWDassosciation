from django.core.management.base import BaseCommand, CommandError
from programs.binding_services import preflight


class Command(BaseCommand):
    help = 'Check explicit PDAO reconciliation readiness; never activate enforcement.'

    def handle(self, *args, **options):
        result = preflight()
        self.stdout.write(f"Published programs: {result['operating']}; unresolved: {result['unresolved']}; terms drift: {result['drift']}.")
        if not result['ready']:
            raise CommandError('Cutover refused: every operating program needs explicit reconciliation of its current terms.')
        self.stdout.write('Preflight passed. Enforcement was not changed; owner-approved operational cutover is still required.')
