"""Environment configuration. See .env.example and docs/SETUP.md."""

import os
import secrets
from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
IS_RENDER = os.getenv("RENDER", "").lower() == "true" or bool(os.getenv("RENDER_EXTERNAL_HOSTNAME"))
DEBUG = os.getenv("DJANGO_DEBUG", "false" if IS_RENDER else "true").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")
    key_file = BASE_DIR / ".development-key"
    if not key_file.exists():
        key_file.write_text(secrets.token_urlsafe(64), encoding="utf-8")
    SECRET_KEY = key_file.read_text(encoding="utf-8").strip()
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=not DEBUG,
        )
    }
elif os.getenv("POSTGRES_DB") or os.getenv("RDS_DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB") or os.environ["RDS_DB_NAME"],
            "USER": os.getenv("POSTGRES_USER", os.getenv("RDS_USERNAME")),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", os.getenv("RDS_PASSWORD")),
            "HOST": os.getenv("POSTGRES_HOST", os.getenv("RDS_HOSTNAME", "localhost")),
            "PORT": os.getenv("POSTGRES_PORT", os.getenv("RDS_PORT", "5432")),
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "sslmode": os.getenv("POSTGRES_SSLMODE", "disable" if DEBUG else "require"),
            },
        }
    }
else:
    if IS_RENDER or not DEBUG:
        raise ImproperlyConfigured(
            "Set DATABASE_URL to your PostgreSQL connection URL "
            "(or configure POSTGRES_DB and the other POSTGRES_* settings)."
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "https://gy-project-frontend.onrender.com,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_HEADERS = [*default_headers, "idempotency-key"]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
# Enable only when requests arrive through a trusted HTTPS-terminating proxy.
TRUST_PROXY_HEADERS = (
    IS_RENDER or os.getenv("DJANGO_TRUST_PROXY_HEADERS", "false").lower() == "true"
)
if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# AWS load balancers may check this endpoint over their private HTTP connection.
if os.getenv("DJANGO_HTTP_HEALTHCHECK", "false").lower() == "true":
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]
    MIDDLEWARE.insert(0, "config.health.ContainerHealthMiddleware")

# Keep production-secure defaults, while allowing an explicitly configured
# HTTP-only deployment (for example, a single-instance Beanstalk environment)
# until TLS is terminated by a load balancer, CloudFront, or a custom domain.
SECURE_SSL_REDIRECT = os.getenv(
    "DJANGO_SECURE_SSL_REDIRECT", "false" if DEBUG else "true"
).lower() == "true"
SECURE_COOKIES = os.getenv(
    "DJANGO_SECURE_COOKIES", "false" if DEBUG else "true"
).lower() == "true"
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
SECURE_HSTS_SECONDS = int(
    os.getenv("DJANGO_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
# A shared database cache is sufficient for the initial committee workload and
# avoids process-local throttles. Run createcachetable in the release task.
if cache_table := os.getenv("DJANGO_CACHE_TABLE"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": cache_table,
        }
    }
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "core.api.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "30/hour", "user": "1000/hour", "login": "10/minute"},
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=12),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "CHECK_REVOKE_TOKEN": True,
}
