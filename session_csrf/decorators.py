import functools
from django.core.cache import cache
from django.middleware import csrf as django_csrf
from django.utils.cache import patch_vary_headers
from .utils import prep_key
from . import conf


def anonymous_csrf(f):
    """Decorator that assigns a CSRF token to an anonymous user."""
    @functools.wraps(f)
    def wrapper(request, *args, **kw):
        use_anon_cookie = not (request.user.is_authenticated() or conf.ANON_ALWAYS)
        if use_anon_cookie:
            if conf.ANON_COOKIE in request.COOKIES:
                key = request.COOKIES[conf.ANON_COOKIE]
                token = cache.get(prep_key(key)) or django_csrf._get_new_csrf_key()
            else:
                key = django_csrf._get_new_csrf_key()
                token = django_csrf._get_new_csrf_key()
            cache.set(prep_key(key), token, conf.ANON_TIMEOUT)
            request.csrf_token = token
        response = f(request, *args, **kw)
        if use_anon_cookie:
            # Set or reset the cache and cookie timeouts.
            response.set_cookie(conf.ANON_COOKIE, key, max_age=conf.ANON_TIMEOUT,
                                httponly=True, secure=request.is_secure())
            patch_vary_headers(response, ['Cookie'])
        return response
    return wrapper


def anonymous_csrf_exempt(f):
    """Like @csrf_exempt but only for anonymous requests."""
    f.anonymous_csrf_exempt = True
    return f


def per_view_csrf(fn):
    """Require per view csrf"""
    fn.per_view_csrf = True
    return fn
