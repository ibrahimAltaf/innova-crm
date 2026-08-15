from campaigns.catalog import DEFAULT_TEMPLATES
from campaigns.models import EmailTemplate


def ensure_templates():
    existing = set(EmailTemplate.objects.values_list("slug", flat=True))
    for item in DEFAULT_TEMPLATES:
        if item["slug"] not in existing:
            EmailTemplate.objects.create(**item)
