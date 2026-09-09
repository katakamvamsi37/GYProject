from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from core.models import UserProfile


@override_settings(
    ALLOWED_HOSTS=["testserver"], PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class APITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.accounts = {}
        for role in ["admin", "treasurer", "secretary", "coordinator", "member"]:
            user = get_user_model().objects.create_user(
                username=role, email=f"{role}@example.test", password="FestivalPass!234"
            )
            UserProfile.objects.create(user=user, role=role)
            self.accounts[role] = user
        self.use("admin")

    def use(self, role):
        self.client.force_authenticate(user=self.accounts[role] if role else None)

    def post(self, url, payload):
        return self.client.post(url, payload, format="json")
