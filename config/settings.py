from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# =============================================================================
# Environment helpers
# =============================================================================


def env_bool(
    name: str,
    *,
    default: bool = False,
) -> bool:
    value = os.environ.get(
        name
    )

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(
    name: str,
    *,
    default: list[str] | None = None,
) -> list[str]:
    value = os.environ.get(
        name
    )

    if value is None:
        return default or []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


# =============================================================================
# Core settings
# =============================================================================

DEBUG = env_bool(
    "DJANGO_DEBUG",
    default=True,
)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY"
)

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = (
            "dev-only-change-me"
        )
    else:
        raise RuntimeError(
            (
                "DJANGO_SECRET_KEY must be set "
                "when DEBUG is false."
            )
        )

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "[::1]",
    ],
)

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
)

# Railway/other reverse proxies terminate HTTPS before Django.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)


# =============================================================================
# Applications
# =============================================================================

INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party apps
    "django_extensions",
    "storages",

    # Local apps
    "config",
    "ops_portal",
    "accounts",
    "products",
    "inventory",
    "orders",
    "pricing",
    "customers",
    "business_portal",
    "business",
    "retail",
    "payments",
    "storefront",
]


# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # Require login for all app pages except explicitly exempt paths.
    "config.middleware.LoginRequiredMiddleware",

    # Custom middleware to set request.account and check view permissions.
    "accounts.middleware.AccountContextMiddleware",
    "accounts.middleware.ViewCapabilityMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =============================================================================
# URL / WSGI
# =============================================================================

ROOT_URLCONF = (
    "config.urls"
)

WSGI_APPLICATION = (
    "config.wsgi.application"
)


# =============================================================================
# Templates
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django.DjangoTemplates"
        ),
        "DIRS": [
            BASE_DIR
            / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth.context_processors."
                    "auth"
                ),
                (
                    "django.contrib.messages.context_processors."
                    "messages"
                ),
                (
                    "config.context_processors."
                    "navigation"
                ),
            ],
        },
    },
]


# =============================================================================
# Database
# =============================================================================

if os.environ.get(
    "PGHOST"
):
    DATABASES = {
        "default": {
            "ENGINE": (
                "django.db.backends.postgresql"
            ),
            "NAME": os.environ[
                "PGDATABASE"
            ],
            "USER": os.environ[
                "PGUSER"
            ],
            "PASSWORD": os.environ[
                "PGPASSWORD"
            ],
            "HOST": os.environ[
                "PGHOST"
            ],
            "PORT": os.environ.get(
                "PGPORT",
                "5432",
            ),
            "CONN_MAX_AGE": 600,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": (
                "django.db.backends.sqlite3"
            ),
            "NAME": (
                BASE_DIR
                / "db.sqlite3"
            ),
        }
    }


# =============================================================================
# Auth / Password validation
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LOGIN_URL = (
    "login"
)

LOGIN_REDIRECT_URL = (
    "accounts:after_login"
)

LOGOUT_REDIRECT_URL = (
    "login"
)


# =============================================================================
# Email
# =============================================================================

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    (
        "SwedeSweets "
        "<no-reply@swedesweets.local>"
    )
    if DEBUG
    else (
        "SwedeSweets "
        "<no-reply@swedesweets.com>"
    ),
)

SERVER_EMAIL = os.environ.get(
    "SERVER_EMAIL",
    DEFAULT_FROM_EMAIL,
)

if DEBUG:
    EMAIL_BACKEND = os.environ.get(
        "EMAIL_BACKEND",
        (
            "django.core.mail.backends."
            "console.EmailBackend"
        ),
    )
else:
    EMAIL_BACKEND = os.environ.get(
        "EMAIL_BACKEND",
        (
            "django.core.mail.backends."
            "smtp.EmailBackend"
        ),
    )

EMAIL_HOST = os.environ.get(
    "EMAIL_HOST",
    "",
)

EMAIL_PORT = int(
    os.environ.get(
        "EMAIL_PORT",
        "587",
    )
)

EMAIL_HOST_USER = os.environ.get(
    "EMAIL_HOST_USER",
    "",
)

EMAIL_HOST_PASSWORD = (
    os.environ.get(
        "EMAIL_HOST_PASSWORD",
        "",
    )
)

EMAIL_USE_TLS = env_bool(
    "EMAIL_USE_TLS",
    default=not DEBUG,
)

EMAIL_USE_SSL = env_bool(
    "EMAIL_USE_SSL",
    default=False,
)

EMAIL_TIMEOUT = int(
    os.environ.get(
        "EMAIL_TIMEOUT",
        "10",
    )
)


# =============================================================================
# Payments
# =============================================================================

SUMUP_API_KEY = os.environ.get(
    "SUMUP_API_KEY",
    "",
)

SUMUP_MERCHANT_CODE = (
    os.environ.get(
        "SUMUP_MERCHANT_CODE",
        "",
    )
)


# =============================================================================
# Internationalization
# =============================================================================

LANGUAGE_CODE = os.environ.get(
    "DJANGO_LANGUAGE_CODE",
    "en",
)

LANGUAGES = [
    (
        "en",
        "English",
    ),
    (
        "fr",
        "French",
    ),
]

LOCALE_PATHS = [
    BASE_DIR
    / "locale",
]

TIME_ZONE = (
    "Europe/Stockholm"
)

USE_I18N = True
USE_TZ = True


# =============================================================================
# Static files
# =============================================================================

STATIC_URL = (
    "/static/"
)

STATIC_ROOT = (
    BASE_DIR
    / "staticfiles"
)

STATICFILES_DIRS = [
    BASE_DIR
    / "static",
]


# =============================================================================
# Media storage
# =============================================================================

MEDIA_URL = (
    "/media/"
)

MEDIA_ROOT = (
    BASE_DIR
    / "media"
)


S3_BUCKET_NAME = os.environ.get(
    "AWS_STORAGE_BUCKET_NAME",
    "",
)

S3_ACCESS_KEY_ID = os.environ.get(
    "AWS_ACCESS_KEY_ID",
    "",
)

S3_SECRET_ACCESS_KEY = os.environ.get(
    "AWS_SECRET_ACCESS_KEY",
    "",
)

S3_ENDPOINT_URL = os.environ.get(
    "AWS_S3_ENDPOINT_URL",
    "",
)

S3_REGION_NAME = os.environ.get(
    "AWS_S3_REGION_NAME",
    "",
)


S3_MEDIA_SETTINGS = {
    "AWS_STORAGE_BUCKET_NAME": (
        S3_BUCKET_NAME
    ),
    "AWS_ACCESS_KEY_ID": (
        S3_ACCESS_KEY_ID
    ),
    "AWS_SECRET_ACCESS_KEY": (
        S3_SECRET_ACCESS_KEY
    ),
    "AWS_S3_ENDPOINT_URL": (
        S3_ENDPOINT_URL
    ),
    "AWS_S3_REGION_NAME": (
        S3_REGION_NAME
    ),
}

MISSING_S3_MEDIA_SETTINGS = [
    name
    for name, value in S3_MEDIA_SETTINGS.items()
    if not value
]

USE_S3_MEDIA = (
    not MISSING_S3_MEDIA_SETTINGS
)


if not DEBUG and not USE_S3_MEDIA:
    missing_settings = ", ".join(
        MISSING_S3_MEDIA_SETTINGS
    )

    raise RuntimeError(
        (
            "S3 media storage must be configured "
            "when DEBUG is false. "
            f"Missing: {missing_settings}"
        )
    )


if USE_S3_MEDIA:
    DEFAULT_STORAGE = {
        "BACKEND": (
            "storages.backends.s3."
            "S3Storage"
        ),
        "OPTIONS": {
            "bucket_name": (
                S3_BUCKET_NAME
            ),
            "access_key": (
                S3_ACCESS_KEY_ID
            ),
            "secret_key": (
                S3_SECRET_ACCESS_KEY
            ),
            "endpoint_url": (
                S3_ENDPOINT_URL
            ),
            "region_name": (
                S3_REGION_NAME
            ),
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 3600,
            "file_overwrite": False,
        },
    }
else:
    DEFAULT_STORAGE = {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    }


STORAGES = {
    "default": DEFAULT_STORAGE,
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# =============================================================================
# Defaults
# =============================================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)
