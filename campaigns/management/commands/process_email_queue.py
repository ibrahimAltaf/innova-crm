from django.core.management.base import BaseCommand

from campaigns.services.email_sender import process_due_jobs
from campaigns.models import EmailJob


class Command(BaseCommand):
    help = "Drain the email queue in this terminal (use when Celery is not running)."

    def add_arguments(self, parser):
        parser.add_argument("--max", type=int, default=0, help="Stop after N jobs (0 = until empty/blocked).")

    def handle(self, *args, **options):
        cap = int(options["max"] or 0)
        done = 0
        while True:
            got = process_due_jobs(max_jobs=1)
            if not got:
                break
            done += got
            self.stdout.write(f"Processed {done}")
            if cap and done >= cap:
                break
        waiting = EmailJob.objects.filter(status__in=["queued", "deferred"]).count()
        self.stdout.write(self.style.SUCCESS(f"Done. processed={done} still_waiting={waiting}"))
