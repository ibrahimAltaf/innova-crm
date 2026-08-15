from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0003_lead_appsettings_brand_color_appsettings_logo_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="next_follow_up",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name="Activity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("note", "Note"),
                            ("status", "Stage change"),
                            ("email", "Email"),
                            ("convert", "Converted"),
                        ],
                        default="note",
                        max_length=20,
                    ),
                ),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lead",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="campaigns.lead",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
