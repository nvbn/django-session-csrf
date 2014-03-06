from django.utils.decorators import method_decorator
from .decorators import per_view_csrf


class PerViewCsrfMixin(object):
    """Per view csrf mixin"""

    @method_decorator(per_view_csrf)
    def dispatch(self, *args, **kwargs):
        return super(PerViewCsrfMixin, self).dispatch(*args, **kwargs)
