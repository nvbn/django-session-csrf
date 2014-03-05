from contextlib import contextmanager
from django.template.defaulttags import CsrfTokenNode
from django import template
from ..models import Token


register = template.Library()


@contextmanager
def save_token(context):
    is_exists = 'csrf_token' in context
    token = context.get('csrf_token')
    yield
    if is_exists:
        context['csrf_token'] = token
    else:
        del context['csrf_token']

@register.simple_tag(takes_context=True)
def per_view_csrf(context, view_name):
    """Register per view csrf token. Not pure!"""
    with save_token(context):
        request = context['request']
        if request.user.is_authenticated():
            token, _ = Token.objects.get_or_create(
                owner=request.user, for_view=view_name)
            context['csrf_token'] = token.value
        node = CsrfTokenNode()
        return node.render(context)
per_view_csrf.is_safe = True
