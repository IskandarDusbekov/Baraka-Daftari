import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("SECRET_KEY muhit o'zgaruvchisi o'rnatilmagan")
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "bot",
    "panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.seo.context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.getenv("DB_ENGINE", "").lower() in ("postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "baraka"),
            "USER": os.getenv("POSTGRES_USER", "baraka"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Kesh: production'da Redis (REDIS_URL=redis://127.0.0.1:6379/1) — rate limit va keshlar
# barcha gunicorn worker'lar uchun umumiy bo'ladi. Bo'lmasa — xotiradagi kesh.
if os.getenv("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.getenv("REDIS_URL")}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if not DEBUG:
    # Fayl nomiga xesh qo'shiladi (app.3f9a1c.js) — brauzer uzoq keshlaydi, yangilanganda darhol yangisini oladi
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }

LOGIN_URL = "/boshqaruv/kirish/"

# Admin panel → Zaxira nusxa: qo'lda olingan nusxalar papkasi (git'ga va nginx'ga kirmaydi)
BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))

# Django admin manzili: productionda taxmin qilib bo'lmaydigan yo'l qo'ying (ADMIN_URL=maxfiy-yol-7f3k/)
ADMIN_URL = os.getenv("ADMIN_URL", "admin/").strip("/") + "/"

# Admin panel sessiyasi: 12 soatdan keyin qayta kirish kerak; cookie'larni JS o'qiy olmaydi
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Katta so'rovlar bilan serverni to'ldirishdan himoya
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# YouTube embed pleyeri sayt manzilini (referrer) talab qiladi, aks holda "153-xato" beradi.
# Django standarti "same-origin" tashqi saytlarga referrer yubormaydi.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # HTTPS ulangach .env da yoqing: SSL_REDIRECT=True, HSTS_SECONDS=31536000
    SECURE_SSL_REDIRECT = os.getenv("SSL_REDIRECT", "False").lower() in ("1", "true", "yes")
    SECURE_HSTS_SECONDS = int(os.getenv("HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"

# --- Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
MORNING_HOUR = int(os.getenv("MORNING_HOUR", "8"))
EVENING_HOUR = int(os.getenv("EVENING_HOUR", "20"))

# Dasturchi kirishi (login/parol). Faqat ishlab chiqish vaqtida yoqing!
DEV_LOGIN = os.getenv("DEV_LOGIN", str(DEBUG)).lower() in ("1", "true", "yes")
DEV_USERNAME = os.getenv("DEV_USERNAME", "admin")
DEV_PASSWORD = os.getenv("DEV_PASSWORD", "")

# API tokeni amal qilish muddati (soniya)
API_TOKEN_MAX_AGE = 60 * 60 * 24 * 30
LOGIN_CODE_TTL = 60 * 10

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
