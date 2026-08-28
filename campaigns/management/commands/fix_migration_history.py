"""Repair migration order when 0007_sendlog was applied before 0005/0006."""
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = "Fake-apply missing campaigns migrations when 0007_sendlog is already recorded."

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        applied = {f"{app}.{name}" for app, name in recorder.applied_migrations()}
        if "campaigns.0007_sendlog" not in applied:
            self.stdout.write("No repair needed.")
            return
        fixes = [
            ("campaigns", "0005_campaign_editor_modes"),
            ("campaigns", "0006_appsettings_daily_send_limit"),
        ]
        for app, name in fixes:
            key = f"{app}.{name}"
            if key not in applied:
                recorder.record_applied(app, name)
                self.stdout.write(self.style.SUCCESS(f"Recorded {key}"))
        self.stdout.write("Migration history repaired.")
