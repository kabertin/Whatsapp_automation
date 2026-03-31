from django.core.management.base import BaseCommand
from django.utils import timezone
from escrow.models import Provider

class Command(BaseCommand):
    help = 'Deactivates providers whose subscription has expired'

    def handle(self, *args, **options):
        now = timezone.now()
        # Find active providers whose expiry date is in the past
        expired = Provider.objects.filter(is_paid=True, subscription_expiry__lt=now)

        count = expired.count()
        # Update all found records to unpaid
        expired.update(is_paid=False)

        self.stdout.write(self.style.SUCCESS(f'Successfully deactivated {count} expired providers.'))
