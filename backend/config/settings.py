from agent.settings import (
    BACKEND_DIR,
    DATA_DIR,
    DJANGO_DEBUG,
    DJANGO_SECRET_KEY,
    FRONTEND_ORIGINS,
)

BASE_DIR = BACKEND_DIR

SECRET_KEY = DJANGO_SECRET_KEY
DEBUG = DJANGO_DEBUG
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {}

CORS_ALLOWED_ORIGINS = FRONTEND_ORIGINS

USE_TZ = True
