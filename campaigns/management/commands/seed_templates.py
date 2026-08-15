from django.core.management.base import BaseCommand

from campaigns.catalog import DEFAULT_TEMPLATES
from campaigns.models import EmailTemplate


class Command(BaseCommand):
    help = "Load the built-in HTML email templates"

    def handle(self, *args, **options):
        created = 0
        for item in DEFAULT_TEMPLATES:
            _, was_created = EmailTemplate.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "description": item["description"],
                    "preview_color": item["preview_color"],
                    "html_body": item["html_body"],
                    "is_active": True,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Templates ready. New: {created}, total: {EmailTemplate.objects.count()}"))
