import hashlib
from . import conf


def prep_key(key):
    """
    In case a bogus request comes in with a large or wrongly formatted
    massive anoncsrf cookie value, memcache will raise a
    MemcachedKeyLengthError or MemcachedKeyCharacterError. We hash the
    key here in order to have a predictable length and character set.
    """
    prefixed = conf.PREFIX + key
    return hashlib.md5(prefixed).hexdigest()
