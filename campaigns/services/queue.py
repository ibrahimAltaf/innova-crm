from django.db import transaction
from django.utils import timezone

from campaigns.models import Campaign, EmailJob, Recipient, UnsubscribeToken
from campaigns.services.suppression import is_suppressed


def job_key(recipient: Recipient) -> str:
    return f"c{recipient.campaign_id}:r{recipient.pk}"


def ensure_unsub_token(recipient: Recipient) -> None:
    UnsubscribeToken.objects.get_or_create(
        recipient=recipient,
        defaults={"token": recipient.unsubscribe_token},
    )


@transaction.atomic
def enqueue_campaign(campaign_id: int, limit: int | None = None) -> int:
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    qs = campaign.recipients.filter(status__in=Recipient.OPEN_STATUSES).order_by("id")
    if limit:
        qs = qs[: max(1, int(limit))]
    recipients = list(qs)
    created = 0
    now = timezone.now()
    for recipient in recipients:
        ensure_unsub_token(recipient)
        suppressed = is_suppressed(recipient.email)
        if suppressed:
            recipient.status = Recipient.Status.SKIPPED
            recipient.error_message = suppressed.get_reason_display()
            recipient.save(update_fields=["status", "error_message"])
            campaign.skipped_count += 1
            EmailJob.objects.update_or_create(
                recipient=recipient,
                defaults={
                    "campaign": campaign,
                    "idempotency_key": job_key(recipient),
                    "status": EmailJob.Status.SUPPRESSED,
                    "last_error": suppressed.get_reason_display(),
                    "next_attempt_at": now,
                },
            )
            continue
        job, was_created = EmailJob.objects.get_or_create(
            recipient=recipient,
            defaults={
                "campaign": campaign,
                "idempotency_key": job_key(recipient),
                "status": EmailJob.Status.QUEUED,
                "next_attempt_at": now,
            },
        )
        if job.status in {EmailJob.Status.SENT, EmailJob.Status.BOUNCED, EmailJob.Status.SUPPRESSED}:
            continue
        if job.status != EmailJob.Status.QUEUED:
            job.status = EmailJob.Status.QUEUED
            job.sender = None
            job.next_attempt_at = now
            job.last_error = ""
            job.save(update_fields=["status", "sender", "next_attempt_at", "last_error", "updated_at"])
        if recipient.status != Recipient.Status.QUEUED:
            recipient.status = Recipient.Status.QUEUED
            recipient.error_message = ""
            recipient.save(update_fields=["status", "error_message"])
        created += 1
        was_created = was_created  # kept for readability
    campaign.status = Campaign.Status.QUEUED
    campaign.started_at = campaign.started_at or now
    campaign.last_error = ""
    campaign.save(update_fields=["status", "started_at", "last_error", "skipped_count", "updated_at"])
    return created


def enqueue_failed_retry(campaign_id: int, limit: int | None = None) -> int:
    campaign = Campaign.objects.get(pk=campaign_id)
    qs = campaign.recipients.filter(status__in={Recipient.Status.FAILED, Recipient.Status.DEFERRED}).order_by("id")
    if limit:
        qs = qs[: max(1, int(limit))]
    count = 0
    now = timezone.now()
    for recipient in qs:
        extra = recipient.extra if isinstance(recipient.extra, dict) else {}
        if extra.get("fail_code") == "mailbox_missing":
            continue
        if is_suppressed(recipient.email):
            continue
        recipient.status = Recipient.Status.QUEUED
        recipient.error_message = ""
        recipient.save(update_fields=["status", "error_message"])
        EmailJob.objects.update_or_create(
            recipient=recipient,
            defaults={
                "campaign": campaign,
                "idempotency_key": job_key(recipient),
                "status": EmailJob.Status.QUEUED,
                "sender": None,
                "next_attempt_at": now,
                "last_error": "",
                "smtp_code": "",
            },
        )
        count += 1
    if count:
        campaign.failed_count = campaign.recipients.filter(status=Recipient.Status.FAILED).count()
        campaign.status = Campaign.Status.QUEUED
        campaign.last_error = ""
        campaign.save(update_fields=["failed_count", "status", "last_error", "updated_at"])
    return count
