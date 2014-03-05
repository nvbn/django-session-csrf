from copy import copy
from django.template.defaulttags import CsrfTokenNode
from django import template
from ..models import Token


register = template.Library()


@register.simple_tag(takes_context=True)
def per_view_csrf(context, view_name):
    """Register per view csrf token. Not pure!"""
    _context = copy(context)
    request = _context['request']
    if request.user.is_authenticated():
        token, _ = Token.objects.get_or_create(
            owner=request.user, for_view=view_name)
        _context['csrf_token'] = token.value
    node = CsrfTokenNode()
    return node.render(_context)
per_view_csrf.is_safe = True
