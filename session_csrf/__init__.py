"""CSRF protection without cookies."""
from django.middleware import csrf as django_csrf
from .middlewares import CsrfMiddleware
# for compatibility with exists code:
from .context_processors import context_processor
from .decorators import anonymous_csrf, anonymous_csrf_exempt
from .utils import prep_key
from .conf import ANON_ALWAYS, ANON_COOKIE, ANON_TIMEOUT, PREFIX


def monkeypatch():
    from django.views.decorators import csrf as csrf_dec
    django_csrf.CsrfViewMiddleware = CsrfMiddleware
    csrf_dec.csrf_protect = csrf_dec.decorator_from_middleware(CsrfMiddleware)
