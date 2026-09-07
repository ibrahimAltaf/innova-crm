import json
import os

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from campaigns.models import Campaign, EmailJob, EmailTemplate, Recipient, SenderAccount
from campaigns.services.credentials import set_sender_password
from campaigns.services.email_sender import process_due_jobs
from campaigns.services.queue import enqueue_campaign
from campaigns.services.sender_pool import pool_snapshot
from campaigns.utils import ensure_templates


def _api_unauthorized():
    return JsonResponse({"ok": False, "error": "Invalid or missing API token"}, status=401)


def _api_token_ok(request) -> bool:
    expected = (getattr(settings, "EMAIL_API_KEY", "") or "").strip()
    if not expected:
        return False
    auth = (request.headers.get("Authorization") or "").strip()
    header_key = (request.headers.get("X-Api-Key") or "").strip()
    bearer = ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
    supplied = bearer or header_key
    return bool(supplied) and supplied == expected


def require_email_api(view):
    @csrf_exempt
    @login_not_required
    def wrapped(request, *args, **kwargs):
        if not _api_token_ok(request):
            return _api_unauthorized()
        return view(request, *args, **kwargs)

    return wrapped


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_recipients(payload) -> list[dict]:
    rows = payload.get("to") or payload.get("recipients") or []
    if isinstance(rows, str):
        rows = [rows]
    parsed = []
    for item in rows:
        if isinstance(item, str):
            email = item.strip().lower()
            name = ""
        elif isinstance(item, dict):
            email = (item.get("email") or "").strip().lower()
            name = (item.get("name") or "").strip()
        else:
            continue
        if "@" in email:
            parsed.append({"email": email, "name": name})
    return parsed


@require_email_api
@require_GET
def api_health(request):
    snap = pool_snapshot()
    return JsonResponse(
        {
            "ok": True,
            "senders_active": snap["active"],
            "senders_ready": snap.get("ready", 0),
            "queued": EmailJob.objects.filter(status=EmailJob.Status.QUEUED).count(),
        }
    )


@require_email_api
@require_GET
def api_templates(request):
    ensure_templates()
    templates = [
        {"slug": t.slug, "name": t.name, "description": t.description}
        for t in EmailTemplate.objects.filter(is_active=True).order_by("name")
    ]
    return JsonResponse({"ok": True, "templates": templates})


@require_email_api
@require_POST
def api_send(request):
    payload = _json_body(request)
    recipients = _parse_recipients(payload)
    if not recipients:
        return JsonResponse({"ok": False, "error": "Provide to: [\"email@domain.com\"]"}, status=400)
    if len(recipients) > 50:
        return JsonResponse({"ok": False, "error": "Max 50 recipients per webhook call"}, status=400)

    ensure_templates()
    slug = (payload.get("template") or "newsletter").strip()
    template = EmailTemplate.objects.filter(slug=slug, is_active=True).first()
    if not template:
        return JsonResponse({"ok": False, "error": f"Unknown template '{slug}'"}, status=400)

    subject = (payload.get("subject") or "Update").strip()[:200]
    heading = (payload.get("heading") or subject).strip()[:200]
    body = (payload.get("body") or payload.get("html") or "").strip()
    name = (payload.get("name") or f"API {subject}")[:160]
    campaign = Campaign.objects.create(
        name=name,
        template=template,
        subject=subject,
        preheader=(payload.get("preheader") or subject)[:140],
        heading=heading,
        body=body or heading,
        cta_text=(payload.get("cta_text") or "")[:80],
        cta_url=payload.get("cta_url") or "",
        status=Campaign.Status.QUEUED,
    )
    added = 0
    for row in recipients:
        Recipient.objects.get_or_create(
            campaign=campaign,
            email=row["email"],
            defaults={"name": row["name"]},
        )
        added += 1
    queued = enqueue_campaign(campaign.pk)
    processed = process_due_jobs()
    campaign.refresh_from_db()
    return JsonResponse(
        {
            "ok": True,
            "campaign_id": campaign.pk,
            "template": template.slug,
            "queued": queued,
            "processed": processed,
            "sent": campaign.sent_count,
            "failed": campaign.failed_count,
            "pending": campaign.pending_count,
            "status": campaign.status,
        }
    )


@require_email_api
@require_http_methods(["GET", "POST"])
def api_drain(request):
    processed = process_due_jobs()
    return JsonResponse(
        {
            "ok": True,
            "processed": processed,
            "queued": EmailJob.objects.filter(status=EmailJob.Status.QUEUED).count(),
            "deferred": EmailJob.objects.filter(status=EmailJob.Status.DEFERRED).count(),
        }
    )


@require_email_api
@require_POST
def api_senders_upsert(request):
    payload = _json_body(request)
    rows = payload.get("senders") or payload.get("accounts") or []
    if not isinstance(rows, list) or not rows:
        return JsonResponse({"ok": False, "error": "Provide senders: [{email, password}]"}, status=400)
    saved = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        email = (row.get("email") or "").strip().lower()
        password = (row.get("password") or "").strip()
        if not email or "@" not in email or not password:
            continue
        sender, _ = SenderAccount.objects.update_or_create(
            email=email,
            defaults={
                "username": email,
                "smtp_host": (row.get("host") or "smtp.hostinger.com").strip(),
                "smtp_port": int(row.get("port") or 465),
                "smtp_use_ssl": True,
                "smtp_use_tls": False,
                "daily_limit": int(row.get("daily_limit") or getattr(settings, "MAIL_DEFAULT_DAILY_LIMIT", 300)),
                "hourly_limit": int(row.get("hourly_limit") or getattr(settings, "MAIL_DEFAULT_HOURLY_LIMIT", 50)),
                "min_interval_seconds": int(row.get("interval") or 12),
                "is_active": True,
            },
        )
        set_sender_password(sender, password)
        sender.save(update_fields=["password_encrypted", "updated_at"])
        saved += 1
    snap = pool_snapshot()
    return JsonResponse({"ok": True, "saved": saved, "active": snap["active"]})
