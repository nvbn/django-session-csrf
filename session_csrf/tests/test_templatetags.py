from mock import MagicMock
from django.contrib.auth.models import User
from django.test import TestCase
from ..models import Token
from ..templatetags.session_csrf import per_view_csrf


class PerViewCsrfCase(TestCase):
    """per_view_csrf templatetag case"""

    def test_should_generate_csrf_token_when_authenticated(self):
        """Test template tag should generate csrf when authenticated"""
        request = MagicMock(user=User.objects.create())
        request.user.is_authenticated = lambda: True
        self.assertNotEqual(per_view_csrf({
            'request': request,
        }, 'test'), '')
        self.assertTrue(Token.objects.filter(
            owner=request.user,
            for_view='test',
        ).exists())

    def test_should_fallback_to_default_csrf_when_not_authenticated(self):
        """Test should fallback to default csrf when not authenticated"""
        request = MagicMock()
        request.user.is_authenticated.return_value = False
        self.assertNotEqual(per_view_csrf({
            'request': request,
            'csrf_token': 'test',
        }, 'test'), '')
