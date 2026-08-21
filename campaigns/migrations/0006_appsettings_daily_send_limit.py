from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0005_campaign_editor_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="daily_send_limit",
            field=models.PositiveIntegerField(
                default=3000,
                help_text="Hostinger Premium ≈ 3000/day per mailbox. Starter ≈ 1000. Free ≈ 100.",
            ),
        ),
    ]
