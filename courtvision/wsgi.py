"""
WSGI config for CourtVision Analytics project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'courtvision.settings.development')

application = get_wsgi_application()
