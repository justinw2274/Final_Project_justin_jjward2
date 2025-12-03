"""
ASGI config for CourtVision Analytics project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'courtvision.settings.development')

application = get_asgi_application()
