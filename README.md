# Innova CRM — Django leads, contacts, branded email

Proper CRM: CSV se leads, contacts, email templates with logo, campaigns. Inbox-first HTML mail. PostgreSQL ready (`USE_POSTGRES=true`).

Template select karo, content bharao, CSV se list upload karo, phir emails **ek-ek karke throttle** ke sath bhejo.

Inbox placement ke liye yeh app spam-filter "bypass" nahi karti. Woh illegal/unstable hota hai. Yeh **legitimate deliverability** follow karti hai: authenticated domain, slow sending, unsubscribe, HTML+text.

## Run

```powershell
cd C:\Users\muham\Desktop\email
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_templates
python manage.py runserver
```

Open: http://127.0.0.1:8000

## Client workflow

1. **SMTP settings** — Hostinger mailbox already wired: `smtp.hostinger.com:465` SSL, from `info@innovafior.online`. Password Settings page par daalo.
2. **Templates** — 26 inbox-safe layouts (newsletter, promo, invoice, follow-up, luxury, property, webinar, and more). New template = pick a layout + name.
3. **New campaign** — subject, heading, body, button, optional image URL.
4. **Recipients** — `sample_recipients.csv` jaisa file: `email,name,company` (3000 rows).
5. **Send test** — pehle apne inbox + spam folder check karo.
6. **Start sending** — app band mat karna jab tak job complete na ho.

   3000 emails ke liye terminal se bhejna zyada safe hai:

   ```powershell
   python manage.py send_campaign 1
   ```

Default pace: ~0.6s per email + 8s pause every 80 messages. 3000 emails ≈ 30–45 minutes.

## Spam folder se bachne ke rules

Yeh app already karti hai:

- Har recipient ko alag email (BCC blast nahi)
- HTML + plain text
- Unsubscribe link + `List-Unsubscribe` header
- Company physical address footer (CAN-SPAM)
- Rate limit / batch pause
- Unsubscribed addresses skip

Aapko DNS par yeh lagana hai (ESP dashboard se copy):

- **SPF**
- **DKIM**
- **DMARC**

Aur:

- Gmail/Yahoo personal SMTP use mat karo (500/day limit + spam)
- Sirf **opt-in** list (khareedi hui / scraped list spam complaints late hai)
- Subject mein ALL CAPS / `FREE!!!` / misleading "Re:" mat likho
- Image-only email mat bhejo
- Naya domain pehle 7–14 din thodi volume se warm-up karo, seedha 3000 mat maro

## Hostinger (current)

```
EMAIL_HOST=smtp.hostinger.com
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_USE_TLS=False
EMAIL_HOST_USER=info@innovafior.online
```

IMAP (`imap.hostinger.com:993`) Outlook/phone ke liye hai, Django sending ke liye nahi.

Password `.env` ki `EMAIL_HOST_PASSWORD` ya http://127.0.0.1:8000/settings/ par daalo, phir test email bhejo.

## Provider examples

Amazon SES (recommended for 3000):

```
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
```

Brevo:

```
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
```

SendGrid:

```
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
```

`SITE_URL` production mein public URL set karo taake unsubscribe links kaam karein.
