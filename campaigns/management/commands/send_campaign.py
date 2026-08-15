from django.core.management.base import BaseCommand, CommandError

from campaigns.mailer import run_campaign
from campaigns.models import Campaign


class Command(BaseCommand):
    help = "Send a campaign in this terminal (safer for 3000 emails than the web button)."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id", type=int)

    def handle(self, *args, **options):
        pk = options["campaign_id"]
        if not Campaign.objects.filter(pk=pk).exists():
            raise CommandError(f"Campaign {pk} not found")
        self.stdout.write(f"Sending campaign {pk}... keep this window open.")
        run_campaign(pk)
        campaign = Campaign.objects.get(pk=pk)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. status={campaign.status} sent={campaign.sent_count} failed={campaign.failed_count} skipped={campaign.skipped_count}"
            )
        )
