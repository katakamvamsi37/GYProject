import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import UserProfile


class Command(BaseCommand):
    help = "Create the initial Render administrator from deployment environment variables."

    username_key = "DJANGO_SUPERUSER_USERNAME"
    email_key = "DJANGO_SUPERUSER_EMAIL"
    password_key = "DJANGO_SUPERUSER_PASSWORD"

    def handle(self, *args, **options):
        values = {key: os.getenv(key, "").strip() for key in self._required_keys()}
        configured = [bool(value) for value in values.values()]

        if not any(configured):
            self.stdout.write("Bootstrap administrator variables are not set; skipping.")
            return
        if not all(configured):
            missing = ", ".join(key for key, value in values.items() if not value)
            raise CommandError(f"Missing required bootstrap administrator variable(s): {missing}")

        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=values[self.username_key])
        except user_model.DoesNotExist:
            user = None

        if user is not None and not user.is_superuser:
            raise CommandError(
                f"Username '{values[self.username_key]}' already exists and is not a superuser."
            )

        if user is None:
            candidate = user_model(
                username=values[self.username_key],
                email=values[self.email_key],
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            validate_password(values[self.password_key], candidate)
            with transaction.atomic():
                user = user_model.objects.create_superuser(
                    username=values[self.username_key],
                    email=values[self.email_key],
                    password=values[self.password_key],
                )
                UserProfile.objects.update_or_create(
                    user=user, defaults={"role": "admin"}
                )
            self.stdout.write(self.style.SUCCESS("Bootstrap administrator created."))
            return

        UserProfile.objects.update_or_create(user=user, defaults={"role": "admin"})
        self.stdout.write("Bootstrap administrator already exists; no password changed.")

    def _required_keys(self):
        return (self.username_key, self.email_key, self.password_key)
