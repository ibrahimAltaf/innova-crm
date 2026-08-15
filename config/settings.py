import os
import sys
from pathlib import Path

from django.contrib.messages import constants as message_constants
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

# SQLite by default; set USE_POSTGRES=true after PostgreSQL is installed.

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() in {"1", "true", "yes"}
raw_hosts = os.getenv("ALLOWED_HOSTS", "").strip()
if not raw_hosts or raw_hosts == "*":
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
    if ".vercel.app" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".vercel.app")
    if "127.0.0.1" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append("127.0.0.1")
    if "localhost" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append("localhost")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "campaigns",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        "DIRS": [BASE_DIR / "campaigns" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "campaigns.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

import urllib.parse

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() in {"1", "true", "yes"}
db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
if "test" in sys.argv:
    pass
elif db_url:
    url = urllib.parse.urlparse(db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path.lstrip("/"),
            "USER": urllib.parse.unquote(url.username or ""),
            "PASSWORD": urllib.parse.unquote(url.password or ""),
            "HOST": url.hostname,
            "PORT": url.port or 5432,
            "OPTIONS": {
                "sslmode": "require",
            },
        }
    }
elif USE_POSTGRES or os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DATABASE") or os.getenv("POSTGRES_DB") or os.getenv("PGDATABASE", "innovacrm"),
            "USER": os.getenv("POSTGRES_USER") or os.getenv("PGUSER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD", "postgres"),
            "HOST": os.getenv("POSTGRES_HOST") or os.getenv("PGHOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "OPTIONS": {
                "sslmode": "require",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip().strip('"').strip("'")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in {"1", "true", "yes"}
EMAIL_TIMEOUT = 30
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@localhost")
DEFAULT_FROM_NAME = os.getenv("DEFAULT_FROM_NAME", "MailForge")
REPLY_TO_EMAIL = os.getenv("REPLY_TO_EMAIL", DEFAULT_FROM_EMAIL)
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
