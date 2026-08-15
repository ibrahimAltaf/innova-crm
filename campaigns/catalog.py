"""Inbox-safe HTML email layouts (table + inline CSS). Web Bootstrap does not render in Gmail/Outlook."""

from string import Template


def _shell(inner: str, *, bg: str, accent: str) -> str:
    shell = Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{{subject}}</title>
</head>
<body style="margin:0;padding:0;background:${bg};font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{{preheader}}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${bg};padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;">
          <tr>
            <td style="padding:20px 36px 0;">{{logo_block}}</td>
          </tr>
          ${inner}
          <tr>
            <td style="padding:22px 36px 32px;background:#f8fafc;border-top:1px solid #e5e7eb;">
              <p style="margin:0 0 8px;font-size:12px;line-height:18px;color:#64748b;text-align:center;">
                You received this email because you are a customer or subscriber of <strong>{{company_name}}</strong>.
              </p>
              <p style="margin:0 0 8px;font-size:12px;line-height:18px;color:#64748b;text-align:center;">{{company_address}}</p>
              <p style="margin:0;font-size:12px;line-height:18px;color:#64748b;text-align:center;">
                <a href="{{unsubscribe_url}}" style="color:${accent};text-decoration:underline;">Unsubscribe</a>
                &nbsp;·&nbsp;
                <a href="{{website_url}}" style="color:${accent};text-decoration:underline;">Visit website</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>""")
    return shell.safe_substitute(bg=bg, accent=accent, inner=inner)


NEWSLETTER = _shell(
    """
          <tr>
            <td style="padding:28px 36px 12px;background:#0f172a;">
              <p style="margin:0;font-size:13px;letter-spacing:1.4px;text-transform:uppercase;color:#93c5fd;font-weight:700;">{{company_name}}</p>
              <h1 style="margin:10px 0 0;font-size:26px;line-height:34px;color:#ffffff;font-weight:700;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:20px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 28px;" align="left">{{cta_block}}</td>
          </tr>
    """,
    bg="#eef2ff",
    accent="#2563eb",
)

PROMO = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#6d28d9;">
                <tr>
                  <td style="padding:36px 36px 28px;text-align:center;">
                    <p style="margin:0 0 10px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#ddd6fe;">Limited offer</p>
                    <h1 style="margin:0;font-size:30px;line-height:38px;color:#ffffff;">{{heading}}</h1>
                    <p style="margin:12px 0 0;font-size:15px;color:#e9d5ff;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:24px 36px 8px;text-align:center;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;text-align:left;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#f5f3ff",
    accent="#7c3aed",
)

WELCOME = _shell(
    """
          <tr>
            <td style="padding:36px 36px 8px;text-align:center;">
              <div style="display:inline-block;background:#dcfce7;color:#166534;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:6px 12px;border-radius:999px;">Welcome</div>
              <h1 style="margin:16px 0 0;font-size:28px;line-height:36px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:20px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hello {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#ecfdf5",
    accent="#059669",
)

PRODUCT = _shell(
    """
          <tr>
            <td style="padding:28px 36px 4px;">
              <p style="margin:0;font-size:13px;color:#0ea5e9;font-weight:700;letter-spacing:1px;text-transform:uppercase;">New release</p>
              <h1 style="margin:8px 0 0;font-size:26px;line-height:34px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:20px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:18px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#f0f9ff",
    accent="#0284c7",
)

EVENT = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#111827;">
                <tr>
                  <td style="padding:32px 36px;">
                    <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#fbbf24;">You're invited</p>
                    <h1 style="margin:10px 0 0;font-size:28px;line-height:36px;color:#ffffff;">{{heading}}</h1>
                    <p style="margin:12px 0 0;font-size:15px;color:#d1d5db;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#fff7ed",
    accent="#d97706",
)

BUSINESS = _shell(
    """
          <tr>
            <td style="padding:28px 36px 0;border-bottom:3px solid #0f172a;">
              <table role="presentation" width="100%">
                <tr>
                  <td>
                    <p style="margin:0;font-size:18px;font-weight:700;color:#0f172a;">{{company_name}}</p>
                    <p style="margin:4px 0 16px;font-size:12px;color:#64748b;">Official update</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 36px 8px;">
              <h1 style="margin:0 0 16px;font-size:22px;line-height:30px;color:#0f172a;">{{heading}}</h1>
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#f1f5f9",
    accent="#0f172a",
)

THANKS = _shell(
    """
          <tr>
            <td style="padding:36px 36px 8px;text-align:center;">
              <p style="margin:0;font-size:13px;letter-spacing:1.6px;text-transform:uppercase;color:#2563eb;font-weight:700;">Thank you</p>
              <h1 style="margin:12px 0 0;font-size:28px;line-height:36px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:18px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#eff6ff",
    accent="#1d4ed8",
)

ANNOUNCEMENT = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1e3a8a;">
                <tr>
                  <td style="padding:32px 36px;">
                    <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#93c5fd;">Announcement</p>
                    <h1 style="margin:10px 0 0;font-size:26px;line-height:34px;color:#ffffff;">{{heading}}</h1>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hello {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#e0e7ff",
    accent="#1d4ed8",
)

INVOICE = _shell(
    """
          <tr>
            <td style="padding:28px 36px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <p style="margin:0;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#64748b;font-weight:700;">Invoice</p>
                    <h1 style="margin:8px 0 0;font-size:24px;line-height:32px;color:#0f172a;">{{heading}}</h1>
                  </td>
                  <td align="right" style="vertical-align:top;">
                    <p style="margin:0;font-size:12px;color:#64748b;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 36px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <p style="margin:0 0 12px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
                    <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:16px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#f8fafc",
    accent="#0f172a",
)

APPOINTMENT = _shell(
    """
          <tr>
            <td style="padding:28px 36px 8px;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#ecfeff;border-radius:12px;padding:10px 14px;font-size:12px;font-weight:700;color:#0e7490;letter-spacing:1px;text-transform:uppercase;">Appointment</td>
                </tr>
              </table>
              <h1 style="margin:16px 0 0;font-size:26px;line-height:34px;color:#0f172a;">{{heading}}</h1>
              <p style="margin:8px 0 0;font-size:15px;color:#0e7490;font-weight:700;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:20px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#ecfeff",
    accent="#0e7490",
)

REVIEW = _shell(
    """
          <tr>
            <td style="padding:36px 36px 8px;text-align:center;">
              <p style="margin:0;font-size:22px;letter-spacing:4px;color:#f59e0b;">★★★★★</p>
              <h1 style="margin:12px 0 0;font-size:26px;line-height:34px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:20px 36px 8px;text-align:center;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;text-align:left;">{{body}}</div>
              <p style="margin:16px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#fffbeb",
    accent="#d97706",
)

FOLLOWUP = _shell(
    """
          <tr>
            <td style="padding:28px 36px 0;border-left:6px solid #4f46e5;">
              <p style="margin:0;font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:#4f46e5;font-weight:700;">Follow-up</p>
              <h1 style="margin:10px 0 0;font-size:24px;line-height:32px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:20px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#eef2ff",
    accent="#4f46e5",
)

INTRO = _shell(
    """
          <tr>
            <td style="padding:32px 36px 8px;">
              <p style="margin:0;font-size:13px;color:#64748b;">A note from {{company_name}}</p>
              <h1 style="margin:8px 0 0;font-size:26px;line-height:34px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:16px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hello {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:18px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#f8fafc",
    accent="#334155",
)

FLASH = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#dc2626;">
                <tr>
                  <td style="padding:28px 36px;text-align:center;">
                    <p style="margin:0 0 8px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#fecaca;font-weight:700;">Flash sale</p>
                    <h1 style="margin:0;font-size:32px;line-height:40px;color:#ffffff;">{{heading}}</h1>
                    <p style="margin:10px 0 0;font-size:16px;color:#fee2e2;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;text-align:center;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;text-align:left;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#fef2f2",
    accent="#dc2626",
)

DIGEST = _shell(
    """
          <tr>
            <td style="padding:24px 36px 0;">
              <p style="margin:0;font-size:12px;letter-spacing:1.6px;text-transform:uppercase;color:#6366f1;font-weight:700;">Weekly digest</p>
              <h1 style="margin:8px 0 12px;font-size:26px;line-height:34px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:0 36px;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:18px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}}, here is this week's update.</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:16px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#eef2ff",
    accent="#4f46e5",
)

LUXURY = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#111827;">
                <tr>
                  <td style="padding:36px 36px 28px;text-align:center;border-bottom:1px solid #d4af37;">
                    <p style="margin:0 0 10px;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#d4af37;">Exclusive</p>
                    <h1 style="margin:0;font-size:28px;line-height:36px;color:#ffffff;font-weight:500;">{{heading}}</h1>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:24px 36px 8px;text-align:center;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
              <div style="font-size:16px;line-height:28px;color:#334155;text-align:left;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#111827",
    accent="#d4af37",
)

PROPERTY = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f766e;">
                <tr>
                  <td style="padding:32px 36px;">
                    <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#99f6e4;">Property</p>
                    <h1 style="margin:10px 0 0;font-size:26px;line-height:34px;color:#ffffff;">{{heading}}</h1>
                    <p style="margin:10px 0 0;font-size:15px;color:#ccfbf1;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#f0fdfa",
    accent="#0f766e",
)

HOSPITALITY = _shell(
    """
          <tr>
            <td style="padding:32px 36px 8px;text-align:center;background:#fff7ed;">
              <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#c2410c;font-weight:700;">Hospitality</p>
              <h1 style="margin:12px 0 0;font-size:28px;line-height:36px;color:#7c2d12;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:16px 0 0;font-size:14px;color:#9a3412;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#fff7ed",
    accent="#c2410c",
)

WEBINAR = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1d4ed8;">
                <tr>
                  <td style="padding:32px 36px;">
                    <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#bfdbfe;">Live session</p>
                    <h1 style="margin:10px 0 0;font-size:26px;line-height:34px;color:#ffffff;">{{heading}}</h1>
                    <p style="margin:10px 0 0;font-size:15px;color:#dbeafe;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#eff6ff",
    accent="#1d4ed8",
)

QUOTE = _shell(
    """
          <tr>
            <td style="padding:28px 36px 0;">
              <p style="margin:0;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#0369a1;font-weight:700;">Proposal</p>
              <h1 style="margin:8px 0 0;font-size:24px;line-height:32px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 36px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #bae6fd;border-left:6px solid #0284c7;border-radius:8px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <p style="margin:0 0 12px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
                    <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
                    <p style="margin:14px 0 0;font-size:14px;color:#0369a1;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:16px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#f0f9ff",
    accent="#0369a1",
)

MEETING = _shell(
    """
          <tr>
            <td style="padding:28px 36px 8px;">
              <p style="margin:0;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#7c3aed;font-weight:700;">Meeting notes</p>
              <h1 style="margin:10px 0 0;font-size:24px;line-height:32px;color:#0f172a;">{{heading}}</h1>
              <p style="margin:8px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:18px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#f5f3ff",
    accent="#7c3aed",
)

GREETING = _shell(
    """
          <tr>
            <td style="padding:36px 36px 8px;text-align:center;background:#fdf2f8;">
              <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#be185d;font-weight:700;">With thanks</p>
              <h1 style="margin:14px 0 0;font-size:30px;line-height:38px;color:#9d174d;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;text-align:center;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Dear {{name}},</p>
              <div style="font-size:16px;line-height:28px;color:#334155;text-align:left;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#fdf2f8",
    accent="#be185d",
)

SUPPORT = _shell(
    """
          <tr>
            <td style="padding:28px 36px 8px;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#dbeafe;color:#1e40af;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:6px 12px;border-radius:999px;">Support</td>
                </tr>
              </table>
              <h1 style="margin:16px 0 0;font-size:24px;line-height:32px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:18px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:16px 0 0;font-size:14px;color:#64748b;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#eff6ff",
    accent="#1d4ed8",
)

SEASONAL = _shell(
    """
          <tr>
            <td style="padding:0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#14532d;">
                <tr>
                  <td style="padding:36px 36px 28px;text-align:center;">
                    <p style="margin:0 0 8px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#86efac;">Seasonal</p>
                    <h1 style="margin:0;font-size:28px;line-height:36px;color:#ffffff;">{{heading}}</h1>
                    <p style="margin:10px 0 0;font-size:15px;color:#bbf7d0;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#ecfdf5",
    accent="#15803d",
)

TESTIMONIAL = _shell(
    """
          <tr>
            <td style="padding:32px 36px 8px;text-align:center;">
              <p style="margin:0;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#7c3aed;font-weight:700;">Customer story</p>
              <h1 style="margin:12px 0 0;font-size:26px;line-height:34px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:18px 36px 8px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f3ff;border-radius:12px;">
                <tr>
                  <td style="padding:20px;">
                    <p style="margin:0 0 12px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
                    <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
                    <p style="margin:14px 0 0;font-size:14px;color:#6d28d9;">{{extra_note}}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;" align="center">{{cta_block}}</td>
          </tr>
    """,
    bg="#faf5ff",
    accent="#7c3aed",
)

REMINDER = _shell(
    """
          <tr>
            <td style="padding:28px 36px 8px;">
              <p style="margin:0;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#ea580c;font-weight:700;">Friendly reminder</p>
              <h1 style="margin:10px 0 0;font-size:24px;line-height:32px;color:#0f172a;">{{heading}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0;">{{image_block}}</td>
          </tr>
          <tr>
            <td style="padding:18px 36px 8px;">
              <p style="margin:0 0 16px;font-size:16px;line-height:26px;color:#334155;">Hi {{name}},</p>
              <div style="font-size:16px;line-height:26px;color:#334155;">{{body}}</div>
              <p style="margin:16px 0 0;font-size:14px;color:#9a3412;">{{extra_note}}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 32px;">{{cta_block}}</td>
          </tr>
    """,
    bg="#fff7ed",
    accent="#ea580c",
)

DEFAULT_TEMPLATES = [
    {
        "slug": "newsletter",
        "name": "Newsletter",
        "description": "Monthly update with a dark header, image, and a single call-to-action.",
        "preview_color": "#2563eb",
        "html_body": NEWSLETTER,
    },
    {
        "slug": "promo",
        "name": "Promo / Offer",
        "description": "Bold offer layout for discounts, launches, and seasonal campaigns.",
        "preview_color": "#7c3aed",
        "html_body": PROMO,
    },
    {
        "slug": "welcome",
        "name": "Welcome",
        "description": "Friendly onboarding email for new customers or subscribers.",
        "preview_color": "#059669",
        "html_body": WELCOME,
    },
    {
        "slug": "product",
        "name": "Product Launch",
        "description": "Clean product announcement with image and feature copy.",
        "preview_color": "#0284c7",
        "html_body": PRODUCT,
    },
    {
        "slug": "event",
        "name": "Event Invite",
        "description": "Invitation layout for webinars, openings, and client events.",
        "preview_color": "#d97706",
        "html_body": EVENT,
    },
    {
        "slug": "business",
        "name": "Business Update",
        "description": "Formal letter-style notice for invoices, policies, and company news.",
        "preview_color": "#0f172a",
        "html_body": BUSINESS,
    },
    {
        "slug": "thanks",
        "name": "Thank you",
        "description": "Follow-up after a meeting, purchase, or support conversation.",
        "preview_color": "#1d4ed8",
        "html_body": THANKS,
    },
    {
        "slug": "announcement",
        "name": "Announcement",
        "description": "Company news, policy updates, and product notices.",
        "preview_color": "#1e3a8a",
        "html_body": ANNOUNCEMENT,
    },
    {
        "slug": "invoice",
        "name": "Invoice / Payment",
        "description": "Bills, payment requests, and due-date reminders.",
        "preview_color": "#0f172a",
        "html_body": INVOICE,
    },
    {
        "slug": "appointment",
        "name": "Appointment",
        "description": "Bookings, confirmations, and visit reminders.",
        "preview_color": "#0e7490",
        "html_body": APPOINTMENT,
    },
    {
        "slug": "review",
        "name": "Review request",
        "description": "Ask for feedback, ratings, or a Google review.",
        "preview_color": "#d97706",
        "html_body": REVIEW,
    },
    {
        "slug": "followup",
        "name": "Sales follow-up",
        "description": "After a call, demo, or proposal — keep the conversation going.",
        "preview_color": "#4f46e5",
        "html_body": FOLLOWUP,
    },
    {
        "slug": "intro",
        "name": "Introduction",
        "description": "Professional first email to a new lead or partner.",
        "preview_color": "#334155",
        "html_body": INTRO,
    },
    {
        "slug": "flash",
        "name": "Flash sale",
        "description": "Urgent red banner for short-lived discounts.",
        "preview_color": "#dc2626",
        "html_body": FLASH,
    },
    {
        "slug": "digest",
        "name": "Weekly digest",
        "description": "Round-up of news, tips, or product updates.",
        "preview_color": "#4f46e5",
        "html_body": DIGEST,
    },
    {
        "slug": "luxury",
        "name": "Luxury / Premium",
        "description": "Dark gold layout for VIP, fashion, and premium brands.",
        "preview_color": "#d4af37",
        "html_body": LUXURY,
    },
    {
        "slug": "property",
        "name": "Real estate",
        "description": "Listings, viewings, and property updates.",
        "preview_color": "#0f766e",
        "html_body": PROPERTY,
    },
    {
        "slug": "hospitality",
        "name": "Restaurant / Hotel",
        "description": "Menus, reservations, and guest follow-ups.",
        "preview_color": "#c2410c",
        "html_body": HOSPITALITY,
    },
    {
        "slug": "webinar",
        "name": "Webinar / Class",
        "description": "Training, courses, and live session invites.",
        "preview_color": "#1d4ed8",
        "html_body": WEBINAR,
    },
    {
        "slug": "quote",
        "name": "Quote / Proposal",
        "description": "Send a price, scope, or formal offer.",
        "preview_color": "#0369a1",
        "html_body": QUOTE,
    },
    {
        "slug": "meeting",
        "name": "Meeting recap",
        "description": "Summary, next steps, and action items after a meeting.",
        "preview_color": "#7c3aed",
        "html_body": MEETING,
    },
    {
        "slug": "greeting",
        "name": "Greeting card",
        "description": "Birthday, Eid, anniversary, or personal thank-you.",
        "preview_color": "#be185d",
        "html_body": GREETING,
    },
    {
        "slug": "support",
        "name": "Support update",
        "description": "Ticket replies, how-to notes, and help articles.",
        "preview_color": "#1d4ed8",
        "html_body": SUPPORT,
    },
    {
        "slug": "seasonal",
        "name": "Seasonal / Holiday",
        "description": "Ramadan, New Year, and festive campaigns.",
        "preview_color": "#15803d",
        "html_body": SEASONAL,
    },
    {
        "slug": "testimonial",
        "name": "Case study",
        "description": "Share a customer win or social proof story.",
        "preview_color": "#7c3aed",
        "html_body": TESTIMONIAL,
    },
    {
        "slug": "reminder",
        "name": "Gentle reminder",
        "description": "Nudge for unpaid invoices, pending forms, or unused offers.",
        "preview_color": "#ea580c",
        "html_body": REMINDER,
    },
]
