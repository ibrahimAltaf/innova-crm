from django.core.management.base import BaseCommand, CommandError

from campaigns.models import SenderAccount
from campaigns.services.credentials import set_sender_password


class Command(BaseCommand):
    help = "Add or update a Hostinger mailbox in the sender pool (password is encrypted at rest)."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--password", default="")
        parser.add_argument("--env-key", default="", help="Env var name that holds the password.")
        parser.add_argument("--host", default="smtp.hostinger.com")
        parser.add_argument("--port", type=int, default=465)
        parser.add_argument("--daily-limit", type=int, default=300)
        parser.add_argument("--hourly-limit", type=int, default=50)
        parser.add_argument("--interval", type=int, default=12)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        env_key = options["env_key"].strip()
        if not password and not env_key:
            raise CommandError("Pass --password or --env-key")
        sender, _ = SenderAccount.objects.update_or_create(
            email=email,
            defaults={
                "username": email,
                "smtp_host": options["host"],
                "smtp_port": options["port"],
                "smtp_use_ssl": int(options["port"]) == 465,
                "smtp_use_tls": int(options["port"]) != 465,
                "daily_limit": options["daily_limit"],
                "hourly_limit": options["hourly_limit"],
                "min_interval_seconds": options["interval"],
                "credential_env_key": env_key,
                "is_active": True,
            },
        )
        if password:
            set_sender_password(sender, password)
            sender.save(update_fields=["password_encrypted"])
        self.stdout.write(self.style.SUCCESS(f"Saved sender {sender.email}"))
