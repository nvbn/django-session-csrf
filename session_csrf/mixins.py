from django.utils.decorators import classonlymethod


class PerViewCsrfMixin(object):
    """Per view csrf mixin"""

    @classonlymethod
    def as_view(cls, *args, **kwargs):
        view = super(PerViewCsrfMixin, cls).as_view(*args, **kwargs)
        view.per_view_csrf = True
        return view
