import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from campaigns.models import SenderAccount
from campaigns.services.credentials import set_sender_password


class Command(BaseCommand):
    help = "Load SMTP mailboxes from emailsbukl.json into the sender pool (passwords encrypted)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(Path(settings.BASE_DIR) / "emailsbukl.json"),
        )
        parser.add_argument("--daily-limit", type=int, default=300)
        parser.add_argument("--hourly-limit", type=int, default=50)
        parser.add_argument("--interval", type=int, default=12)

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError(f"Missing {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("accounts") or raw.get("senders") or []
        if not rows:
            raise CommandError("JSON has no sender rows")
        saved = 0
        for row in rows:
            email = (row.get("email") or row.get("user") or "").strip().lower()
            password = (row.get("password") or row.get("smtp_password") or "").strip()
            if not email or not password:
                continue
            sender, _ = SenderAccount.objects.update_or_create(
                email=email,
                defaults={
                    "username": email,
                    "smtp_host": (row.get("host") or "smtp.hostinger.com").strip(),
                    "smtp_port": int(row.get("port") or 465),
                    "smtp_use_ssl": True,
                    "smtp_use_tls": False,
                    "daily_limit": int(row.get("daily_limit") or options["daily_limit"]),
                    "hourly_limit": int(row.get("hourly_limit") or options["hourly_limit"]),
                    "min_interval_seconds": int(row.get("interval") or options["interval"]),
                    "credential_env_key": "",
                    "is_active": True,
                },
            )
            set_sender_password(sender, password)
            sender.save(update_fields=["password_encrypted", "updated_at"])
            self.stdout.write(f"Saved {sender.email}")
            saved += 1
        self.stdout.write(self.style.SUCCESS(f"Loaded {saved} mailboxes"))
