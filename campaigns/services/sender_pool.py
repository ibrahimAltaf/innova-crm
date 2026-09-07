from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import F, Q
from django.utils import timezone

from campaigns.models import AppSettings, SenderAccount
from campaigns.services.credentials import encrypt_secret


def _lock_kwargs() -> dict:
    if getattr(connection.features, "has_select_for_update_skip_locked", False):
        return {"skip_locked": True}
    return {}


def _window(now=None):
    now = now or timezone.now()
    local = timezone.localtime(now)
    return now, local.date(), local.hour


def reset_sender_windows(sender: SenderAccount, today, hour) -> None:
    changed = []
    if sender.day_key is None:
        sender.day_key = today
        sender.hour_key = hour
        changed = ["day_key", "hour_key"]
    elif sender.day_key != today:
        sender.sent_today = 0
        sender.day_key = today
        sender.sent_this_hour = 0
        sender.hour_key = hour
        changed = ["sent_today", "day_key", "sent_this_hour", "hour_key"]
    elif sender.hour_key != hour:
        sender.sent_this_hour = 0
        sender.hour_key = hour
        changed = ["sent_this_hour", "hour_key"]
    if changed:
        sender.save(update_fields=changed + ["updated_at"])


def ensure_default_sender() -> SenderAccount | None:
    if SenderAccount.objects.exists():
        return SenderAccount.objects.filter(is_active=True).first()
    app = AppSettings.load()
    email = (app.smtp_user or app.from_email or "").strip().lower()
    if not email:
        return None
    password = (app.smtp_password or "").strip()
    return SenderAccount.objects.create(
        email=email,
        smtp_host=app.smtp_host or "smtp.hostinger.com",
        smtp_port=app.smtp_port or 465,
        username=app.smtp_user or email,
        password_encrypted=encrypt_secret(password) if password else "",
        smtp_use_tls=bool(app.smtp_use_tls),
        smtp_use_ssl=bool(app.smtp_use_ssl) or int(app.smtp_port or 465) == 465,
        daily_limit=int(getattr(settings, "MAIL_DEFAULT_DAILY_LIMIT", 300)),
        hourly_limit=int(getattr(settings, "MAIL_DEFAULT_HOURLY_LIMIT", 50)),
        min_interval_seconds=max(8, int(float(app.delay_seconds or 1) * 8)),
        is_active=True,
    )


def _within_hourly_daily(sender: SenderAccount) -> bool:
    return sender.sent_today < sender.daily_limit and sender.sent_this_hour < sender.hourly_limit


def _past_min_interval(sender: SenderAccount, now) -> bool:
    interval_s = max(0, int(sender.min_interval_seconds or 0))
    if not interval_s or not sender.last_sent_at:
        return True
    return sender.last_sent_at + timedelta(seconds=interval_s) <= now


def sender_has_capacity(sender: SenderAccount, now) -> bool:
    if not sender.is_active or sender.in_cooldown(now):
        return False
    if not _within_hourly_daily(sender):
        return False
    return _past_min_interval(sender, now)


def _fair_sort_key(sender: SenderAccount):
    """Least-used first, then longest idle, then stable id. No mailbox-name logic."""
    remaining_day = max(0, int(sender.daily_limit) - int(sender.sent_today))
    remaining_hour = max(0, int(sender.hourly_limit) - int(sender.sent_this_hour))
    return (
        sender.sent_today,
        sender.sent_this_hour,
        -remaining_hour,
        -remaining_day,
        sender.last_sent_at is not None,
        sender.last_sent_at or timezone.now(),
        sender.id,
    )


def get_available_senders(*, exclude_ids=None, require_pacing: bool = True, now=None, lock: bool = False):
    """Every active, healthy SenderAccount with remaining hourly/daily capacity.

    Future mailboxes appear automatically: this is a live query, not a named series.
    """
    ensure_default_sender()
    now, today, hour = _window(now)
    exclude_ids = list(exclude_ids or [])
    qs = SenderAccount.objects.filter(is_active=True).filter(
        Q(cooldown_until__isnull=True) | Q(cooldown_until__lte=now)
    )
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    qs = qs.order_by("id")
    if lock:
        qs = qs.select_for_update(**_lock_kwargs())
    ready = []
    for sender in qs:
        reset_sender_windows(sender, today, hour)
        sender.refresh_from_db()
        if not sender.is_active or sender.in_cooldown(now) or not _within_hourly_daily(sender):
            continue
        if require_pacing and not _past_min_interval(sender, now):
            continue
        ready.append(sender)
    ready.sort(key=_fair_sort_key)
    return ready


def suggested_jobs_per_tick() -> int:
    """One job per currently send-ready mailbox so a tick spreads across the whole pool."""
    n = len(get_available_senders(require_pacing=True))
    cap = int(getattr(settings, "MAIL_JOBS_PER_TICK", 20) or 20)
    return max(1, min(cap, n if n else 1))


def soonest_capacity_at(now=None):
    now, today, hour = _window(now)
    soonest = now + timedelta(minutes=5)
    any_ready = False
    for sender in SenderAccount.objects.filter(is_active=True):
        reset_sender_windows(sender, today, hour)
        if sender.in_cooldown(now) and sender.cooldown_until:
            soonest = min(soonest, sender.cooldown_until)
            continue
        if not _within_hourly_daily(sender):
            if sender.sent_this_hour >= sender.hourly_limit:
                next_hour = timezone.localtime(now).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                soonest = min(soonest, next_hour)
            if sender.sent_today >= sender.daily_limit:
                tomorrow = datetime.combine(today + timedelta(days=1), time.min)
                if timezone.is_naive(tomorrow):
                    tomorrow = timezone.make_aware(tomorrow)
                soonest = min(soonest, tomorrow)
            continue
        if not _past_min_interval(sender, now) and sender.last_sent_at:
            soonest = min(
                soonest,
                sender.last_sent_at + timedelta(seconds=max(0, int(sender.min_interval_seconds or 0))),
            )
            continue
        any_ready = True
        break
    return now if any_ready else soonest


@transaction.atomic
def reserve_sender_capacity(sender: SenderAccount, now=None) -> SenderAccount:
    now = now or timezone.now()
    locked = SenderAccount.objects.select_for_update().filter(pk=sender.pk).first()
    if not locked:
        raise SenderAccount.DoesNotExist
    _, today, hour = _window(now)
    reset_sender_windows(locked, today, hour)
    locked.refresh_from_db()
    locked.sent_today = F("sent_today") + 1
    locked.sent_this_hour = F("sent_this_hour") + 1
    locked.last_sent_at = now
    locked.save(update_fields=["sent_today", "sent_this_hour", "last_sent_at", "day_key", "hour_key", "updated_at"])
    locked.refresh_from_db()
    return locked


@transaction.atomic
def select_sender(*, exclude_ids=None) -> SenderAccount | None:
    """Pick the least-used healthy mailbox and reserve one send of capacity."""
    now = timezone.now()
    candidates = get_available_senders(exclude_ids=exclude_ids, require_pacing=True, now=now, lock=True)
    if not candidates:
        return None
    chosen = candidates[0]
    if not sender_has_capacity(chosen, now):
        return None
    return reserve_sender_capacity(chosen, now=now)


def allocate_sender(*, exclude_ids=None) -> SenderAccount | None:
    return select_sender(exclude_ids=exclude_ids)


@transaction.atomic
def release_reserved_capacity(sender: SenderAccount) -> None:
    locked = SenderAccount.objects.select_for_update().filter(pk=sender.pk).first()
    if not locked:
        return
    locked.sent_today = max(0, locked.sent_today - 1)
    locked.sent_this_hour = max(0, locked.sent_this_hour - 1)
    locked.save(update_fields=["sent_today", "sent_this_hour", "updated_at"])


def release_or_update_capacity(sender: SenderAccount, *, accepted: bool) -> None:
    if not accepted:
        release_reserved_capacity(sender)


def mark_sender_success(sender: SenderAccount) -> None:
    SenderAccount.objects.filter(pk=sender.pk).update(failure_count=0, last_smtp_error="", cooldown_until=None)


@transaction.atomic
def put_sender_in_cooldown(sender: SenderAccount, message: str = "") -> None:
    mark_sender_failure(sender, message, cooldown=True)


@transaction.atomic
def mark_sender_failure(sender: SenderAccount, message: str, *, cooldown: bool = False) -> None:
    now = timezone.now()
    locked = SenderAccount.objects.select_for_update().filter(pk=sender.pk).first()
    if not locked:
        return
    locked.failure_count = (locked.failure_count or 0) + 1
    locked.last_smtp_error = (message or "")[:400]
    seconds = int(getattr(settings, "MAIL_SENDER_COOLDOWN_SECONDS", 900))
    if cooldown or locked.failure_count >= 3:
        locked.cooldown_until = now + timedelta(seconds=max(60, seconds))
    locked.save(update_fields=["failure_count", "last_smtp_error", "cooldown_until", "updated_at"])


def pool_snapshot() -> dict:
    ensure_default_sender()
    now, today, hour = _window()
    rows = []
    remaining = 0
    for sender in SenderAccount.objects.all().order_by("email"):
        reset_sender_windows(sender, today, hour)
        left = sender.remaining_today() if sender.is_active else 0
        remaining += left
        rows.append(
            {
                "id": sender.pk,
                "email": sender.email,
                "is_active": sender.is_active,
                "sent_today": sender.sent_today,
                "sent_this_hour": sender.sent_this_hour,
                "daily_limit": sender.daily_limit,
                "hourly_limit": sender.hourly_limit,
                "remaining_today": sender.remaining_today(),
                "remaining_hour": sender.remaining_hour(),
                "cooldown_until": sender.cooldown_until,
                "in_cooldown": sender.in_cooldown(now),
                "failure_count": sender.failure_count,
                "last_smtp_error": sender.last_smtp_error,
                "last_sent_at": sender.last_sent_at,
            }
        )
    return {
        "senders": rows,
        "remaining_today": remaining,
        "active": SenderAccount.objects.filter(is_active=True).count(),
        "ready": len(get_available_senders(require_pacing=True, now=now)),
    }
