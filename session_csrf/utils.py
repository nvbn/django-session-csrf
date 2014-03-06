from contextlib import contextmanager
import hashlib
from .models import Token
from . import conf


def prep_key(key):
    """
    In case a bogus request comes in with a large or wrongly formatted
    massive anoncsrf cookie value, memcache will raise a
    MemcachedKeyLengthError or MemcachedKeyCharacterError. We hash the
    key here in order to have a predictable length and character set.
    """
    prefixed = conf.PREFIX + key
    return hashlib.sha1(prefixed).hexdigest()


@contextmanager
def save_token(context):
    """Restore token value in context"""
    is_exists = 'csrf_token' in context
    token = context.get('csrf_token')
    yield
    if is_exists:
        context['csrf_token'] = token
    else:
        del context['csrf_token']


def get_token_for_request(request, view_name):
    """Get token for request"""
    if request.user.is_authenticated():
        token, _ = Token.objects.get_or_create(
            owner=request.user, for_view=view_name)
        return token
