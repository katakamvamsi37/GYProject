from importlib import import_module
from io import BytesIO
from uuid import uuid4

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from core.models import AuditEvent, ProfileImage, UserProfile
from core.services.profile_images import MAX_UPLOAD_BYTES
from .base import APITestCase


class AccountFeaturesTests(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def login(self, identifier, password="FestivalPass!234", key="identifier"):
        return APIClient().post(
            "/api/login/", {key: identifier, "password": password}, format="json"
        )

    def patch_profile(self, user, data, format="json"):
        return self.client.patch(f"/api/profiles/{user.pk}/", data, format=format)

    def image_upload(self, format="PNG", size=(20, 10)):
        output = BytesIO()
        Image.new("RGB", size, "red").save(output, format=format)
        return SimpleUploadedFile("local-photo." + format.lower(), output.getvalue())

    def test_mobile_login_accepts_normalized_forms_and_requires_matching_password(self):
        member = self.accounts["member"]
        response = self.patch_profile(member, {"phone": "98765 43210"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["phone"], "+919876543210")
        for key, value in [
            ("phone", "9876543210"),
            ("email", "+91 98765-43210"),
            ("identifier", "919876543210"),
        ]:
            with self.subTest(key=key):
                result = self.login(value, key=key)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.data["user"]["id"], member.pk)
        for identifier, password in [
            ("9876543210", "wrong"),
            ("9988776655", "FestivalPass!234"),
            ("member@example.test", "wrong"),
        ]:
            self.assertEqual(self.login(identifier, password).status_code, 401)

    def test_duplicate_and_invalid_phone_updates_are_rejected(self):
        self.assertEqual(
            self.patch_profile(self.accounts["admin"], {"phone": "9876543210"}).status_code, 200
        )
        member = self.accounts["member"]
        for phone in ["+91 9876543210", "bad-number", "12345", "+9199999"]:
            self.assertEqual(self.patch_profile(member, {"phone": phone}).status_code, 400)
        self.assertEqual(UserProfile.objects.get(user=member).phone, "")

    def test_another_accounts_correct_password_cannot_login(self):
        member = self.accounts["member"]
        member.set_password("MemberOnlyPassword!432")
        member.save(update_fields=["password"])
        self.patch_profile(member, {"phone": "9876543210"})
        for identifier in [member.email, "9876543210"]:
            self.assertEqual(self.login(identifier, "FestivalPass!234").status_code, 401)
            self.assertEqual(self.login(identifier, "MemberOnlyPassword!432").status_code, 200)

    def test_legacy_phone_migration_preserves_ambiguous_numbers_and_blocks_login(self):
        UserProfile.objects.filter(user=self.accounts["admin"]).update(phone="98765 43210")
        UserProfile.objects.filter(user=self.accounts["member"]).update(phone="+91-9876543210")
        migration = import_module("core.migrations.0006_profile_images_and_phone_login")
        migration.normalize_existing_phones(apps, connection.schema_editor())
        self.assertEqual(UserProfile.objects.filter(phone="+919876543210").count(), 2)
        self.assertEqual(self.login("9876543210").status_code, 401)
        self.assertEqual(self.login("member@example.test").status_code, 200)

    def test_duplicate_email_is_ambiguous_even_if_password_matches(self):
        get_user_model().objects.filter(pk=self.accounts["member"].pk).update(
            email="admin@example.test"
        )
        self.assertEqual(self.login("admin@example.test").status_code, 401)

    def test_signup_phone_is_available_for_login(self):
        response = self.post(
            "/api/signup/",
            {
                "name": "New member",
                "email": "new@example.test",
                "phone": "9876543210",
                "password": "NewFestival!4392",
                "role": "member",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.login("9876543210", "NewFestival!4392").status_code, 200)

    def test_email_change_retires_old_email_shaped_username(self):
        user = get_user_model().objects.create_user(
            username="old@example.test", email="old@example.test", password="FestivalPass!234"
        )
        UserProfile.objects.create(user=user)
        self.assertEqual(self.patch_profile(user, {"email": "new@example.test"}).status_code, 200)
        self.assertEqual(self.login("old@example.test").status_code, 401)
        self.assertEqual(self.login("NEW@example.test").status_code, 200)

    def test_inactive_account_cannot_login_by_mobile(self):
        member = self.accounts["member"]
        self.patch_profile(member, {"phone": "9876543210"})
        member.is_active = False
        member.save(update_fields=["is_active"])
        self.assertEqual(self.login("9876543210").status_code, 401)

    def test_login_rejects_conflicting_or_invalid_identifiers(self):
        for body in [
            {"email": "admin@example.test", "phone": "9876543210"},
            {"phone": 9876543210},
            {"identifier": None},
        ]:
            self.assertEqual(
                APIClient()
                .post("/api/login/", {**body, "password": "FestivalPass!234"}, format="json")
                .status_code,
                400,
            )

    def test_admin_resets_member_and_other_admin_passwords_and_revokes_sessions(self):
        other_admin = get_user_model().objects.create_user(
            username="other_admin", email="other@example.test", password="FestivalPass!234"
        )
        UserProfile.objects.create(user=other_admin, role="admin")
        for user in [self.accounts["member"], other_admin]:
            with self.subTest(user=user.username):
                tokens = self.login(user.email).data
                response = self.post(
                    f"/api/users/{user.pk}/password/", {"new_password": "UpdatedFestival!445"}
                )
                self.assertEqual(response.status_code, 200)
                user.refresh_from_db()
                self.assertTrue(user.check_password("UpdatedFestival!445"))
                self.assertEqual(self.login(user.email).status_code, 401)
                self.assertEqual(self.login(user.email, "UpdatedFestival!445").status_code, 200)
                old_session = APIClient()
                old_session.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
                self.assertEqual(old_session.get("/api/me/").status_code, 401)
                self.assertEqual(
                    APIClient()
                    .post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
                    .status_code,
                    401,
                )
                event = AuditEvent.objects.get(action="password_reset", object_id=str(user.pk))
                self.assertEqual(event.actor_id, self.accounts["admin"].pk)
                self.assertEqual(event.before, {})
                self.assertEqual(event.after, {"password_changed": True})
                self.assertNotIn(user.password, str(event.after))

    def test_password_reset_permissions_and_validation(self):
        user = self.accounts["admin"]
        url = f"/api/users/{user.pk}/password/"
        for role in ["member", "treasurer", "secretary", "coordinator", None]:
            self.use(role)
            self.assertEqual(
                self.post(url, {"new_password": "UpdatedFestival!445"}).status_code,
                401 if role is None else 403,
            )
        self.use("admin")
        for body in [{}, {"new_password": ""}, {"new_password": "12345"}]:
            self.assertEqual(self.post(url, body).status_code, 400)
        user.refresh_from_db()
        self.assertTrue(user.check_password("FestivalPass!234"))
        self.assertFalse(AuditEvent.objects.filter(action="password_reset").exists())
        self.assertEqual(
            self.post(
                "/api/users/999999/password/", {"new_password": "UpdatedFestival!445"}
            ).status_code,
            404,
        )

    def test_password_spaces_are_preserved(self):
        member = self.accounts["member"]
        password = "  UpdatedFestival!445  "
        self.assertEqual(
            self.post(f"/api/users/{member.pk}/password/", {"new_password": password}).status_code,
            200,
        )
        self.assertEqual(self.login(member.email, password).status_code, 200)
        self.assertEqual(self.login(member.email, password.strip()).status_code, 401)

    def test_own_password_change_revokes_refresh(self):
        tokens = self.login("member@example.test").data
        self.use("member")
        self.assertEqual(
            self.post(
                "/api/auth/password/change/",
                {
                    "current_password": "FestivalPass!234",
                    "new_password": "UpdatedFestival!445",
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            APIClient()
            .post(
                "/api/auth/token/refresh/",
                {
                    "refresh": tokens["refresh"],
                },
                format="json",
            )
            .status_code,
            401,
        )

    def test_local_avatar_upload_is_stored_resized_and_served_in_production(self):
        member = self.accounts["member"]
        self.use("member")
        response = self.patch_profile(
            member,
            {"name": "New name", "avatar": self.image_upload(size=(1024, 512))},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        url = response.data["user"]["avatar_url"]
        self.assertTrue(url.startswith("http://testserver/api/profiles/"))
        saved = ProfileImage.objects.get(user=member)
        self.assertTrue(saved.image)
        with self.settings(DEBUG=False):
            downloaded = APIClient().get(url)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded["Content-Type"], "image/webp")
        with Image.open(BytesIO(downloaded.content)) as image:
            self.assertEqual(image.size, (512, 256))
            self.assertEqual(image.format, "WEBP")
        self.assertEqual(self.client.get("/api/me/").data["user"]["avatar_url"], url)
        self.assertEqual(self.login(member.email).data["user"]["avatar_url"], url)
        self.assertEqual(
            self.client.get(f"/api/profiles/{member.pk}/").data["user"]["name"], "New name"
        )
        event = AuditEvent.objects.get(action="profile_updated")
        self.assertNotIn("image", event.after)

    def test_avatar_replacement_removal_and_old_urls(self):
        member = self.accounts["member"]
        first = self.patch_profile(
            member, {"avatar": self.image_upload()}, format="multipart"
        ).data["user"]["avatar_url"]
        second = self.patch_profile(
            member, {"avatar": self.image_upload("JPEG")}, format="multipart"
        ).data["user"]["avatar_url"]
        self.assertNotEqual(first, second)
        self.assertEqual(ProfileImage.objects.filter(user=member).count(), 1)
        self.assertEqual(APIClient().get(first).status_code, 404)
        self.assertEqual(APIClient().get(second).status_code, 200)
        self.assertEqual(self.patch_profile(member, {"avatar_url": ""}).status_code, 200)
        self.assertFalse(ProfileImage.objects.filter(user=member).exists())
        self.assertEqual(APIClient().get(second).status_code, 404)

    @override_settings(ALLOWED_HOSTS=["testserver", "api.example.test"])
    def test_text_profile_update_preserves_returned_avatar_url(self):
        self.client.defaults["HTTP_HOST"] = "api.example.test"
        member = self.accounts["member"]
        response = self.patch_profile(member, {"avatar": self.image_upload()}, format="multipart")
        url = response.data["user"]["avatar_url"]
        response = self.patch_profile(member, {"name": "Updated", "avatar_url": url})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["avatar_url"], url)
        self.assertEqual(ProfileImage.objects.filter(user=member).count(), 1)
        self.assertEqual(APIClient().get(url).status_code, 200)

    def test_invalid_avatar_is_rejected_without_changing_profile(self):
        member = self.accounts["member"]
        for upload in [
            SimpleUploadedFile("fake.png", b"<script>bad</script>"),
            SimpleUploadedFile("big.jpg", b"x" * (MAX_UPLOAD_BYTES + 1)),
            self.image_upload("GIF"),
            self.image_upload(size=(5000, 4001)),
        ]:
            response = self.patch_profile(
                member, {"name": "Wrong", "avatar": upload}, format="multipart"
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("avatar", response.data)
        member.refresh_from_db()
        self.assertEqual(member.first_name, "")
        self.assertFalse(ProfileImage.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action="profile_updated").exists())

    def test_member_cannot_upload_someone_elses_avatar(self):
        self.use("member")
        response = self.patch_profile(
            self.accounts["admin"], {"avatar": self.image_upload()}, format="multipart"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProfileImage.objects.exists())

    def test_avatar_url_and_file_cannot_be_sent_together(self):
        response = self.patch_profile(
            self.accounts["member"],
            {
                "avatar": self.image_upload(),
                "avatar_url": "https://example.test/avatar.png",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_avatar_version_returns_404(self):
        self.assertEqual(
            APIClient()
            .get(f"/api/profiles/{self.accounts['member'].pk}/avatar/{uuid4()}/")
            .status_code,
            404,
        )
