"""
Base settings shared by all environments.
"""
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-insecure-secret-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "mozilla_django_oidc",
    # local apps
    "apps.accounts",
    "apps.patients",
    "apps.encounters",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
#
# Unlike the earlier "AI apps" in this project (doc-search, faq-chatbot,
# job-matcher, product-recommender, ticket-triage, recipe-finder), which
# stored embeddings as a pgvector column directly on Postgres, this app uses
# TWO genuinely separate database systems:
#   1. Postgres (plain - no `vector` extension needed) for all relational
#      data: users, patients, encounters.
#   2. Qdrant (a dedicated vector database, via apps/common/qdrant_store.py)
#      for embeddings and semantic similarity search, as a completely
#      separate service with no foreign-key/transactional consistency with
#      Postgres - see that module's docstring and the README for how the two
#      are kept in sync and what happens if Qdrant's data is ever lost.
#
# DEV-ONLY OVERRIDE: when USE_SQLITE=True is set in the environment (the
# default in config/settings/dev.py), fall back to SQLite so `manage.py
# check`, `makemigrations` and `test` can run on a machine with no
# Postgres/Docker available. The Qdrant side has its own, independent
# dev-mode fallback (an embedded `:memory:` client - see qdrant_store.py)
# that activates whenever QDRANT_URL is unset, so the whole pipeline is
# testable fully offline regardless of USE_SQLITE.
# ---------------------------------------------------------------------------
USE_SQLITE = config("USE_SQLITE", default=True, cast=bool)

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "dev-sqlite.db",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("POSTGRES_DB", default="clinical_case_finder"),
            "USER": config("POSTGRES_USER", default="postgres"),
            "PASSWORD": config("POSTGRES_PASSWORD", default="postgres"),
            "HOST": config("POSTGRES_HOST", default="localhost"),
            "PORT": config("POSTGRES_PORT", default="5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/min",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# OIDC sign-in via Microsoft Entra ID (mozilla-django-oidc).
#
# The browser is sent to /oidc/authenticate/ (Entra ID authorization code
# flow); on /oidc/callback/ the ID token is verified against Entra's JWKS and
# a server-side Django session is created. The SPA then exchanges that
# session for an app access token (kept in memory only) plus a refresh token
# that is ONLY ever stored in an HttpOnly cookie (see AUTH_REFRESH_COOKIE_*),
# never in localStorage. Unauthenticated API calls get HTTP 401 and the SPA
# redirects the browser to the identity provider.
#
# OIDC_ISSUER is the Entra v2.0 issuer, i.e.
# https://login.microsoftonline.com/<tenant-id>/v2.0 - endpoints are derived
# from it and can each be overridden explicitly.
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "apps.accounts.views.EntraOIDCAuthenticationBackend",
]

OIDC_ISSUER = config("OIDC_ISSUER", default="")
_OIDC_AUTHORITY = OIDC_ISSUER.rstrip("/").removesuffix("/v2.0")

OIDC_RP_CLIENT_ID = config("OIDC_CLIENT_ID", default="")
OIDC_RP_CLIENT_SECRET = config("OIDC_CLIENT_SECRET", default="")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
OIDC_OP_AUTHORIZATION_ENDPOINT = config(
    "OIDC_OP_AUTHORIZATION_ENDPOINT", default=f"{_OIDC_AUTHORITY}/oauth2/v2.0/authorize"
)
OIDC_OP_TOKEN_ENDPOINT = config(
    "OIDC_OP_TOKEN_ENDPOINT", default=f"{_OIDC_AUTHORITY}/oauth2/v2.0/token"
)
OIDC_OP_JWKS_ENDPOINT = config(
    "OIDC_OP_JWKS_ENDPOINT", default=f"{_OIDC_AUTHORITY}/discovery/v2.0/keys"
)
OIDC_OP_USER_ENDPOINT = config(
    "OIDC_OP_USER_ENDPOINT", default="https://graph.microsoft.com/oidc/userinfo"
)
OIDC_STORE_ID_TOKEN = False

LOGIN_URL = "oidc_authentication_init"
# Where the browser lands after a successful/failed Entra sign-in (the SPA).
LOGIN_REDIRECT_URL = config("OIDC_LOGIN_REDIRECT_URL", default="http://localhost:5173/")
LOGIN_REDIRECT_URL_FAILURE = config("OIDC_LOGIN_REDIRECT_URL_FAILURE", default=LOGIN_REDIRECT_URL)
LOGOUT_REDIRECT_URL = config("OIDC_LOGOUT_REDIRECT_URL", default=LOGIN_REDIRECT_URL)

SESSION_COOKIE_HTTPONLY = True

# Refresh token transport: HttpOnly + Secure + SameSite cookie, scoped to the
# auth endpoints only. Never exposed to JavaScript.
AUTH_REFRESH_COOKIE_NAME = config("AUTH_REFRESH_COOKIE_NAME", default="ccf_refresh")
AUTH_REFRESH_COOKIE_PATH = "/api/auth/"
AUTH_REFRESH_COOKIE_SECURE = config("AUTH_REFRESH_COOKIE_SECURE", default=True, cast=bool)
AUTH_REFRESH_COOKIE_SAMESITE = config("AUTH_REFRESH_COOKIE_SAMESITE", default="Lax")

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# AI (apps/common/ai.py). No OpenAI key is required to run this app: with
# OPENAI_API_KEY unset, embeddings are generated by a deterministic,
# documented stub so the whole pipeline is testable offline.
# ---------------------------------------------------------------------------
EMBEDDING_DIMENSIONS = config("OPENAI_EMBEDDING_DIMENSIONS", default=1536, cast=int)
OPENAI_EMBEDDING_MODEL = config("OPENAI_EMBEDDING_MODEL", default="text-embedding-3-large")
OPENAI_CHAT_MODEL = config("OPENAI_CHAT_MODEL", default="gpt-5.6-sol")
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")

# ---------------------------------------------------------------------------
# Qdrant (apps/common/qdrant_store.py). When QDRANT_URL is unset, the store
# uses qdrant-client's fully local embedded mode (`location=":memory:"`) -
# the real Qdrant engine running in-process, no server required. Set
# QDRANT_URL (e.g. http://localhost:6333) to point at a real Qdrant service.
# ---------------------------------------------------------------------------
QDRANT_URL = config("QDRANT_URL", default="")
QDRANT_COLLECTION = config("QDRANT_COLLECTION", default="encounters")
