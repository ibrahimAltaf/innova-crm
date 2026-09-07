from django.db import transaction
from django.utils import timezone

from campaigns.models import Recipient, SuppressionEntry, Unsubscribe, UnsubscribeToken


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_suppressed(email: str) -> SuppressionEntry | None:
    addr = normalize_email(email)
    if not addr:
        return None
    entry = SuppressionEntry.objects.filter(email=addr).first()
    if entry:
        return entry
    if Unsubscribe.objects.filter(email=addr).exists():
        return suppress_email(addr, SuppressionEntry.Reason.UNSUBSCRIBE, source="unsubscribe-table")
    return None


@transaction.atomic
def suppress_email(email: str, reason: str, *, source: str = "", notes: str = "") -> SuppressionEntry:
    addr = normalize_email(email)
    entry, created = SuppressionEntry.objects.select_for_update().get_or_create(
        email=addr,
        defaults={"reason": reason, "source": source, "notes": notes},
    )
    if not created:
        if reason == SuppressionEntry.Reason.UNSUBSCRIBE or entry.reason == SuppressionEntry.Reason.MANUAL:
            pass
        elif reason == SuppressionEntry.Reason.COMPLAINT:
            entry.reason = reason
        elif reason == SuppressionEntry.Reason.BOUNCE and entry.reason not in {
            SuppressionEntry.Reason.UNSUBSCRIBE,
            SuppressionEntry.Reason.COMPLAINT,
            SuppressionEntry.Reason.MANUAL,
        }:
            entry.reason = reason
        if source and not entry.source:
            entry.source = source
        if notes:
            entry.notes = notes
        entry.save(update_fields=["reason", "source", "notes"])
    if reason == SuppressionEntry.Reason.UNSUBSCRIBE:
        Unsubscribe.objects.get_or_create(email=addr)
    Recipient.objects.filter(email__iexact=addr, status__in=Recipient.OPEN_STATUSES).update(
        status=Recipient.Status.SKIPPED,
        error_message=entry.get_reason_display(),
    )
    return entry


def apply_unsubscribe(recipient: Recipient, *, source: str = "one-click") -> None:
    token_row, _ = UnsubscribeToken.objects.get_or_create(
        recipient=recipient,
        defaults={"token": recipient.unsubscribe_token},
    )
    if not token_row.used_at:
        token_row.used_at = timezone.now()
        token_row.save(update_fields=["used_at"])
    suppress_email(recipient.email, SuppressionEntry.Reason.UNSUBSCRIBE, source=source)
