"""Regression checks for Render configuration and browser API access."""

import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings


class EnvironmentSettingsTests(SimpleTestCase):
    def load_settings(self, **env):
        with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).resolve().parents[2] / "config/settings.py"))

    def test_aws_proxy_and_http_healthcheck_are_explicit(self):
        env = {
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "test-only",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
            "DJANGO_ALLOWED_HOSTS": "api.example.test",
        }
        defaults = self.load_settings(**env)
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", defaults)
        self.assertNotIn("SECURE_REDIRECT_EXEMPT", defaults)
        configured = self.load_settings(
            **env, DJANGO_TRUST_PROXY_HEADERS="true", DJANGO_HTTP_HEALTHCHECK="true"
        )
        self.assertEqual(configured["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(configured["SECURE_REDIRECT_EXEMPT"], [r"^health/$"])
        self.assertTrue(configured["SECURE_SSL_REDIRECT"])
        self.assertFalse(configured["DEBUG"])
        self.assertEqual(configured["MIDDLEWARE"][0], "config.health.ContainerHealthMiddleware")

    def test_split_postgres_uses_tls_in_production_and_shared_cache(self):
        values = self.load_settings(
            DJANGO_DEBUG="false",
            DJANGO_SECRET_KEY="test-only",
            POSTGRES_DB="gyproject",
            DJANGO_CACHE_TABLE="gyproject_cache",
        )
        self.assertEqual(values["DATABASES"]["default"]["OPTIONS"]["sslmode"], "require")
        self.assertEqual(values["CACHES"]["default"]["LOCATION"], "gyproject_cache")

    def test_local_postgres_can_disable_tls(self):
        values = self.load_settings(
            DJANGO_DEBUG="true", DJANGO_SECRET_KEY="test-only", POSTGRES_DB="gyproject"
        )
        self.assertEqual(values["DATABASES"]["default"]["OPTIONS"]["sslmode"], "disable")

    def test_render_requires_a_secret_by_default(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_SECRET_KEY"):
            self.load_settings(RENDER="true")

    def test_render_never_silently_uses_sqlite(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "DATABASE_URL"):
            self.load_settings(RENDER="true", DJANGO_DEBUG="true", DJANGO_SECRET_KEY="test-only")

    def test_render_database_proxy_and_custom_origin(self):
        values = self.load_settings(
            RENDER="true",
            RENDER_EXTERNAL_HOSTNAME="gyproject.onrender.com",
            DJANGO_SECRET_KEY="test-only",
            DATABASE_URL="postgresql://test:test@localhost:5432/test_db",
            CORS_ALLOWED_ORIGINS=" https://frontend.example/ , http://localhost:5173, ",
        )
        self.assertFalse(values["DEBUG"])
        self.assertEqual(values["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(values["DATABASES"]["default"]["OPTIONS"]["sslmode"], "require")
        self.assertIn("gyproject.onrender.com", values["ALLOWED_HOSTS"])
        self.assertEqual(values["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(
            values["CORS_ALLOWED_ORIGINS"],
            ["https://frontend.example", "http://localhost:5173"],
        )


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    CORS_ALLOWED_ORIGINS=["https://gy-project-frontend.onrender.com"],
)
class BrowserDeploymentTests(SimpleTestCase):
    def test_root_and_health_allow_get_and_head_without_database(self):
        for path in ("/", "/health/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).json(), {"status": "ok"})
                self.assertEqual(self.client.head(path).status_code, 200)

    def test_login_and_financial_submission_preflight(self):
        for path in ("/api/login/", "/api/payments/"):
            with self.subTest(path=path):
                response = self.client.options(
                    path,
                    HTTP_ORIGIN="https://gy-project-frontend.onrender.com",
                    HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
                    HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,authorization,idempotency-key",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response["Access-Control-Allow-Origin"],
                    "https://gy-project-frontend.onrender.com",
                )
                self.assertIn("idempotency-key", response["Access-Control-Allow-Headers"])

    def test_unknown_origin_is_not_allowed(self):
        response = self.client.options(
            "/api/login/",
            HTTP_ORIGIN="https://unrelated.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertNotIn("Access-Control-Allow-Origin", response)

    @override_settings(
        DEBUG=False,
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        SECURE_REDIRECT_EXEMPT=[],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.middleware.common.CommonMiddleware",
        ],
    )
    def test_render_https_does_not_redirect_forever(self):
        response = self.client.get("/health/", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/health/").status_code, 301)

    @override_settings(
        DEBUG=False,
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^health/$"],
    )
    def test_private_http_healthcheck_keeps_api_https_redirects(self):
        self.assertEqual(self.client.get("/health/").status_code, 200)
        self.assertEqual(self.client.head("/health/").status_code, 200)
        self.assertEqual(self.client.get("/api/me/").status_code, 301)


@override_settings(
    DEBUG=False,
    ALLOWED_HOSTS=["api.example.test"],
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    MIDDLEWARE=[
        "config.health.ContainerHealthMiddleware",
        "django.middleware.security.SecurityMiddleware",
        "django.middleware.common.CommonMiddleware",
    ],
)
class ContainerHealthTests(SimpleTestCase):
    def test_alb_private_ip_probe_works_without_redirect_or_database(self):
        response = self.client.get("/health/", HTTP_HOST="10.0.1.25:8000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")
        response = self.client.head("/health/", HTTP_HOST="10.0.1.25:8000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_health_rejects_writes(self):
        self.assertEqual(self.client.post("/health/", HTTP_HOST="10.0.1.25").status_code, 405)

    def test_health_exception_does_not_bypass_api_host_validation(self):
        for path in ("/api/me/", "/health/extra", "/admin/"):
            with self.subTest(path=path):
                response = self.client.get(
                    path, HTTP_HOST="untrusted.example", HTTP_X_FORWARDED_PROTO="https"
                )
                self.assertEqual(response.status_code, 400)

    def test_api_still_redirects_to_https(self):
        response = self.client.get("/api/me/", HTTP_HOST="api.example.test")
        self.assertEqual(response.status_code, 301)
