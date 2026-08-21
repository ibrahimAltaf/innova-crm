from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Activity, AppSettings, Campaign, Contact, EmailTemplate, Lead, Recipient, SendLog, Unsubscribe


def send_quota(app: AppSettings | None = None) -> dict:
    """Track today's CRM sends vs configured daily limit (Hostinger has no public remaining-quota API)."""
    app = app or AppSettings.load()
    today = timezone.localdate()
    start = timezone.make_aware(datetime.combine(today, time.min))
    sent_today = SendLog.objects.filter(created_at__gte=start).count()
    limit = max(1, int(app.daily_send_limit or 3000))
    remaining = max(0, limit - sent_today)
    percent = min(100, int((sent_today / limit) * 100))
    return {
        "sent_today": sent_today,
        "limit": limit,
        "remaining": remaining,
        "percent": percent,
        "exhausted": remaining <= 0,
        "warning": remaining <= max(20, int(limit * 0.1)),
    }


def dashboard_payload():
    today = timezone.localdate()
    open_q = ~Q(status__in=[Lead.Status.WON, Lead.Status.LOST])
    pipeline_value = Lead.objects.filter(open_q).aggregate(total=Sum("value"))["total"] or Decimal("0")
    won_value = Lead.objects.filter(status=Lead.Status.WON).aggregate(total=Sum("value"))["total"] or Decimal("0")
    closed = Lead.objects.filter(status__in=[Lead.Status.WON, Lead.Status.LOST]).count()
    won = Lead.objects.filter(status=Lead.Status.WON).count()
    win_rate = int((won / closed) * 100) if closed else 0
    emails_sent = Recipient.objects.filter(status=Recipient.Status.SENT).count()
    emails_failed = Recipient.objects.filter(status=Recipient.Status.FAILED).count()
    attempted = emails_sent + emails_failed

    funnel = []
    for key, label in Lead.Status.choices:
        qs = Lead.objects.filter(status=key)
        funnel.append(
            {
                "key": key,
                "label": label,
                "count": qs.count(),
                "value": float(qs.aggregate(total=Sum("value"))["total"] or 0),
            }
        )

    sources = []
    for row in Lead.objects.values("source").annotate(n=Count("id")).order_by("-n")[:8]:
        label = (row["source"] or "unknown").strip() or "unknown"
        sources.append({"label": label, "count": row["n"]})

    start = timezone.now() - timedelta(days=13)
    sent_map = {
        row["day"]: row["n"]
        for row in SendLog.objects.filter(created_at__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
    }
    if not sent_map:
        sent_map = {
            row["day"]: row["n"]
            for row in Recipient.objects.filter(status=Recipient.Status.SENT, sent_at__gte=start)
            .annotate(day=TruncDate("sent_at"))
            .values("day")
            .annotate(n=Count("id"))
        }
    email_trend = []
    for offset in range(13, -1, -1):
        day = (timezone.now() - timedelta(days=offset)).date()
        email_trend.append({"day": day.strftime("%b %d"), "count": sent_map.get(day, 0)})

    due = list(
        Lead.objects.filter(next_follow_up__isnull=False, next_follow_up__lte=today)
        .exclude(status__in=[Lead.Status.WON, Lead.Status.LOST])
        .order_by("next_follow_up")[:8]
    )
    activities = list(Activity.objects.select_related("lead")[:10])
    campaigns = list(Campaign.objects.select_related("template")[:8])

    stats = {
        "leads": Lead.objects.count(),
        "contacts": Contact.objects.count(),
        "pipeline": pipeline_value,
        "won_value": won_value,
        "win_rate": win_rate,
        "sent": emails_sent,
        "failed": emails_failed,
        "delivery_rate": int((emails_sent / attempted) * 100) if attempted else 0,
        "open": Lead.objects.filter(open_q).count(),
        "unsubscribed": Unsubscribe.objects.count(),
        "campaigns": Campaign.objects.count(),
        "delivered": Recipient.objects.filter(status=Recipient.Status.SENT).count(),
        "pending": Recipient.objects.filter(status=Recipient.Status.PENDING).count(),
    }
    return {
        "stats": stats,
        "quota": send_quota(),
        "funnel": funnel,
        "sources": sources,
        "email_trend": email_trend,
        "due": due,
        "activities": activities,
        "campaigns": campaigns,
    }
