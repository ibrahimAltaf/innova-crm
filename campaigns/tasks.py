from celery import shared_task
from django.conf import settings
from django.utils import timezone

from campaigns.models import EmailJob
from campaigns.services.email_sender import process_due_jobs


@shared_task(ignore_result=True)
def process_email_queue():
    """Spread across every send-ready mailbox, then reschedule. Avoids one-mailbox bursts."""
    processed = process_due_jobs()
    due = EmailJob.objects.filter(
        status__in={EmailJob.Status.QUEUED, EmailJob.Status.DEFERRED, EmailJob.Status.RESERVED},
        next_attempt_at__lte=timezone.now(),
    ).exists()
    if due and not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        interval = float(getattr(settings, "MAIL_SEND_INTERVAL_SECONDS", 8) or 8)
        process_email_queue.apply_async(countdown=max(1.0, interval))
    return processed


@shared_task(ignore_result=True)
def kick_email_workers():
    process_email_queue.delay()
