from datetime import timedelta
from django.conf import settings


ANON_COOKIE = getattr(settings, 'ANON_COOKIE', 'anoncsrf')
ANON_TIMEOUT = getattr(settings, 'ANON_TIMEOUT', 60 * 60 * 2)  # 2 hours.
ANON_ALWAYS = getattr(settings, 'ANON_ALWAYS', False)
PREFIX = 'sessioncsrf:'

CSRF_TOKEN_LIFETIME = getattr(
    settings, 'CSRF_TOKEN_LIFETIME', timedelta(hours=1),
)
