from jinja2 import nodes
from coffin.template.defaulttags import CsrfTokenExtension
from coffin import template
from ..utils import get_token_for_request


register = template.Library()


@register.tag
class PerViewCSRFExtension(CsrfTokenExtension):
    """Per-view csrf token for jinja2"""

    tags = {'per_view_csrf'}

    def parse(self, parser):
        """Parse tokens from template"""
        lineno = parser.stream.next().lineno
        view_name = parser.parse_expression()
        return nodes.Output([
            self.call_method('_render', [
                nodes.Name('csrf_token', 'load'),
                view_name,
                nodes.Name('request', 'load'),
            ]),
        ]).set_lineno(lineno)

    def _render(self, csrf_token, view_name, request):
        """Render csrf token"""
        token = get_token_for_request(request, view_name)
        if token is not None:
            csrf_token = token.value
        return super(PerViewCSRFExtension, self)._render(csrf_token)
