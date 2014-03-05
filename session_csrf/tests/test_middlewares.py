import mock
import django.test
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.template import context
from ..models import Token
from ..middlewares import CsrfMiddleware
from ..utils import prep_key
from .. import conf
from .base import ClientHandler, make_expired


class TestCsrfToken(django.test.TestCase):

    def setUp(self):
        self.client.handler = ClientHandler()
        User.objects.create_user('jbalogh', 'j@moz.com', 'password')
        self.save_ANON_ALWAYS = conf.ANON_ALWAYS
        conf.ANON_ALWAYS = False

    def tearDown(self):
        conf.ANON_ALWAYS = self.save_ANON_ALWAYS

    def login(self):
        assert self.client.login(username='jbalogh', password='password')

    def test_csrftoken_unauthenticated(self):
        # request.csrf_token is '' for anonymous users.
        response = self.client.get('/', follow=True)
        self.assertEqual(response._request.csrf_token, '')

    def test_csrftoken_authenticated(self):
        # request.csrf_token is a random non-empty string for authed users.
        self.login()
        response = self.client.get('/', follow=True)
        # The CSRF token is a 32-character MD5 string.
        self.assertEqual(len(response._request.csrf_token), 32)

    def test_csrftoken_new_session(self):
        # The csrf_token is added to request.session the first time.
        self.login()
        response = self.client.get('/', follow=True)
        # The CSRF token is a 32-character MD5 string.
        token = response._request.session['csrf_token']
        self.assertEqual(len(token), 32)
        self.assertEqual(token, response._request.csrf_token)

    def test_csrftoken_existing_session(self):
        # The csrf_token in request.session is reused on subsequent requests.
        self.login()
        r1 = self.client.get('/', follow=True)
        token = r1._request.session['csrf_token']

        r2 = self.client.get('/', follow=True)
        self.assertEqual(r1._request.csrf_token, r2._request.csrf_token)
        self.assertEqual(token, r2._request.csrf_token)


class TestCsrfMiddleware(django.test.TestCase):

    def setUp(self):
        self.token = 'a' * 32
        self.rf = django.test.RequestFactory()
        self.mw = CsrfMiddleware()
        self._user = User.objects.create()

    def process_view(self, request, view=None):
        request.session = {}
        return self.mw.process_view(request, view, None, None)

    def test_anon_token_from_cookie(self):
        rf = django.test.RequestFactory()
        rf.cookies[conf.ANON_COOKIE] = self.token
        cache.set(prep_key(self.token), 'woo')
        request = rf.get('/')
        SessionMiddleware().process_request(request)
        AuthenticationMiddleware().process_request(request)
        self.mw.process_request(request)
        self.assertEqual(request.csrf_token, 'woo')

    def test_set_csrftoken_once(self):
        # Make sure process_request only sets request.csrf_token once.
        request = self.rf.get('/')
        request.csrf_token = 'woo'
        self.mw.process_request(request)
        self.assertEqual(request.csrf_token, 'woo')

    def test_reject_view(self):
        # Check that the reject view returns a 403.
        response = self.process_view(self.rf.post('/'))
        self.assertEqual(response.status_code, 403)

    def test_csrf_exempt(self):
        # Make sure @csrf_exempt still works.
        view = type("", (), {'csrf_exempt': True})()
        self.assertEqual(self.process_view(self.rf.post('/'), view), None)

    def test_safe_whitelist(self):
        # CSRF should not get checked on these methods.
        self.assertEqual(self.process_view(self.rf.get('/')), None)
        self.assertEqual(self.process_view(self.rf.head('/')), None)
        self.assertEqual(self.process_view(self.rf.options('/')), None)

    def test_unsafe_methods(self):
        self.assertEqual(self.process_view(self.rf.post('/')).status_code,
                         403)
        self.assertEqual(self.process_view(self.rf.put('/')).status_code,
                         403)
        self.assertEqual(self.process_view(self.rf.delete('/')).status_code,
                         403)

    def test_csrfmiddlewaretoken(self):
        # The user token should be found in POST['csrfmiddlewaretoken'].
        request = self.rf.post('/', {'csrfmiddlewaretoken': self.token})
        self.assertEqual(self.process_view(request).status_code, 403)

        request.csrf_token = self.token
        self.assertEqual(self.process_view(request), None)

    def test_x_csrftoken(self):
        # The user token can be found in the X-CSRFTOKEN header.
        request = self.rf.post('/', HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(self.process_view(request).status_code, 403)

        request.csrf_token = self.token
        self.assertEqual(self.process_view(request), None)

    def test_require_request_token_or_user_token(self):
        # Blank request and user tokens raise an error on POST.
        request = self.rf.post('/', HTTP_X_CSRFTOKEN='')
        request.csrf_token = ''
        self.assertEqual(self.process_view(request).status_code, 403)

    def test_token_no_match(self):
        # A 403 is returned when the tokens don't match.
        request = self.rf.post('/', HTTP_X_CSRFTOKEN='woo')
        request.csrf_token = ''
        self.assertEqual(self.process_view(request).status_code, 403)

    def test_csrf_token_context_processor(self):
        # Our CSRF token should be available in the template context.
        request = mock.Mock()
        request.csrf_token = self.token
        request.groups = []
        ctx = {}
        for processor in context.get_standard_processors():
            ctx.update(processor(request))
        self.assertEqual(ctx['csrf_token'], self.token)

    def _authenticated_request(self, token=None, **kwargs):
        """Create mocked request object for authenticated user"""
        self._user.is_authenticated = lambda: True
        if token is None:
            token = Token.objects.create(owner=self._user).value
        return mock.MagicMock(
            csrf_token=token,
            user=self._user,
            POST={},
            META={'HTTP_X_CSRFTOKEN': token},
            csrf_processing_done=False,
            _dont_enforce_csrf_checks=False,
            **kwargs)

    def test_reject_for_wrong_token_if_authenticated(self):
        """Test reject for wrong token if authenticated"""
        request = self._authenticated_request('wrong')
        self.assertIsNotNone(self.process_view(request))

    def test_reject_when_token_expired(self):
        """Test reject when csrf token expired"""
        token = make_expired(Token.objects.create(owner=self._user))
        request = self._authenticated_request(token.value)
        self.assertIsNotNone(self.process_view(request))

    def test_accept_when_token_is_ok(self):
        """Test accept when token is ok"""
        request = self._authenticated_request()
        self.assertIsNone(self.process_view(request))

    def test_renew_csrf_token_on_request_if_expired(self):
        """Test renew csrf token on request if expired"""
        token = make_expired(Token.objects.create(owner=self._user))
        request = self._authenticated_request(token.value, session={
            'csrf_token': token.value,
        })
        del request.csrf_token
        self.mw.process_request(request)
        self.assertNotEqual(token.value, request.csrf_token)

    def test_not_change_csrf_token_on_request_if_valid(self):
        """Test not change csrf token on request if valid"""
        request = self._authenticated_request()
        token = request.csrf_token
        request.session = {
            'csrf_token': token,
        }
        del request.csrf_token
        self.mw.process_request(request)
        self.assertEqual(token, request.csrf_token)

    def test_add_csrf_token_on_request(self):
        """Test add csrf token on request"""
        request = self._authenticated_request()
        del request.csrf_token
        self.mw.process_request(request)
        self.assertIsNotNone(request.csrf_token)
