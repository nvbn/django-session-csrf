from django.template.defaulttags import CsrfTokenNode
from django import template
from ..utils import save_token, get_token_for_request


register = template.Library()


@register.simple_tag(takes_context=True)
def per_view_csrf(context, view_name):
    """Register per view csrf token. Not pure!"""
    with save_token(context):
        token = get_token_for_request(context['request'], view_name)
        if token is not None:
            context['csrf_token'] = token.value
        return CsrfTokenNode().render(context)
per_view_csrf.is_safe = True
