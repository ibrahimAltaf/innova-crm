from django.test import TestCase
from django.urls import reverse

from campaigns.catalog import DEFAULT_TEMPLATES
from campaigns.mailer import render_email_html
from campaigns.models import AppSettings, Campaign, EmailTemplate, Recipient
from campaigns.utils import ensure_templates


class TemplateTests(TestCase):
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
        self.assertContains(detail, "Sent")
        self.assertContains(detail, "Failed")

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


class PipelineTests(TestCase):
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
