from mock import MagicMock
from django.contrib.auth.models import User
from django.test import TestCase
from ..models import Token
from ..utils import save_token, get_token_for_request


class TestUtils(TestCase):
    """Test case for utils"""

    def test_should_not_modify_token(self):
        """Test should not modify token"""
        context = {'csrf_token': 'test'}
        with save_token(context):
            context['csrf_token'] = 'wtf'
        self.assertEqual(context['csrf_token'], 'test')

    def test_get_token_for_authenticated(self):
        """Test get token for authenticated"""
        user = User.objects.create()
        user.is_authenticated = lambda: True
        token = get_token_for_request(MagicMock(user=user), 'test')
        self.assertIsInstance(token, Token)

    def test_get_none_for_anonymous(self):
        """Test get None for anonymous"""
        request = MagicMock()
        request.user.is_authenticated.return_value = False
        token = get_token_for_request(request, 'test')
        self.assertIsNone(token)
