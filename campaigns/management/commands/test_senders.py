from email.utils import formataddr, make_msgid

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError

from campaigns.models import AppSettings, SenderAccount, SendLog
from campaigns.services.credentials import redact_smtp_text, sender_password


class Command(BaseCommand):
    help = "Send one SMTP test from each active mailbox to a single address."

    def add_arguments(self, parser):
        parser.add_argument("to_email")

    def handle(self, *args, **options):
        to_email = (options["to_email"] or "").strip().lower()
        if "@" not in to_email:
            raise CommandError("Enter a valid destination email")
        app = AppSettings.load()
        senders = list(SenderAccount.objects.filter(is_active=True).order_by("email"))
        if not senders:
            raise CommandError("No active sender mailboxes")
        ok = 0
        for sender in senders:
            if not sender_password(sender):
                self.stderr.write(self.style.ERROR(f"FAIL {sender.email} · missing password"))
                continue
            try:
                with get_connection(**sender.smtp_kwargs()) as connection:
                    msg = EmailMultiAlternatives(
                        subject=f"SMTP test from {sender.email}",
                        body=(
                            f"This is a mailbox check from {sender.email}.\n"
                            f"If you received this, Hostinger SMTP for this account is working.\n"
                        ),
                        from_email=formataddr((app.from_name or "Mailbox test", sender.email)),
                        to=[to_email],
                        reply_to=[app.reply_to or sender.email],
                        connection=connection,
                        headers={"Message-ID": make_msgid(domain=sender.email.split("@")[-1])},
                    )
                    msg.send()
                SendLog.objects.create(email=to_email, kind=SendLog.Kind.TEST)
                sender.last_smtp_error = ""
                sender.failure_count = 0
                sender.save(update_fields=["last_smtp_error", "failure_count", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"OK   {sender.email}"))
                ok += 1
            except Exception as exc:
                safe = redact_smtp_text(str(exc))
                sender.last_smtp_error = safe[:400]
                sender.save(update_fields=["last_smtp_error", "updated_at"])
                self.stderr.write(self.style.ERROR(f"FAIL {sender.email} · {safe}"))
        self.stdout.write(f"Done. sent={ok} failed={len(senders) - ok} to={to_email}")
