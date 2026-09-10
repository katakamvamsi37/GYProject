from django.core.cache import cache
from core.models import AuditEvent
from .base import APITestCase


class AuthenticationTests(APITestCase):
    def test_missing_login_fields_do_not_query_accounts(self):
        self.use(None)
        for body in ({}, {"email": "  ", "password": "test"}, {"email": "admin"}):
            with self.subTest(body=body), self.assertNumQueries(0):
                self.assertEqual(self.post("/api/login/", body).status_code, 400)

    def test_login_accepts_email_address(self):
        self.use(None)
        response = self.post(
            "/api/login/", {"email": "ADMIN@example.test", "password": "FestivalPass!234"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "admin")

    def test_initial_superuser_can_sign_in_without_existing_profile(self):
        from django.contrib.auth import get_user_model

        self.use(None)
        get_user_model().objects.create_superuser(
            username="initial-admin",
            email="initial@example.test",
            password="InitialFestival!234",
        )
        response = self.post(
            "/api/login/", {"email": "initial@example.test", "password": "InitialFestival!234"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "admin")

    def test_fresh_session_requires_login(self):
        self.use(None)
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_password_login_refresh_and_logout(self):
        self.use(None)
        response = self.post("/api/login/", {"email": "admin", "password": "FestivalPass!234"})
        self.assertEqual(response.status_code, 200)
        old_refresh = response.data["refresh"]
        rotated = self.post("/api/auth/token/refresh/", {"refresh": old_refresh})
        self.assertEqual(rotated.status_code, 200)
        self.assertEqual(
            self.post("/api/auth/token/refresh/", {"refresh": old_refresh}).status_code, 401
        )
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + rotated.data["access"])
        self.assertEqual(
            self.post("/api/logout/", {"refresh": rotated.data["refresh"]}).status_code, 204
        )
        self.client.credentials()
        self.assertEqual(
            self.post("/api/auth/token/refresh/", {"refresh": rotated.data["refresh"]}).status_code,
            401,
        )

    def test_otp_never_exposes_codes_even_in_debug(self):
        self.use(None)
        with self.settings(DEBUG=True):
            for path in ["auth/otp/request", "auth/otp/verify", "auth/password/reset"]:
                response = self.post(
                    "/api/" + path + "/",
                    {"destination": "admin@example.test", "channel": "email", "purpose": "login"},
                )
                self.assertEqual(response.status_code, 410)
                self.assertNotIn("development_code", response.data)

    def test_member_cannot_manage_accounts(self):
        self.use("member")
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.post("/api/signup/", {}).status_code, 403)

    def test_creation_validates_password_and_audits_without_secrets(self):
        body = {
            "name": "Volunteer",
            "email": "new@example.test",
            "password": "12345678",
            "role": "member",
        }
        self.assertEqual(self.post("/api/signup/", body).status_code, 400)
        body["password"] = "NewFestival!4392"
        response = self.post("/api/signup/", body)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["user"]["is_active"])
        event = AuditEvent.objects.get(action="user_created")
        self.assertNotIn("password", event.after)
        self.assertNotIn(body["password"], str(event.after))

    def test_profile_changes_clear_verification_and_cannot_change_role(self):
        user = self.accounts["member"]
        profile = user.profile
        profile.phone, profile.phone_verified, profile.email_verified = "12345", True, True
        profile.save()
        self.use("member")
        response = self.client.patch(
            f"/api/profiles/{user.pk}/",
            {"phone": "9876543210", "email": "changed@example.test", "role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["user"]["phone_verified"])
        self.assertFalse(response.data["user"]["email_verified"])
        self.assertEqual(response.data["user"]["role"], "member")
        self.assertEqual(
            self.client.get(f"/api/profiles/{self.accounts['admin'].pk}/").status_code, 403
        )

    def test_deactivation_revokes_access(self):
        self.use(None)
        tokens = self.post("/api/login/", {"email": "member", "password": "FestivalPass!234"}).data
        user = self.accounts["member"]
        user.is_active = False
        user.save()
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_password_change_invalidates_existing_access(self):
        self.use(None)
        tokens = self.post("/api/login/", {"email": "member", "password": "FestivalPass!234"}).data
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        self.assertEqual(
            self.post(
                "/api/auth/password/change/",
                {"current_password": "FestivalPass!234", "new_password": "DifferentFestival!445"},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_login_rate_limit(self):
        self.use(None)
        cache.clear()
        for i in range(10):
            self.post("/api/login/", {"email": "missing", "password": "incorrect"})
        self.assertEqual(
            self.post("/api/login/", {"email": "missing", "password": "incorrect"}).status_code, 429
        )
        cache.clear()

    def test_cannot_disable_own_admin_access(self):
        response = self.client.patch(
            f"/api/users/{self.accounts['admin'].pk}/access/",
            {"role": "member", "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
