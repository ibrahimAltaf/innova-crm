from campaigns.catalog import DEFAULT_TEMPLATES
from campaigns.models import EmailTemplate

CUSTOM_HTML_SLUG = "custom-html"

CUSTOM_HTML_BODY = """<!DOCTYPE html>
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
            <td style="padding:16px 32px 8px;">
              <h1 style="margin:0;font-size:22px;line-height:28px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 24px;font-size:15px;line-height:24px;color:#334155;">{{body}}</td>
          </tr>
          <tr>
            <td style="padding:0 32px 24px;">{{cta_block}}</td>
          </tr>
          <tr>
            <td style="padding:16px 32px 28px;background:#f8fafc;border-top:1px solid #e5e7eb;font-size:12px;line-height:18px;color:#64748b;text-align:center;">
              {{company_name}} · {{company_address}}<br>
              <a href="{{unsubscribe_url}}" style="color:#64748b;">Unsubscribe</a>
              &nbsp;·&nbsp;
              <a href="{{website_url}}" style="color:#64748b;">Visit website</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def ensure_templates():
    existing = set(EmailTemplate.objects.values_list("slug", flat=True))
    for item in DEFAULT_TEMPLATES:
        if item["slug"] not in existing:
            EmailTemplate.objects.create(**item)


def ensure_custom_template() -> EmailTemplate:
    ensure_templates()
    obj, _ = EmailTemplate.objects.get_or_create(
        slug=CUSTOM_HTML_SLUG,
        defaults={
            "name": "Custom HTML",
            "description": "Canvas used by Simple, HTML, and Drag-and-drop editors.",
            "preview_color": "#0f172a",
            "html_body": CUSTOM_HTML_BODY,
            "is_active": False,
        },
    )
    return obj
