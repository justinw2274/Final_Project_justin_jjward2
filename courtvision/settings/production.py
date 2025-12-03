"""
Django production settings for CourtVision Analytics.
For deployment on PythonAnywhere.
"""

from .base import *
import os

DEBUG = False

# Update with your PythonAnywhere username
ALLOWED_HOSTS = [
    'justinward.pythonanywhere.com',  # Update this with your actual username
    'localhost',
    '127.0.0.1',
]

# Production secret key - generate a new one for production!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'your-production-secret-key-change-me')

# Database configuration
# Option 1: SQLite (simpler, works on free PythonAnywhere)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Option 2: PostgreSQL (uncomment for external database - requires paid account)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.environ.get('DB_NAME', 'courtvision'),
#         'USER': os.environ.get('DB_USER', ''),
#         'PASSWORD': os.environ.get('DB_PASSWORD', ''),
#         'HOST': os.environ.get('DB_HOST', 'localhost'),
#         'PORT': os.environ.get('DB_PORT', '5432'),
#     }
# }

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
