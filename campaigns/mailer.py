import base64
import html as html_lib
import imaplib
import re
import ssl
import time
from email.mime.image import MIMEImage
from email.utils import formataddr, make_msgid
from pathlib import Path
from threading import Lock, Thread

from django.conf import settings as dj_settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.urls import reverse
from django.utils import timezone

from .models import AppSettings, Campaign, Recipient, Unsubscribe

_SEND_LOCK = Lock()
_RUNNING = set()


def _nl2br(text: str) -> str:
    escaped = html_lib.escape(text or "")
    return escaped.replace("\r\n", "\n").replace("\n", "<br>")


def _plain_from_html(html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</(h[1-6]|div|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _absolute_url(path_or_url: str) -> str:
    value = (path_or_url or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"{dj_settings.SITE_URL.rstrip('/')}/{value.lstrip('/')}"


LOGO_CID = "brand-logo"
_DATA_IMG_RE = re.compile(
    r"""(<img\b[^>]*?\bsrc\s*=\s*["'])(data:image/([a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+))(["'])""",
    re.I | re.S,
)
_FRAGMENT_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{subject}}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{{preheader}}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e5e7eb;">
          <tr>
            <td style="padding:20px 32px 0;">{{logo_block}}</td>
          </tr>
          <tr>
            <td style="padding:16px 32px 24px;font-size:15px;line-height:24px;color:#334155;">{{custom_html}}</td>
          </tr>
          <tr>
            <td style="padding:16px 32px 28px;background:#f8fafc;border-top:1px solid #e5e7eb;font-size:12px;line-height:18px;color:#64748b;text-align:center;">
              {{company_name}} · {{company_address}}<br>
              <a href="{{unsubscribe_url}}" style="color:#64748b;text-decoration:underline;">Unsubscribe</a>
              &nbsp;·&nbsp;
              <a href="{{website_url}}" style="color:#64748b;text-decoration:underline;">Visit website</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _apply_placeholders(html: str, values: dict) -> str:
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", value or "")
    return html


def _is_full_document(html: str) -> bool:
    return bool(re.search(r"<html[\s>]", html or "", re.I))


def _inject_unsubscribe(html: str, unsubscribe_url: str, app: AppSettings) -> str:
    if not html:
        return html
    if unsubscribe_url and unsubscribe_url in html:
        return html
    if "{{unsubscribe_url}}" in html:
        return html
    footer = (
        '<div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;'
        'font-size:12px;line-height:18px;color:#64748b;text-align:center;">'
        f"{html_lib.escape(app.company_name)} · {html_lib.escape(app.company_address)}<br>"
        f'<a href="{html_lib.escape(unsubscribe_url)}" style="color:#64748b;">Unsubscribe</a></div>'
    )
    if re.search(r"</body>", html, re.I):
        return re.sub(r"</body>", footer + "</body>", html, count=1, flags=re.I)
    return html + footer


def attach_data_uri_images(html: str, msg: EmailMultiAlternatives) -> str:
    counter = 0

    def repl(match):
        nonlocal counter
        subtype = (match.group(3) or "png").lower().split("+")[0]
        if subtype == "jpg":
            subtype = "jpeg"
        try:
            raw = base64.b64decode(re.sub(r"\s+", "", match.group(4)))
        except Exception:
            return match.group(0)
        counter += 1
        cid_name = f"paste-img-{counter}"
        image = MIMEImage(raw, _subtype=subtype)
        image.add_header("Content-ID", f"<{cid_name}>")
        image.add_header("Content-Disposition", "inline", filename=f"{cid_name}.{subtype}")
        msg.attach(image)
        msg.mixed_subtype = "related"
        return f"{match.group(1)}cid:{cid_name}{match.group(5)}"

    return _DATA_IMG_RE.sub(repl, html)


def _resolve_logo_path(campaign: Campaign, app: AppSettings) -> Path | None:
    for image in (getattr(campaign.template, "logo", None), getattr(app, "logo", None)):
        if not image:
            continue
        try:
            path = Path(image.path)
        except (ValueError, OSError):
            continue
        if path.is_file():
            return path
    return None


def _logo_src(campaign: Campaign, app: AppSettings, *, embed: bool) -> str:
    if embed and _resolve_logo_path(campaign, app):
        return f"cid:{LOGO_CID}"
    template = campaign.template
    if getattr(template, "logo_url", ""):
        return template.logo_url
    if getattr(template, "logo", None) and template.logo:
        return _absolute_url(template.logo.url)
    if getattr(app, "logo_url", ""):
        return app.logo_url
    if getattr(app, "logo", None) and app.logo:
        return _absolute_url(app.logo.url)
    return ""


def _logo_block(campaign: Campaign, app: AppSettings, *, embed: bool = False) -> str:
    src = _logo_src(campaign, app, embed=embed)
    if not src:
        return (
            f'<p style="margin:0;font-size:15px;font-weight:700;color:#0f172a;">'
            f"{html_lib.escape(app.company_name)}</p>"
        )
    return (
        f'<img src="{html_lib.escape(src)}" alt="{html_lib.escape(app.company_name)}" '
        'height="42" style="display:block;max-height:42px;border:0;">'
    )


def render_email_html(
    campaign: Campaign,
    recipient: Recipient,
    unsubscribe_url: str,
    app: AppSettings,
    *,
    embed_logo: bool = False,
) -> str:
    image_block = ""
    if campaign.image_url:
        image_block = (
            f'<img src="{html_lib.escape(campaign.image_url)}" alt="" width="528" '
            'style="display:block;width:100%;max-width:528px;border-radius:12px;margin:16px 0 0;border:0;">'
        )

    cta_block = ""
    if campaign.cta_text and campaign.cta_url:
        accent = html_lib.escape(getattr(app, "brand_color", None) or "#2563eb")
        cta_block = (
            f'<a href="{html_lib.escape(campaign.cta_url)}" '
            f'style="display:inline-block;background:{accent};color:#ffffff;text-decoration:none;'
            "font-weight:700;font-size:14px;padding:12px 22px;border-radius:8px;margin-top:8px;\">"
            f"{html_lib.escape(campaign.cta_text)}</a>"
        )

    custom = (campaign.html_content or "").strip()
    body_html = custom if custom else _nl2br(campaign.body)
    values = {
        "subject": campaign.subject,
        "preheader": campaign.preheader or campaign.subject,
        "heading": html_lib.escape(campaign.heading),
        "body": body_html,
        "name": html_lib.escape(recipient.name or "there"),
        "email": html_lib.escape(recipient.email),
        "company": html_lib.escape(recipient.company or ""),
        "cta_text": html_lib.escape(campaign.cta_text),
        "cta_url": html_lib.escape(campaign.cta_url),
        "image_url": html_lib.escape(campaign.image_url),
        "extra_note": html_lib.escape(campaign.extra_note),
        "company_name": html_lib.escape(app.company_name),
        "company_address": html_lib.escape(app.company_address),
        "website_url": html_lib.escape(app.website_url or dj_settings.SITE_URL),
        "unsubscribe_url": html_lib.escape(unsubscribe_url),
        "image_block": image_block,
        "cta_block": cta_block,
        "logo_block": _logo_block(campaign, app, embed=embed_logo),
        "custom_html": custom,
    }

    if custom:
        html = custom if _is_full_document(custom) else _FRAGMENT_SHELL.replace("{{custom_html}}", custom)
        html = _inject_unsubscribe(html, unsubscribe_url, app)
        return _apply_placeholders(html, values)

    html = campaign.template.html_body
    return _apply_placeholders(html, values)


def preview_sample_html(template, app: AppSettings | None = None, campaign: Campaign | None = None) -> str:
    """Render a full email for the in-app live preview (no SMTP)."""
    app = app or AppSettings.load()
    if campaign is None:
        campaign = Campaign(
            name="Preview",
            template=template,
            subject="Preview",
            preheader="Inbox preview of your branded email.",
            heading="A clear headline for your customers",
            body="This is sample copy so you can judge the layout before you send. Replace it with a short, useful message.",
            cta_text="Learn more",
            cta_url=app.website_url or "https://innovafior.online",
            extra_note="Optional note or date",
        )
    sample = None
    if campaign.pk:
        sample = campaign.recipients.first()
    recipient = sample or Recipient(
        campaign=campaign,
        email="preview@example.com",
        name="Ayesha",
        company="Client Co",
        unsubscribe_token="preview",
    )
    return render_email_html(campaign, recipient, "#", app)


def build_message(campaign: Campaign, recipient: Recipient, app: AppSettings, connection) -> EmailMultiAlternatives:
    unsub_path = reverse("campaigns:unsubscribe", args=[recipient.unsubscribe_token])
    unsubscribe_url = f"{dj_settings.SITE_URL}{unsub_path}"
    html = render_email_html(campaign, recipient, unsubscribe_url, app, embed_logo=True)
    text = _plain_from_html(html)
    text += f"\n\nUnsubscribe: {unsubscribe_url}\n{app.company_name}\n{app.company_address}\n"

    from_email = formataddr((app.from_name or dj_settings.DEFAULT_FROM_NAME, app.from_email or dj_settings.DEFAULT_FROM_EMAIL))
    reply_to = [app.reply_to] if app.reply_to else None

    msg = EmailMultiAlternatives(
        subject=campaign.subject,
        body=text,
        from_email=from_email,
        to=[recipient.email],
        reply_to=reply_to,
        connection=connection,
        headers={
            "Message-ID": make_msgid(domain=(app.from_email or "localhost").split("@")[-1]),
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
    html = attach_data_uri_images(html, msg)
    msg.attach_alternative(html, "text/html")
    logo_path = _resolve_logo_path(campaign, app)
    if logo_path:
        subtype = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif", ".webp": "webp"}.get(
            logo_path.suffix.lower(), "png"
        )
        with logo_path.open("rb") as handle:
            image = MIMEImage(handle.read(), _subtype=subtype)
        image.add_header("Content-ID", f"<{LOGO_CID}>")
        image.add_header("Content-Disposition", "inline", filename=logo_path.name)
        msg.attach(image)
        msg.mixed_subtype = "related"
    return msg


def save_copy_to_sent(app: AppSettings, raw_message: bytes) -> None:
    user = app.smtp_user or dj_settings.EMAIL_HOST_USER
    password = app.smtp_password or dj_settings.EMAIL_HOST_PASSWORD
    context = ssl.create_default_context()
    try:
        client = imaplib.IMAP4_SSL("imap.hostinger.com", 993, timeout=8, ssl_context=context)
    except TypeError:
        client = imaplib.IMAP4_SSL("imap.hostinger.com", 993, ssl_context=context)
    try:
        client.sock.settimeout(8)
        client.login(user, password)
        typ, mailboxes = client.list()
        names = []
        if typ == "OK" and mailboxes:
            for item in mailboxes:
                if not item:
                    continue
                decoded = item.decode("utf-8", errors="replace")
                if decoded.endswith('"') and '"' in decoded:
                    names.append(decoded.rsplit('"', 2)[-2])
        folder = next((n for n in names if n.lower() in {"sent", "sent items", "inbox.sent"}), None)
        folder = folder or "Sent"
        client.append(folder, "\\Seen", None, raw_message)
    finally:
        try:
            client.logout()
        except Exception:
            pass


def smtp_kwargs(app: AppSettings) -> dict:
    host = (app.smtp_host or dj_settings.EMAIL_HOST or "").strip()
    password = (app.smtp_password or dj_settings.EMAIL_HOST_PASSWORD or "").strip()
    use_ssl = app.smtp_use_ssl if app.smtp_host else dj_settings.EMAIL_USE_SSL
    use_tls = app.smtp_use_tls if app.smtp_host else dj_settings.EMAIL_USE_TLS
    if app.smtp_host:
        use_ssl = bool(app.smtp_use_ssl)
        use_tls = bool(app.smtp_use_tls)
    return {
        "host": host,
        "port": app.smtp_port or dj_settings.EMAIL_PORT,
        "username": (app.smtp_user or dj_settings.EMAIL_HOST_USER or "").strip(),
        "password": password,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "timeout": 30,
        "fail_silently": False,
    }


def send_one(campaign: Campaign, recipient: Recipient, app: AppSettings, connection) -> None:
    if Unsubscribe.objects.filter(email__iexact=recipient.email).exists():
        recipient.status = Recipient.Status.SKIPPED
        recipient.error_message = "Unsubscribed"
        recipient.save(update_fields=["status", "error_message"])
        campaign.skipped_count += 1
        campaign.save(update_fields=["skipped_count", "updated_at"])
        return

    msg = build_message(campaign, recipient, app, connection)
    msg.send()
    try:
        save_copy_to_sent(app, msg.message().as_bytes())
    except Exception:
        pass
    recipient.status = Recipient.Status.SENT
    recipient.sent_at = timezone.now()
    recipient.error_message = ""
    recipient.save(update_fields=["status", "sent_at", "error_message"])
    campaign.sent_count += 1
    campaign.save(update_fields=["sent_count", "updated_at"])


def send_test(campaign: Campaign, to_email: str) -> None:
    app = AppSettings.load()
    fake = Recipient(
        campaign=campaign,
        email=to_email,
        name="Test User",
        company="Test Co",
        unsubscribe_token="test-preview-token",
    )
    with get_connection(**smtp_kwargs(app)) as connection:
        msg = build_message(campaign, fake, app, connection)
        msg.send()
        try:
            save_copy_to_sent(app, msg.message().as_bytes())
        except Exception:
            pass


def prepare_campaign_for_send(campaign: Campaign) -> int:
    pending = campaign.recipients.filter(status=Recipient.Status.PENDING).count()
    if pending:
        return pending
    campaign.recipients.exclude(status=Recipient.Status.SKIPPED).update(
        status=Recipient.Status.PENDING,
        error_message="",
        sent_at=None,
    )
    campaign.sent_count = 0
    campaign.failed_count = 0
    campaign.skipped_count = 0
    campaign.last_error = ""
    campaign.save(update_fields=["sent_count", "failed_count", "skipped_count", "last_error", "updated_at"])
    return campaign.recipients.filter(status=Recipient.Status.PENDING).count()


def run_campaign(campaign_id: int) -> None:
    if campaign_id in _RUNNING:
        return
    with _SEND_LOCK:
        if campaign_id in _RUNNING:
            return
        _RUNNING.add(campaign_id)

    try:
        campaign = Campaign.objects.select_related("template").get(pk=campaign_id)
        app = AppSettings.load()
        campaign.status = Campaign.Status.SENDING
        campaign.started_at = campaign.started_at or timezone.now()
        campaign.last_error = ""
        campaign.save(update_fields=["status", "started_at", "last_error", "updated_at"])

        pending_ids = list(
            campaign.recipients.filter(status=Recipient.Status.PENDING).values_list("pk", flat=True)
        )
        small = len(pending_ids) <= 25
        delay = 0.35 if small else max(0.05, float(app.delay_seconds or 0.6))
        batch_every = 10_000 if small else max(1, app.batch_pause_every)
        batch_pause = 0.0 if small else max(0.0, float(app.batch_pause_seconds or 0))
        processed_in_batch = 0
        with get_connection(**smtp_kwargs(app)) as connection:
            for index, recipient_id in enumerate(pending_ids):
                campaign.refresh_from_db(fields=["status"])
                if campaign.status == Campaign.Status.PAUSED:
                    return
                recipient = Recipient.objects.get(pk=recipient_id)
                try:
                    send_one(campaign, recipient, app, connection)
                except Exception as exc:
                    recipient.status = Recipient.Status.FAILED
                    recipient.error_message = str(exc)[:800]
                    recipient.save(update_fields=["status", "error_message"])
                    campaign.failed_count += 1
                    campaign.last_error = str(exc)[:800]
                    campaign.save(update_fields=["failed_count", "last_error", "updated_at"])

                if index < len(pending_ids) - 1:
                    processed_in_batch += 1
                    time.sleep(delay)
                    if processed_in_batch >= batch_every:
                        time.sleep(batch_pause)
                        processed_in_batch = 0

        campaign.refresh_from_db()
        if campaign.status != Campaign.Status.PAUSED:
            campaign.status = Campaign.Status.COMPLETED
            campaign.finished_at = timezone.now()
            campaign.save(update_fields=["status", "finished_at", "updated_at"])
    except Exception as exc:
        Campaign.objects.filter(pk=campaign_id).update(
            status=Campaign.Status.FAILED,
            last_error=str(exc)[:800],
            finished_at=timezone.now(),
        )
    finally:
        _RUNNING.discard(campaign_id)


def start_campaign_async(campaign_id: int) -> None:
    thread = Thread(target=run_campaign, args=(campaign_id,), daemon=True)
    thread.start()
