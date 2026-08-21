import django.db.models.deletion
from django.db import migrations, models


def backfill_from_recipients(apps, schema_editor):
    Recipient = apps.get_model("campaigns", "Recipient")
    SendLog = apps.get_model("campaigns", "SendLog")
    for row in Recipient.objects.filter(status="sent").iterator():
        log = SendLog(email=row.email, campaign_id=row.campaign_id, kind="campaign")
        log.save()
        when = row.sent_at or row.created_at
        if when:
            SendLog.objects.filter(pk=log.pk).update(created_at=when)


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0006_appsettings_daily_send_limit"),
    ]

    operations = [
        migrations.CreateModel(
            name="SendLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                (
                    "kind",
                    models.CharField(
                        choices=[("campaign", "Campaign"), ("test", "Test")],
                        default="campaign",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="send_logs",
                        to="campaigns.campaign",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(backfill_from_recipients, migrations.RunPython.noop),
    ]
