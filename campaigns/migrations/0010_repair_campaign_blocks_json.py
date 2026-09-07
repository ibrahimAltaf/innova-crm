from django.db import migrations


def repair_blocks_json(apps, schema_editor):
    table = "campaigns_campaign"
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            if "blocks_json" not in columns:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN blocks_json text NOT NULL DEFAULT '[]'"
                )
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'blocks_json'
                """,
                [table],
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN blocks_json jsonb NOT NULL DEFAULT '[]'::jsonb"
                )


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0009_repair_campaign_html_content")]

    operations = [migrations.RunPython(repair_blocks_json, migrations.RunPython.noop)]
