from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from campaigns.models import (
    Campaign,
    EmailJob,
    EmailTemplate,
    Recipient,
    SenderAccount,
    SuppressionEntry,
)
from campaigns.services.credentials import set_sender_password, sender_password
from campaigns.services.email_sender import process_due_jobs
from campaigns.services.queue import enqueue_campaign
from campaigns.services.sender_pool import allocate_sender, get_available_senders, select_sender
from campaigns.services.suppression import suppress_email
from campaigns.utils import ensure_templates
from campaigns.tests import AuthMixin


def _campaign():
    ensure_templates()
    tpl = EmailTemplate.objects.get(slug="newsletter")
    return Campaign.objects.create(name="Pool", template=tpl, subject="Hi", heading="Hi", body="Body")


def _sender(**kwargs):
    defaults = dict(
        smtp_host="smtp.hostinger.com",
        smtp_port=465,
        smtp_use_ssl=True,
        daily_limit=300,
        hourly_limit=50,
        min_interval_seconds=0,
        is_active=True,
    )
    defaults.update(kwargs)
    return SenderAccount.objects.create(**defaults)


class SenderPoolTests(AuthMixin, TestCase):
    def test_passwords_are_encrypted(self):
        sender = _sender(email="a@example.com")
        set_sender_password(sender, "plain-secret")
        sender.save()
        sender.refresh_from_db()
        self.assertNotEqual(sender.password_encrypted, "plain-secret")
        self.assertEqual(sender_password(sender), "plain-secret")

    def test_least_used_sender_is_selected(self):
        busy = _sender(email="busy@example.com", sent_today=9)
        fresh = _sender(email="fresh@example.com", sent_today=1)
        picked = allocate_sender()
        self.assertEqual(picked.pk, fresh.pk)
        busy.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(fresh.sent_today, 2)
        self.assertEqual(busy.sent_today, 9)

    def test_hourly_limit_is_not_exceeded(self):
        _sender(email="capped@example.com", hourly_limit=1, sent_this_hour=1, hour_key=timezone.localtime().hour)
        self.assertIsNone(allocate_sender())

    def test_suppressed_addresses_are_not_queued_as_sendable(self):
        campaign = _campaign()
        row = Recipient.objects.create(campaign=campaign, email="stop@client.com")
        suppress_email("stop@client.com", SuppressionEntry.Reason.UNSUBSCRIBE, source="test")
        queued = enqueue_campaign(campaign.pk)
        self.assertEqual(queued, 0)
        row.refresh_from_db()
        self.assertEqual(row.status, Recipient.Status.SKIPPED)

    def test_idempotent_resend_does_not_duplicate(self):
        campaign = _campaign()
        _sender(email="pool@example.com")
        row = Recipient.objects.create(campaign=campaign, email="once@client.com")
        enqueue_campaign(campaign.pk)

        def fake_send(_campaign, recipient, _app, _connection, **_kwargs):
            recipient.status = Recipient.Status.SENT
            recipient.sent_at = timezone.now()
            recipient.save(update_fields=["status", "sent_at"])
            _campaign.sent_count += 1
            _campaign.save(update_fields=["sent_count", "updated_at"])

        with patch("campaigns.services.email_sender._open_sender_smtp", return_value=MagicMock()), patch(
            "campaigns.services.email_sender.send_one", side_effect=fake_send
        ), patch("campaigns.services.email_sender.time.sleep"):
            self.assertEqual(process_due_jobs(1), 1)
            self.assertEqual(process_due_jobs(1), 0)
        row.refresh_from_db()
        self.assertEqual(row.status, Recipient.Status.SENT)
        self.assertEqual(EmailJob.objects.filter(recipient=row, status=EmailJob.Status.SENT).count(), 1)

    def test_sender_pool_page_requires_login_and_hides_secrets(self):
        sender = _sender(email="secret@example.com")
        set_sender_password(sender, "super-secret-pass")
        sender.save()
        page = self.client.get(reverse("campaigns:sender_pool"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "secret@example.com")
        self.assertNotContains(page, "super-secret-pass")

    def test_all_active_mailboxes_share_a_campaign_evenly(self):
        boxes = [_sender(email=f"box{i}@example.com") for i in range(5)]
        picks = [allocate_sender().email for _ in range(10)]
        counts = {box.email: picks.count(box.email) for box in boxes}
        self.assertEqual(set(counts.values()), {2})
        self.assertEqual(len(get_available_senders()), 5)

    def test_lower_limit_mailbox_is_not_overfilled(self):
        small = _sender(email="small@example.com", daily_limit=1, hourly_limit=1)
        big = _sender(email="big@example.com", daily_limit=100, hourly_limit=50)
        picks = [allocate_sender().email for _ in range(4)]
        self.assertEqual(picks.count(small.email), 1)
        self.assertEqual(picks.count(big.email), 3)

    def test_inactive_mailbox_is_excluded_until_enabled(self):
        live = _sender(email="live@example.com")
        dark = _sender(email="dark@example.com", is_active=False)
        picked = select_sender()
        self.assertEqual(picked.pk, live.pk)
        dark.is_active = True
        dark.save(update_fields=["is_active"])
        emails = {select_sender().email, select_sender().email}
        self.assertEqual(emails, {live.email, dark.email})
