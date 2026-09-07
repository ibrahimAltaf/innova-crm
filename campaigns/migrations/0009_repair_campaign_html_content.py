from django.db import migrations


def repair_html_content(apps, schema_editor):
    table = "campaigns_campaign"
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            if "html_content" not in columns:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN html_content text NOT NULL DEFAULT ''"
                )
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'html_content'
                """,
                [table],
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN html_content text NOT NULL DEFAULT ''"
                )


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0008_alter_campaign_html_content")]

    operations = [migrations.RunPython(repair_html_content, migrations.RunPython.noop)]
