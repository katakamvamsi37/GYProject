import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase

from core.models import UserProfile


class BootstrapAdminCommandTests(TestCase):
    bootstrap_env = {
        "DJANGO_SUPERUSER_USERNAME": "render-admin",
        "DJANGO_SUPERUSER_EMAIL": "render-admin@example.test",
        "DJANGO_SUPERUSER_PASSWORD": "StrongRenderPassword!234",
    }

    def test_missing_variables_are_a_safe_noop(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in self.bootstrap_env:
                os.environ.pop(key, None)
            call_command("bootstrap_admin")

        self.assertFalse(get_user_model().objects.exists())

    def test_creates_superuser_and_admin_profile(self):
        with patch.dict(os.environ, self.bootstrap_env):
            call_command("bootstrap_admin")

        user = get_user_model().objects.get(username="render-admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(self.bootstrap_env["DJANGO_SUPERUSER_PASSWORD"]))
        self.assertEqual(user.profile.role, "admin")

    def test_repeated_deploy_does_not_change_password(self):
        with patch.dict(os.environ, self.bootstrap_env):
            call_command("bootstrap_admin")
            password_hash = get_user_model().objects.get(username="render-admin").password
            call_command("bootstrap_admin")

        user = get_user_model().objects.get(username="render-admin")
        self.assertEqual(user.password, password_hash)
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_existing_non_superuser_username_fails(self):
        get_user_model().objects.create_user(
            username="render-admin", email="member@example.test", password="MemberPass!234"
        )

        with self.assertRaisesMessage(CommandError, "already exists and is not a superuser"):
            with patch.dict(os.environ, self.bootstrap_env):
                call_command("bootstrap_admin")
