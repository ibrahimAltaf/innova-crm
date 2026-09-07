import logging
import re
import time
from datetime import timedelta

from django.conf import settings
from django.core.mail import get_connection
from django.db import connection, transaction
from django.utils import timezone

from campaigns.mailer import (
    _is_permanent_bounce,
    _is_ratelimit,
    _smtp_connection_dead,
    explain_send_error,
    send_one,
)
from campaigns.models import (
    AppSettings,
    Campaign,
    EmailDeliveryAttempt,
    EmailJob,
    Recipient,
    SuppressionEntry,
)
from campaigns.services.credentials import redact_smtp_text
from campaigns.services.sender_pool import (
    allocate_sender,
    mark_sender_failure,
    mark_sender_success,
    release_reserved_capacity,
    select_sender,
    soonest_capacity_at,
    suggested_jobs_per_tick,
)
from campaigns.services.suppression import is_suppressed, suppress_email

logger = logging.getLogger(__name__)
_CODE_RE = re.compile(r"\b([45]\d\d)\b")


def _lock_kwargs() -> dict:
    if getattr(connection.features, "has_select_for_update_skip_locked", False):
        return {"skip_locked": True}
    return {}


def smtp_code_from_error(exc: Exception) -> str:
    text = redact_smtp_text(str(exc))
    match = _CODE_RE.search(text)
    return match.group(1) if match else ""


def classify_send_error(exc: Exception) -> str:
    if _is_permanent_bounce(exc):
        return EmailDeliveryAttempt.Outcome.PERMANENT
    if _is_ratelimit(exc):
        return EmailDeliveryAttempt.Outcome.TEMPORARY
    if _smtp_connection_dead(exc):
        return EmailDeliveryAttempt.Outcome.CONNECTION
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text or "connection" in text:
        return EmailDeliveryAttempt.Outcome.CONNECTION
    code = smtp_code_from_error(exc)
    if code.startswith("5"):
        if code in {"535", "530", "534"}:
            return EmailDeliveryAttempt.Outcome.CONNECTION
        return EmailDeliveryAttempt.Outcome.PERMANENT
    if code.startswith("4"):
        return EmailDeliveryAttempt.Outcome.TEMPORARY
    return EmailDeliveryAttempt.Outcome.CONNECTION


def _backoff_seconds(attempt: int) -> int:
    return min(1800, 30 * (2 ** max(0, attempt - 1)))


def _open_sender_smtp(sender, previous=None):
    if previous is not None:
        try:
            previous.close()
        except Exception:
            pass
    connection = get_connection(**sender.smtp_kwargs())
    connection.open()
    return connection


@transaction.atomic
def claim_due_job() -> EmailJob | None:
    now = timezone.now()
    stale = now - timedelta(minutes=10)
    EmailJob.objects.filter(status=EmailJob.Status.RESERVED, reserved_at__lt=stale).update(
        status=EmailJob.Status.QUEUED,
        next_attempt_at=now,
    )
    job = (
        EmailJob.objects.select_for_update(**_lock_kwargs())
        .select_related("recipient", "campaign")
        .filter(status__in={EmailJob.Status.QUEUED, EmailJob.Status.DEFERRED})
        .filter(next_attempt_at__lte=now)
        .filter(campaign__status__in={Campaign.Status.QUEUED, Campaign.Status.SENDING})
        .order_by("next_attempt_at", "id")
        .first()
    )
    if not job:
        return None
    if job.recipient.status == Recipient.Status.SENT:
        job.status = EmailJob.Status.SENT
        job.sent_at = job.recipient.sent_at or now
        job.save(update_fields=["status", "sent_at", "updated_at"])
        return None
    job.status = EmailJob.Status.RESERVED
    job.reserved_at = now
    job.save(update_fields=["status", "reserved_at", "updated_at"])
    return job


def process_due_jobs(max_jobs: int | None = None) -> int:
    if max_jobs is None:
        max_jobs = suggested_jobs_per_tick()
    processed = 0
    for _ in range(max(1, int(max_jobs))):
        if not process_one_job():
            break
        processed += 1
    return processed


def process_one_job() -> bool:
    job = claim_due_job()
    if job is None:
        return False
    try:
        result = _deliver_job(job)
    except Exception as exc:
        logger.exception("Unexpected send error for job %s: %s", job.pk, redact_smtp_text(str(exc)))
        _defer_job(job, redact_smtp_text(str(exc)), smtp_code="")
        result = "ok"
    _refresh_campaign_status(job.campaign_id)
    return result != "no_capacity"


def _deliver_job(job: EmailJob) -> None:
    job = EmailJob.objects.select_related("recipient", "campaign", "campaign__template").get(pk=job.pk)
    recipient = job.recipient
    campaign = job.campaign
    app = AppSettings.load()

    if recipient.status == Recipient.Status.SENT:
        job.status = EmailJob.Status.SENT
        job.sent_at = recipient.sent_at or timezone.now()
        job.save(update_fields=["status", "sent_at", "updated_at"])
        return

    suppressed = is_suppressed(recipient.email)
    if suppressed:
        _mark_suppressed(job, recipient, campaign, suppressed.get_reason_display())
        return

    sender = select_sender()
    if sender is None:
        job.status = EmailJob.Status.QUEUED
        job.sender = None
        job.next_attempt_at = soonest_capacity_at()
        job.last_error = "No mailbox has remaining hourly/daily capacity"
        job.save(update_fields=["status", "sender", "next_attempt_at", "last_error", "updated_at"])
        recipient.status = Recipient.Status.QUEUED
        recipient.save(update_fields=["status"])
        return "no_capacity"

    job.sender = sender
    job.attempt_count += 1
    job.save(update_fields=["sender", "attempt_count", "updated_at"])

    smtp = None
    sent_ok = False
    last_exc = None
    rate_tries = 0
    connect_tries = 0
    used_ids = {sender.pk}
    max_attempts = int(getattr(settings, "MAIL_MAX_ATTEMPTS", 8))

    while True:
        try:
            smtp = _open_sender_smtp(sender, smtp)
            send_one(campaign, recipient, app, smtp, sender=sender)
            sent_ok = True
            break
        except Exception as exc:
            last_exc = exc
            outcome = classify_send_error(exc)
            code = smtp_code_from_error(exc)
            title, raw = explain_send_error(exc)
            safe = redact_smtp_text(f"{title} · {raw}")
            EmailDeliveryAttempt.objects.create(
                job=job,
                sender=sender,
                outcome=outcome,
                smtp_code=code,
                smtp_response=safe,
            )
            logger.info("SMTP %s job=%s sender=%s code=%s", outcome, job.pk, sender.email, code)

            if outcome == EmailDeliveryAttempt.Outcome.PERMANENT:
                release_reserved_capacity(sender)
                suppress_email(
                    recipient.email,
                    SuppressionEntry.Reason.BOUNCE,
                    source=f"campaign:{campaign.pk}",
                    notes=safe,
                )
                _mark_bounced(job, recipient, campaign, title, raw, code, sender)
                return

            if outcome == EmailDeliveryAttempt.Outcome.TEMPORARY:
                if rate_tries < 6:
                    rate_tries += 1
                    time.sleep(min(25 * rate_tries, 60))
                    nxt = select_sender(exclude_ids=used_ids)
                    if nxt:
                        sender = nxt
                        used_ids.add(nxt.pk)
                        job.sender = sender
                        job.save(update_fields=["sender", "updated_at"])
                    continue
                mark_sender_failure(sender, safe, cooldown=True)
                _defer_job(job, safe, code, recipient=recipient)
                return

            mark_sender_failure(sender, safe, cooldown=connect_tries >= 1 or code in {"535", "530"})
            if _smtp_connection_dead(exc) and connect_tries < 1:
                connect_tries += 1
                continue
            release_reserved_capacity(sender)
            if job.attempt_count >= max_attempts:
                _mark_failed(job, recipient, campaign, title, raw, code, sender)
                return
            _defer_job(job, safe, code, recipient=recipient)
            return

    if smtp is not None:
        try:
            smtp.close()
        except Exception:
            pass

    if sent_ok:
        mark_sender_success(sender)
        now = timezone.now()
        job.status = EmailJob.Status.SENT
        job.sent_at = now
        job.last_error = ""
        job.smtp_code = "250"
        job.save(update_fields=["status", "sent_at", "last_error", "smtp_code", "updated_at"])
        EmailDeliveryAttempt.objects.create(
            job=job, sender=sender, outcome=EmailDeliveryAttempt.Outcome.SENT, smtp_code="250", smtp_response="accepted"
        )
        return

    if last_exc is not None:
        title, raw = explain_send_error(last_exc)
        _mark_failed(job, recipient, campaign, title, raw, smtp_code_from_error(last_exc), sender)


def _mark_suppressed(job, recipient, campaign, reason: str) -> None:
    job.status = EmailJob.Status.SUPPRESSED
    job.last_error = reason
    job.save(update_fields=["status", "last_error", "updated_at"])
    if recipient.status != Recipient.Status.SKIPPED:
        recipient.status = Recipient.Status.SKIPPED
        recipient.error_message = reason
        recipient.save(update_fields=["status", "error_message"])
        campaign.skipped_count += 1
        campaign.save(update_fields=["skipped_count", "updated_at"])
    EmailDeliveryAttempt.objects.create(
        job=job, outcome=EmailDeliveryAttempt.Outcome.SUPPRESSED, smtp_response=reason
    )


def _mark_bounced(job, recipient, campaign, title, raw, code, sender) -> None:
    extra = dict(recipient.extra or {})
    extra["smtp_error"] = redact_smtp_text(raw)
    extra["fail_code"] = "mailbox_missing"
    recipient.status = Recipient.Status.BOUNCED
    recipient.error_message = title
    recipient.extra = extra
    recipient.save(update_fields=["status", "error_message", "extra"])
    job.status = EmailJob.Status.BOUNCED
    job.smtp_code = code
    job.last_error = redact_smtp_text(f"{title} · {raw}")
    job.sender = sender
    job.save(update_fields=["status", "smtp_code", "last_error", "sender", "updated_at"])
    campaign.failed_count += 1
    campaign.last_error = job.last_error[:800]
    campaign.save(update_fields=["failed_count", "last_error", "updated_at"])


def _mark_failed(job, recipient, campaign, title, raw, code, sender) -> None:
    extra = dict(recipient.extra or {})
    extra["smtp_error"] = redact_smtp_text(raw)
    extra["fail_code"] = "send_failed"
    recipient.status = Recipient.Status.FAILED
    recipient.error_message = title
    recipient.extra = extra
    recipient.save(update_fields=["status", "error_message", "extra"])
    job.status = EmailJob.Status.FAILED
    job.smtp_code = code
    job.last_error = redact_smtp_text(f"{title} · {raw}")
    job.sender = sender
    job.save(update_fields=["status", "smtp_code", "last_error", "sender", "updated_at"])
    campaign.failed_count += 1
    campaign.last_error = job.last_error[:800]
    campaign.save(update_fields=["failed_count", "last_error", "updated_at"])


def _defer_job(job, message, smtp_code, recipient=None) -> None:
    delay = _backoff_seconds(job.attempt_count)
    job.status = EmailJob.Status.DEFERRED
    job.next_attempt_at = timezone.now() + timedelta(seconds=delay)
    job.last_error = message[:400]
    job.smtp_code = smtp_code
    job.save(update_fields=["status", "next_attempt_at", "last_error", "smtp_code", "updated_at"])
    if recipient is not None:
        recipient.status = Recipient.Status.DEFERRED
        recipient.error_message = message[:400]
        recipient.save(update_fields=["status", "error_message"])


def _refresh_campaign_status(campaign_id: int) -> None:
    campaign = Campaign.objects.get(pk=campaign_id)
    if campaign.status == Campaign.Status.PAUSED:
        return
    open_left = campaign.recipients.filter(status__in=Recipient.OPEN_STATUSES).exists()
    jobs_left = campaign.email_jobs.filter(
        status__in={EmailJob.Status.QUEUED, EmailJob.Status.RESERVED, EmailJob.Status.DEFERRED}
    ).exists()
    if open_left or jobs_left:
        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=["status", "updated_at"])
        return
    campaign.status = Campaign.Status.COMPLETED
    campaign.finished_at = timezone.now()
    campaign.save(update_fields=["status", "finished_at", "updated_at"])
