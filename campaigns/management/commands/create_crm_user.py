import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the single CRM login user (from env or defaults)."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv("CRM_USERNAME", "admin")
        password = os.getenv("CRM_PASSWORD", "admin123")
        email = os.getenv("CRM_EMAIL", "admin@innovafior.online")
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} CRM user '{username}'. Sign in at /login/"))
        if password == "admin123":
            self.stdout.write(self.style.WARNING("Default password is admin123 — change CRM_PASSWORD in .env for production."))
