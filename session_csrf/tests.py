from datetime import datetime, timedelta
import django.test
from django import http
try:
    from django.conf.urls import patterns
except ImportError:
    from django.conf.urls.defaults import patterns
from django.contrib.auth import logout
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.models import Session
from django.core import signals
from django.core.cache import cache
from django.core.handlers.wsgi import WSGIRequest
from django.db import close_connection
from django.template import context

import mock

import session_csrf
from session_csrf import (
    anonymous_csrf, anonymous_csrf_exempt,
    CsrfMiddleware, prep_key,
    ANON_COOKIE,
)
from session_csrf import conf
from session_csrf.models import Token


urlpatterns = patterns('',
    ('^$', lambda r: http.HttpResponse()),
    ('^anon$', anonymous_csrf(lambda r: http.HttpResponse())),
    ('^no-anon-csrf$', anonymous_csrf_exempt(lambda r: http.HttpResponse())),
    ('^logout$', anonymous_csrf(lambda r: logout(r) or http.HttpResponse())),
)


def _make_expired(token):
    """Make token expired"""
    token.created =\
        datetime.now() - conf.CSRF_TOKEN_LIFETIME - timedelta(days=1)
    token.save()
    return token


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

    def process_view(self, request, view=None):
        request.session = {}
        return self.mw.process_view(request, view, None, None)

    def test_anon_token_from_cookie(self):
        rf = django.test.RequestFactory()
        rf.cookies[ANON_COOKIE] = self.token
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

    def _authenticated_request(self, user, token=None, **kwargs):
        """Create mocked request object for authenticated user"""
        user.is_authenticated = lambda: True
        if token is None:
            token = Token.objects.create(owner=user).value
        return mock.MagicMock(
            csrf_token=token,
            user=user,
            POST={},
            META={'HTTP_X_CSRFTOKEN': token},
            csrf_processing_done=False,
            _dont_enforce_csrf_checks=False,
            **kwargs)

    def test_reject_for_wrong_token_if_authenticated(self):
        """Test reject for wrong token if authenticated"""
        user = User.objects.create()
        request = self._authenticated_request(user, 'wrong')
        self.assertIsNotNone(self.process_view(request))

    def test_reject_when_token_expired(self):
        """Test reject when csrf token expired"""
        user = User.objects.create()
        token = _make_expired(Token.objects.create(owner=user))
        request = self._authenticated_request(user, token.value)
        self.assertIsNotNone(self.process_view(request))

    def test_accept_when_token_is_ok(self):
        """Test accept when token is ok"""
        user = User.objects.create()
        request = self._authenticated_request(user)
        self.assertIsNone(self.process_view(request))


class TestAnonymousCsrf(django.test.TestCase):
    urls = 'session_csrf.tests'

    def setUp(self):
        self.token = 'a' * 32
        self.rf = django.test.RequestFactory()
        User.objects.create_user('jbalogh', 'j@moz.com', 'password')
        self.client.handler = ClientHandler(enforce_csrf_checks=True)
        self.save_ANON_ALWAYS = session_csrf.ANON_ALWAYS
        conf.ANON_ALWAYS = False

    def tearDown(self):
        conf.ANON_ALWAYS = self.save_ANON_ALWAYS

    def login(self):
        assert self.client.login(username='jbalogh', password='password')

    def test_authenticated_request(self):
        # Nothing special happens, nothing breaks.
        # Find the CSRF token in the session.
        self.login()
        response = self.client.get('/anon')
        sessionid = response.cookies['sessionid'].value
        session = Session.objects.get(session_key=sessionid)
        token = session.get_decoded()['csrf_token']

        response = self.client.post('/anon', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_request(self):
        # We get a 403 since we're not sending a token.
        response = self.client.post('/anon')
        self.assertEqual(response.status_code, 403)

    def test_no_anon_cookie(self):
        # We don't get an anon cookie on non-@anonymous_csrf views.
        response = self.client.get('/')
        self.assertEqual(response.cookies, {})

    def test_new_anon_token_on_request(self):
        # A new anon user gets a key+token on the request and response.
        response = self.client.get('/anon')
        # Get the key from the cookie and find the token in the cache.
        key = response.cookies[ANON_COOKIE].value
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))

    def test_existing_anon_cookie_on_request(self):
        # We reuse an existing anon cookie key+token.
        response = self.client.get('/anon')
        key = response.cookies[ANON_COOKIE].value
        # Now check that subsequent requests use that cookie.
        response = self.client.get('/anon')
        self.assertEqual(response.cookies[ANON_COOKIE].value, key)
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))

    def test_new_anon_token_on_response(self):
        # The anon cookie is sent and we vary on Cookie.
        response = self.client.get('/anon')
        self.assertIn(ANON_COOKIE, response.cookies)
        self.assertEqual(response['Vary'], 'Cookie')

    def test_existing_anon_token_on_response(self):
        # The anon cookie is sent and we vary on Cookie, reusing the old value.
        response = self.client.get('/anon')
        key = response.cookies[ANON_COOKIE].value

        response = self.client.get('/anon')
        self.assertEqual(response.cookies[ANON_COOKIE].value, key)
        self.assertIn(ANON_COOKIE, response.cookies)
        self.assertEqual(response['Vary'], 'Cookie')

    def test_anon_csrf_logout(self):
        # Beware of views that logout the user.
        self.login()
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 200)

    def test_existing_anon_cookie_not_in_cache(self):
        response = self.client.get('/anon')
        self.assertEqual(len(response._request.csrf_token), 32)

        # Clear cache and make sure we still get a token
        cache.clear()
        response = self.client.get('/anon')
        self.assertEqual(len(response._request.csrf_token), 32)

    def test_anonymous_csrf_exempt(self):
        response = self.client.post('/no-anon-csrf')
        self.assertEqual(response.status_code, 200)

        self.login()
        response = self.client.post('/no-anon-csrf')
        self.assertEqual(response.status_code, 403)


class TestAnonAlways(django.test.TestCase):
    # Repeats some tests with ANON_ALWAYS = True
    urls = 'session_csrf.tests'

    def setUp(self):
        self.token = 'a' * 32
        self.rf = django.test.RequestFactory()
        User.objects.create_user('jbalogh', 'j@moz.com', 'password')
        self.client.handler = ClientHandler(enforce_csrf_checks=True)
        self.save_ANON_ALWAYS = conf.ANON_ALWAYS
        conf.ANON_ALWAYS = True

    def tearDown(self):
        conf.ANON_ALWAYS = self.save_ANON_ALWAYS

    def login(self):
        assert self.client.login(username='jbalogh', password='password')

    def test_csrftoken_unauthenticated(self):
        # request.csrf_token is set for anonymous users
        # when ANON_ALWAYS is enabled.
        response = self.client.get('/', follow=True)
        # The CSRF token is a 32-character MD5 string.
        self.assertEqual(len(response._request.csrf_token), 32)

    def test_authenticated_request(self):
        # Nothing special happens, nothing breaks.
        # Find the CSRF token in the session.
        self.login()
        response = self.client.get('/', follow=True)
        sessionid = response.cookies['sessionid'].value
        session = Session.objects.get(session_key=sessionid)
        token = session.get_decoded()['csrf_token']

        response = self.client.post('/', follow=True, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_request(self):
        # We get a 403 since we're not sending a token.
        response = self.client.post('/')
        self.assertEqual(response.status_code, 403)

    def test_new_anon_token_on_request(self):
        # A new anon user gets a key+token on the request and response.
        response = self.client.get('/')
        # Get the key from the cookie and find the token in the cache.
        key = response.cookies[ANON_COOKIE].value
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))

    def test_existing_anon_cookie_on_request(self):
        # We reuse an existing anon cookie key+token.
        response = self.client.get('/')
        key = response.cookies[ANON_COOKIE].value

        # Now check that subsequent requests use that cookie.
        response = self.client.get('/')
        self.assertEqual(response.cookies[ANON_COOKIE].value, key)
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))
        self.assertEqual(response['Vary'], 'Cookie')

    def test_anon_csrf_logout(self):
        # Beware of views that logout the user.
        self.login()
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 200)

    def test_existing_anon_cookie_not_in_cache(self):
        response = self.client.get('/')
        self.assertEqual(len(response._request.csrf_token), 32)

        # Clear cache and make sure we still get a token
        cache.clear()
        response = self.client.get('/')
        self.assertEqual(len(response._request.csrf_token), 32)

    def test_massive_anon_cookie(self):
        # if the key + PREFIX + setting prefix is greater than 250
        # memcache will cry and you get a warning if you use LocMemCache
        junk = 'x' * 300
        with mock.patch('warnings.warn') as warner:
            response = self.client.get('/', HTTP_COOKIE='anoncsrf=%s' % junk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(warner.call_count, 0)

    def test_surprising_characters(self):
        c = 'anoncsrf="|dir; multidb_pin_writes=y; sessionid="gAJ9cQFVC'
        with mock.patch('warnings.warn') as warner:
            response = self.client.get('/', HTTP_COOKIE=c)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(warner.call_count, 0)


class ClientHandler(django.test.client.ClientHandler):
    """
    Handler that stores the real request object on the response.

    Almost all the code comes from the parent class.
    """

    def __call__(self, environ):
        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        if self._request_middleware is None:
            self.load_middleware()

        signals.request_started.send(sender=self.__class__)
        try:
            request = WSGIRequest(environ)
            # sneaky little hack so that we can easily get round
            # CsrfViewMiddleware.  This makes life easier, and is probably
            # required for backwards compatibility with external tests against
            # admin views.
            request._dont_enforce_csrf_checks = not self.enforce_csrf_checks
            response = self.get_response(request)
        finally:
            signals.request_finished.disconnect(close_connection)
            signals.request_finished.send(sender=self.__class__)
            signals.request_finished.connect(close_connection)

        # Store the request object.
        response._request = request
        return response


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
            _make_expired(Token.objects.create(owner=self._user))
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
        _make_expired(token)
        self.assertFalse(
            Token.objects.has_valid(self._user, token.value),
        )
