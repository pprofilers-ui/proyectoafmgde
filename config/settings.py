from pathlib import Path
from datetime import timedelta
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'afmgde-local-secret-key-2026-min-32-chars')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = [host for host in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',') if host]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'drf_yasg',
    'users',
    'audit',
    'stability',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'audit.middleware.AuditRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Configuracion activa para presentacion y despliegue sencillo en PythonAnywhere.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Configuracion alternativa para Azure SQL / SQL Server cuando quieras pasar a entorno final.
# Requiere instalar mssql-django y pyodbc, rellenar el .env y ejecutar migraciones.
# DATABASES = {
#     'default': {
#         'ENGINE': 'mssql',
#         'NAME': os.getenv('DB_NAME', ''),
#         'HOST': os.getenv('DB_HOST', ''),
#         'PORT': os.getenv('DB_PORT', '1433'),
#         'USER': os.getenv('DB_USER', ''),
#         'PASSWORD': os.getenv('DB_PASSWORD', ''),
#         'OPTIONS': {
#             'driver': os.getenv('DB_DRIVER', 'ODBC Driver 18 for SQL Server'),
#             'extra_params': os.getenv('DB_EXTRA_PARAMS', 'Encrypt=yes;TrustServerCertificate=yes'),
#         },
#     }
# }
#
# if os.getenv('DB_TRUSTED_CONNECTION', 'false').lower() == 'true':
#     DATABASES['default']['OPTIONS']['trusted_connection'] = 'yes'
#
# Ejemplo local SQLEXPRESS:
# DATABASES = {
#     'default': {
#         'ENGINE': 'mssql',
#         'NAME': 'afmgde',
#         'HOST': 'localhost\\SQLEXPRESS',
#         'PORT': '',
#         'USER': '',
#         'PASSWORD': '',
#         'OPTIONS': {
#             'driver': 'ODBC Driver 18 for SQL Server',
#             'trusted_connection': 'yes',
#             'extra_params': 'TrustServerCertificate=yes',
#         },
#     }
# }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL='/media/'

MEDIA_ROOT=os.path.join(BASE_DIR,'media')

STATICFILES_DIRS=[os.path.join(BASE_DIR,'static'),]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'users.authentication.ContextJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 25,
    'EXCEPTION_HANDLER': 'config.exception.api_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
}

SWAGGER_SETTINGS = {
    'USE_SESSION_AUTH': True,
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'JWT Authorization header using the Bearer scheme. Example: Bearer <token>',
        },
        'App Version': {
            'type': 'apiKey',
            'name': 'app-version',
            'in': 'header',
            'description': 'Version de cliente requerida por la API.',
        },
        'Company': {
            'type': 'apiKey',
            'name': 'company',
            'in': 'header',
            'description': 'Codigo de empresa activa.',
        },
        'Contact': {
            'type': 'apiKey',
            'name': 'contact',
            'in': 'header',
            'description': 'Codigo de contacto activo.',
        },
        'Address': {
            'type': 'apiKey',
            'name': 'address',
            'in': 'header',
            'description': 'Codigo de direccion o ubicacion activa.',
        },
    },
}

REQUIRED_APP_VERSION = os.getenv('REQUIRED_APP_VERSION', '1.0.0')
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'


# ==============================================================================
# CORRECCIÓN PARA ERROR: "Object of type Decimal is not JSON serializable"
# ==============================================================================
import json
from django.core.serializers.json import DjangoJSONEncoder

# Forzamos a que todo el proyecto use el encoder de Django que sí acepta Decimales
json.JSONEncoder = DjangoJSONEncoder