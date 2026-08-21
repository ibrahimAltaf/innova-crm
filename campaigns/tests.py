from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campaigns.catalog import DEFAULT_TEMPLATES
from campaigns.mailer import render_email_html
from campaigns.models import AppSettings, Campaign, EmailTemplate, Recipient
from campaigns.utils import ensure_templates


class AuthMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(username="admin", password="pass123")
        self.client.login(username="admin", password="pass123")


class TemplateTests(AuthMixin, TestCase):
    def test_core_placeholders(self):
        required = ["heading", "body", "name", "company_name", "unsubscribe_url", "cta_block", "logo_block"]
        for item in DEFAULT_TEMPLATES:
            for key in required:
                self.assertIn("{{" + key + "}}", item["html_body"], item["slug"])

    def test_render_replaces_placeholders(self):
        ensure_templates()
        tpl = EmailTemplate.objects.get(slug="newsletter")
        campaign = Campaign.objects.create(
            name="August",
            template=tpl,
            subject="Hello from Acme",
            preheader="A useful update",
            heading="Your August update",
            body="Thanks for staying with us.",
            cta_text="Open dashboard",
            cta_url="https://example.com",
        )
        recipient = Recipient(
            campaign=campaign,
            email="ana@example.com",
            name="Ana",
            unsubscribe_token="abc",
        )
        app = AppSettings(
            company_name="Acme",
            company_address="1 Street",
            website_url="https://example.com",
        )
        html = render_email_html(campaign, recipient, "https://example.com/unsub", app)
        self.assertIn("Ana", html)
        self.assertIn("Your August update", html)
        self.assertIn("https://example.com/unsub", html)
        self.assertNotIn("{{heading}}", html)

    def test_dashboard_and_gallery(self):
        response = self.client.get(reverse("campaigns:dashboard"))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("campaigns:templates"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newsletter")

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("campaigns:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_template_create_without_slug_or_html(self):
        response = self.client.post(
            reverse("campaigns:template_create"),
            {"name": "Client thanks", "layout": "thanks", "is_active": "on", "preview_color": "#1d4ed8"},
        )
        self.assertEqual(response.status_code, 302)
        tpl = EmailTemplate.objects.get(name="Client thanks")
        self.assertTrue(tpl.slug)
        self.assertIn("{{heading}}", tpl.html_body)
        self.assertIn("{{unsubscribe_url}}", tpl.html_body)

    def test_create_picker_and_simple_editor(self):
        response = self.client.get(reverse("campaigns:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Simple editor")
        self.assertContains(response, "blog post")
        editor_page = self.client.get(reverse("campaigns:editor_simple_new"))
        self.assertEqual(editor_page.status_code, 200)
        self.assertContains(editor_page, "Start writing")
        self.assertContains(editor_page, "Inbox preview")
        self.assertContains(editor_page, "Preview &amp; Test")
        self.assertContains(response, "HTML custom code")
        self.assertContains(response, "Drag and drop editor")
        save = self.client.post(
            reverse("campaigns:editor_simple_new"),
            {
                "name": "Paste campaign",
                "subject": "Please link your page",
                "preheader": "A short inbox preview",
                "html_content": "<p>Hi {{name}},</p><p><img src=\"data:image/png;base64,iVBORw0KGgo=\" alt=\"\"></p>",
                "blocks_json": "[]",
                "action": "quit",
            },
        )
        self.assertEqual(save.status_code, 302)
        campaign = Campaign.objects.get(name="Paste campaign")
        self.assertEqual(campaign.editor_mode, "simple")
        self.assertIn("<img", campaign.html_content)
        detail = self.client.get(reverse("campaigns:detail", args=[campaign.pk]))
        self.assertEqual(detail.status_code, 200)
        autosave = self.client.post(
            reverse("campaigns:editor_simple_new"),
            {
                "name": "Auto draft",
                "subject": "Hello",
                "preheader": "",
                "html_content": "<p>Hi</p>",
                "blocks_json": "[]",
                "action": "autosave",
            },
        )
        self.assertEqual(autosave.status_code, 200)
        payload = autosave.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["id"])
        self.assertContains(detail, "Sent")
        self.assertContains(detail, "Failed")

    def test_html_and_dragdrop_editors_load(self):
        html_page = self.client.get(reverse("campaigns:editor_html_new"))
        self.assertEqual(html_page.status_code, 200)
        self.assertContains(html_page, "HTML custom code")
        blocks = self.client.get(reverse("campaigns:editor_dragdrop_new"))
        self.assertEqual(blocks.status_code, 200)
        self.assertContains(blocks, "Heading")
        settings = self.client.get(reverse("campaigns:settings"))
        self.assertEqual(settings.status_code, 200)
        self.assertContains(settings, "SMTP")

    def test_custom_html_render_and_cid(self):
        from email.mime.multipart import MIMEMultipart

        from campaigns.mailer import attach_data_uri_images, render_email_html
        from campaigns.utils import ensure_custom_template

        template = ensure_custom_template()
        campaign = Campaign.objects.create(
            name="HTML send",
            template=template,
            editor_mode="html",
            subject="Hello",
            heading="Hello",
            html_content="<p>Hi {{name}}</p><img src=\"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=\" alt=\"x\">",
        )
        recipient = Recipient(campaign=campaign, email="ana@example.com", name="Ana", unsubscribe_token="abc")
        app = AppSettings(company_name="Acme", company_address="1 Street", website_url="https://example.com")
        html = render_email_html(campaign, recipient, "https://example.com/unsub", app)
        self.assertIn("Hi Ana", html)
        self.assertIn("Unsubscribe", html)
        msg = MIMEMultipart()
        converted = attach_data_uri_images(html, msg)
        self.assertIn("cid:paste-img-1", converted)
        self.assertTrue(msg.get_payload())

    def test_statistics_page(self):
        response = self.client.get(reverse("campaigns:statistics"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delivery statistics")

    def test_live_preview_renders(self):
        ensure_templates()
        tpl = EmailTemplate.objects.get(slug="newsletter")
        campaign = Campaign.objects.create(
            name="Preview campaign",
            template=tpl,
            subject="Hello",
            heading="Visible headline",
            body="Body copy",
        )
        response = self.client.get(reverse("campaigns:detail", args=[campaign.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible headline")
        self.assertContains(response, "campaign-preview-frame")
        preview = self.client.get(reverse("campaigns:preview", args=[campaign.pk]))
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Visible headline")


class ContactBulkTests(AuthMixin, TestCase):
    def test_search_and_bulk_add(self):
        ensure_templates()
        tpl = EmailTemplate.objects.get(slug="newsletter")
        campaign = Campaign.objects.create(
            name="Outreach",
            template=tpl,
            subject="Hi",
            heading="Hi",
            body="Hello",
        )
        from campaigns.models import Contact

        for i in range(30):
            Contact.objects.create(email=f"user{i}@client.com", name=f"User {i}", company="Acme")
        page = self.client.get(reverse("campaigns:contacts"), {"q": "user1"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "user1@client.com")
        self.assertContains(page, "Select")
        bulk = self.client.post(
            reverse("campaigns:contacts_bulk_send"),
            {"campaign_id": campaign.pk, "mode": "20", "q": ""},
        )
        self.assertEqual(bulk.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.total_recipients, 20)
        picked = self.client.post(
            reverse("campaigns:recipients", args=[campaign.pk]),
            {"action": "from_contacts", "mode": "50"},
        )
        self.assertEqual(picked.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.total_recipients, 30)

    def test_smtp_prefers_env_password(self):
        from django.test import override_settings

        from campaigns.mailer import smtp_kwargs
        from campaigns.models import AppSettings

        AppSettings.objects.create(
            smtp_host="smtp.old.example",
            smtp_user="old@example.com",
            smtp_password="old-db-password",
            from_email="old@example.com",
        )
        with override_settings(
            EMAIL_HOST="smtp.hostinger.com",
            EMAIL_PORT=465,
            EMAIL_HOST_USER="info@innovafior.online",
            EMAIL_HOST_PASSWORD="env-secret",
            EMAIL_USE_SSL=True,
            EMAIL_USE_TLS=False,
        ):
            kwargs = smtp_kwargs(AppSettings.load())
        self.assertEqual(kwargs["password"], "env-secret")
        self.assertEqual(kwargs["username"], "info@innovafior.online")
        self.assertEqual(kwargs["host"], "smtp.hostinger.com")


class SmtpRecoveryTests(AuthMixin, TestCase):
    def test_dead_connection_is_detected(self):
        from campaigns.mailer import _is_ratelimit, _smtp_connection_dead, explain_send_error

        self.assertTrue(_smtp_connection_dead(RuntimeError("please run connect() first")))
        self.assertTrue(_smtp_connection_dead(RuntimeError("SMTP server disconnected")))
        self.assertFalse(_smtp_connection_dead(RuntimeError("550 user unknown")))
        self.assertTrue(_is_ratelimit(RuntimeError('451 4.7.1 Ratelimit "hostinger_out_ratelimit" exceeded')))
        title, raw = explain_send_error(RuntimeError("(550, '5.1.1 User unknown: gone@nope.invalid')"))
        self.assertIn("not available", title.lower())
        self.assertIn("550", raw)
        auth_title, _ = explain_send_error(RuntimeError("(535, b'5.7.8 Error: authentication failed: (reason unavailable)')"))
        self.assertIn("password", auth_title.lower())

    def test_campaign_continues_after_missing_mailbox(self):
        from unittest.mock import MagicMock, patch

        from campaigns.mailer import run_campaign
        from django.utils import timezone

        ensure_templates()
        tpl = EmailTemplate.objects.get(slug="newsletter")
        campaign = Campaign.objects.create(
            name="Hostinger bounce",
            template=tpl,
            subject="Hi",
            heading="Hi",
            body="Body",
        )
        bad = Recipient.objects.create(campaign=campaign, email="gone@nope.invalid", name="Gone")
        ok = Recipient.objects.create(campaign=campaign, email="ok@client.com", name="Ok")

        def fake_send(_campaign, recipient, _app, _connection):
            if recipient.email.startswith("gone@"):
                raise RuntimeError("(550, '5.1.1 User unknown: gone@nope.invalid')")
            recipient.status = Recipient.Status.SENT
            recipient.sent_at = timezone.now()
            recipient.error_message = ""
            recipient.save(update_fields=["status", "sent_at", "error_message"])
            _campaign.sent_count += 1
            _campaign.save(update_fields=["sent_count", "updated_at"])

        with patch("campaigns.mailer._open_smtp", return_value=MagicMock()), patch(
            "campaigns.mailer.send_one", side_effect=fake_send
        ), patch("campaigns.mailer.time.sleep"):
            run_campaign(campaign.pk)

        bad.refresh_from_db()
        ok.refresh_from_db()
        campaign.refresh_from_db()
        self.assertEqual(bad.status, Recipient.Status.FAILED)
        self.assertIn("not available", bad.error_message.lower())
        self.assertIn("550", bad.fail_detail)
        self.assertEqual(ok.status, Recipient.Status.SENT)
        self.assertEqual(campaign.sent_count, 1)
        self.assertEqual(campaign.failed_count, 1)


class PipelineTests(AuthMixin, TestCase):
    def test_dashboard_pipeline_and_move(self):
        from campaigns.models import Activity, Lead

        lead = Lead.objects.create(email="ana@client.com", name="Ana", company="Acme", value=15000, source="website")
        dash = self.client.get(reverse("campaigns:dashboard"))
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "Pipeline funnel")
        board = self.client.get(reverse("campaigns:leads"))
        self.assertEqual(board.status_code, 200)
        self.assertContains(board, "Ana")
        self.assertContains(board, "Lead management")
        self.assertContains(board, "Qualified")
        move = self.client.post(
            reverse("campaigns:lead_move", args=[lead.pk]),
            data='{"status": "qualified"}',
            content_type="application/json",
        )
        self.assertEqual(move.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "qualified")
        self.assertTrue(Activity.objects.filter(lead=lead, kind="status").exists())

    def test_delivery_report(self):
        ensure_templates()
        tpl = EmailTemplate.objects.get(slug="newsletter")
        campaign = Campaign.objects.create(
            name="Blast",
            template=tpl,
            subject="Hi",
            heading="Hi",
            body="Body",
        )
        Recipient.objects.create(campaign=campaign, email="ok@ex.com", name="Ok", status="sent")
        Recipient.objects.create(
            campaign=campaign, email="bad@ex.com", name="Bad", status="failed", error_message="SMTP error"
        )
        report = self.client.get(reverse("campaigns:delivery") + "?status=failed")
        self.assertEqual(report.status_code, 200)
        self.assertContains(report, "bad@ex.com")
        self.assertContains(report, "SMTP error")
        dash = self.client.get(reverse("campaigns:dashboard"))
        self.assertContains(dash, "Hostinger send quota")

    def test_send_batch_size_buttons(self):
        from unittest.mock import patch

        app = AppSettings.load()
        app.smtp_host = "smtp.hostinger.com"
        app.smtp_port = 465
        app.smtp_user = "info@example.com"
        app.smtp_password = "secret"
        app.smtp_use_ssl = True
        app.from_email = "info@example.com"
        app.save()
        ensure_templates()
        tpl = EmailTemplate.objects.get(slug="newsletter")
        campaign = Campaign.objects.create(name="Batch", template=tpl, subject="Hi", heading="Hi", body="Body")
        for i in range(3):
            Recipient.objects.create(campaign=campaign, email=f"u{i}@client.com", name=f"U{i}")
        page = self.client.get(reverse("campaigns:detail", args=[campaign.pk]))
        self.assertContains(page, "Send 20")
        self.assertContains(page, "Send 100")
        self.assertContains(page, "Send 500")
        with patch("campaigns.views.run_campaign") as run:
            response = self.client.post(
                reverse("campaigns:send", args=[campaign.pk]),
                {"batch": "100"},
                HTTP_X_REQUESTED_WITH="fetch",
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["batch"], 100)
        run.assert_called_once_with(campaign.pk, limit=3)
