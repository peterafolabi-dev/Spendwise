import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG is disabled.')
    SECRET_KEY = 'django-insecure-local-development-key-only'

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if not DEBUG and not DATABASE_URL:
    raise ImproperlyConfigured(
        'DATABASE_URL must point to persistent PostgreSQL when DEBUG is disabled.'
    )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
    if host.strip()
]
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
WEBAUTHN_RP_ID = os.environ.get('WEBAUTHN_RP_ID', '')
WEBAUTHN_ORIGIN = os.environ.get('WEBAUTHN_ORIGIN', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b').strip()

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'tracker',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.environ.get(
    'SECURE_SSL_REDIRECT', 'False' if DEBUG else 'True'
).lower() == 'true'
SECURE_HSTS_SECONDS = int(
    os.environ.get('SECURE_HSTS_SECONDS', '0' if DEBUG else '31536000')
)

ROOT_URLCONF = 'spendwise.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tracker.context_processors.social_login_providers',
            ],
        },
    },
]

WSGI_APPLICATION = 'spendwise.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}' if DEBUG else None,
        conn_max_age=600,
        conn_health_checks=True,
    )
}
if not DEBUG and DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured(
        'Production DATABASE_URL must use PostgreSQL; SQLite is only supported for local development.'
    )

CACHES = {
    'default': {
        'BACKEND': (
            'django.core.cache.backends.locmem.LocMemCache'
            if DEBUG
            else 'django.core.cache.backends.db.DatabaseCache'
        ),
        'LOCATION': 'spendwise-cache' if DEBUG else 'django_cache',
        'TIMEOUT': 300,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "tracker.storage.LenientCompressedManifestStaticFilesStorage",
    },
}

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
SITE_ID = 1
LOGOUT_REDIRECT_URL = 'landing'

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 20))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'webmaster@localhost')
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    (
        'django.core.mail.backends.smtp.EmailBackend'
        if EMAIL_HOST and EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
        else (
            'django.core.mail.backends.console.EmailBackend'
            if DEBUG
            else 'django.core.mail.backends.dummy.EmailBackend'
        )
    ),
)

GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '').strip()
APPLE_OAUTH_CLIENT_ID = os.environ.get('APPLE_OAUTH_CLIENT_ID', '').strip()
APPLE_OAUTH_KEY_ID = os.environ.get('APPLE_OAUTH_KEY_ID', '').strip()
APPLE_OAUTH_TEAM_ID = os.environ.get('APPLE_OAUTH_TEAM_ID', '').strip()
APPLE_OAUTH_PRIVATE_KEY = os.environ.get('APPLE_OAUTH_PRIVATE_KEY', '').replace('\\n', '\n').strip()

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APPS': (
            [{
                'client_id': GOOGLE_OAUTH_CLIENT_ID,
                'secret': GOOGLE_OAUTH_CLIENT_SECRET,
                'key': '',
            }]
            if GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET
            else []
        ),
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
    },
    'apple': {
        'APPS': (
            [{
                'client_id': APPLE_OAUTH_CLIENT_ID,
                'secret': APPLE_OAUTH_KEY_ID,
                'key': APPLE_OAUTH_TEAM_ID,
                'settings': {'certificate_key': APPLE_OAUTH_PRIVATE_KEY},
            }]
            if all((
                APPLE_OAUTH_CLIENT_ID,
                APPLE_OAUTH_KEY_ID,
                APPLE_OAUTH_TEAM_ID,
                APPLE_OAUTH_PRIVATE_KEY,
            ))
            else []
        ),
    },
}
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_LOGIN_METHODS = {'username'}
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
