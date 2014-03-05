import django.test
from django.contrib.auth.models import User
from ..models import Token
from .base import make_expired


class TokenModelCase(django.test.TestCase):
    """Test case for token model"""

    def setUp(self):
        self._user = User.objects.create_user('test', 'test@test.test', 'test')

    def test_should_generate_token_on_first_save(self):
        """Test that token should be generated on first save"""
        token = Token.objects.create(owner=self._user)
        self.assertIsNotNone(token.value)

    def test_should_not_regenerate_token(self):
        """Test that token should not regenerate token on second save"""
        token = Token.objects.create(owner=self._user)
        value = token.value
        token.save()
        self.assertEqual(token.value, value)

    def test_get_expired_tokens(self):
        """Test get expired tokens"""
        for _ in range(5):
            Token.objects.create(owner=self._user)
        expired = [
            make_expired(Token.objects.create(owner=self._user))
            for _ in range(3)
        ]
        self.assertItemsEqual(
            Token.objects.get_expired(), expired,
        )

    def test_has_valid_tokens(self):
        """Test user has valid tokens"""
        token = Token.objects.create(owner=self._user)
        self.assertTrue(
            Token.objects.has_valid(self._user, token.value),
        )

    def test_has_no_valid_tokens_without_token(self):
        """Test has no valid tokens without tokens"""
        self.assertFalse(
            Token.objects.has_valid(self._user, 'token'),
        )

    def test_has_no_valid_token_when_expired(self):
        """Test has not valid tokens when expired"""
        token = Token.objects.create(owner=self._user)
        make_expired(token)
        self.assertFalse(
            Token.objects.has_valid(self._user, token.value),
        )

    def test_has_valid_token_for_view(self):
        """Test has valid token for view"""
        token = Token.objects.create(owner=self._user, for_view='test')
        self.assertTrue(
            Token.objects.has_valid(self._user, token.value, 'test'),
        )
