"""
Django production settings for CourtVision Analytics.
For deployment on PythonAnywhere.
"""

from .base import *
import os

DEBUG = False

# Update with your PythonAnywhere username
ALLOWED_HOSTS = [
    'justinw2274.pythonanywhere.com',
    'localhost',
    '127.0.0.1',
]

# Production secret key - generate a new one for production!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'your-production-secret-key-change-me')

# Database configuration - MySQL (PythonAnywhere free tier)
# Set USE_MYSQL=true in environment to enable external database
if os.environ.get('USE_MYSQL', 'false').lower() == 'true':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DB_NAME', 'justinw2274$courtvision'),
            'USER': os.environ.get('MYSQL_USER', 'justinw2274'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', 'justinw2274.mysql.pythonanywhere-services.com'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    # Fallback to SQLite for simpler setup
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
