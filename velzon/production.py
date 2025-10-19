# velzon/production.py

from .settings import *
import os
from pathlib import Path
import platform

# Security settings for production
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY')

# ==============================================================================
# CRITICAL FIX: Ensure your Azure hostname is in ALLOWED_HOSTS
# ==============================================================================
AZURE_HOSTNAME = os.environ.get('WEBSITE_HOSTNAME')
ALLOWED_HOSTS = []
if AZURE_HOSTNAME:
    ALLOWED_HOSTS.append(AZURE_HOSTNAME)

print(f"[Startup] Allowed hosts configured: {ALLOWED_HOSTS}")
# ==============================================================================


# CSRF and Security
CSRF_TRUSTED_ORIGINS = [
    f"https://{AZURE_HOSTNAME}"
] if AZURE_HOSTNAME else []

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Fix redirect loop behind Azure proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Azure MySQL Flexible Server Configuration (secure)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('AZURE_MYSQL_NAME', 'careercoach1'),
        'USER': os.environ.get('AZURE_MYSQL_USER'),
        'PASSWORD': os.environ.get('AZURE_MYSQL_PASSWORD'),
        'HOST': os.environ.get('AZURE_MYSQL_HOST'),
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
            'ssl_mode': 'REQUIRED',
        },
    }
}

# PRODUCTION CACHE & CHANNELS CONFIGURATION (AZURE REDIS)
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
REDIS_HOST = 'redicach3.redis.cache.windows.net'
REDIS_PORT = 6380

if REDIS_PASSWORD:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None},
            },
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [(f"rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1")],
            },
        },
    }
    print("[Startup] Redis configured for Caching and Channels.")
else:
    print("[Startup] WARNING: REDIS_PASSWORD not set. Falling back to in-memory.")
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Static files for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'