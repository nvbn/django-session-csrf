import mock
import django.test
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from ..utils import prep_key
from .. import conf
from .base import ClientHandler


class TestAnonymousCsrf(django.test.TestCase):
    urls = 'session_csrf.tests'

    def setUp(self):
        self.token = 'a' * 32
        self.rf = django.test.RequestFactory()
        User.objects.create_user('jbalogh', 'j@moz.com', 'password')
        self.client.handler = ClientHandler(enforce_csrf_checks=True)
        self.save_ANON_ALWAYS = conf.ANON_ALWAYS
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
        key = response.cookies[conf.ANON_COOKIE].value
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))

    def test_existing_anon_cookie_on_request(self):
        # We reuse an existing anon cookie key+token.
        response = self.client.get('/anon')
        key = response.cookies[conf.ANON_COOKIE].value
        # Now check that subsequent requests use that cookie.
        response = self.client.get('/anon')
        self.assertEqual(response.cookies[conf.ANON_COOKIE].value, key)
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))

    def test_new_anon_token_on_response(self):
        # The anon cookie is sent and we vary on Cookie.
        response = self.client.get('/anon')
        self.assertIn(conf.ANON_COOKIE, response.cookies)
        self.assertEqual(response['Vary'], 'Cookie')

    def test_existing_anon_token_on_response(self):
        # The anon cookie is sent and we vary on Cookie, reusing the old value.
        response = self.client.get('/anon')
        key = response.cookies[conf.ANON_COOKIE].value

        response = self.client.get('/anon')
        self.assertEqual(response.cookies[conf.ANON_COOKIE].value, key)
        self.assertIn(conf.ANON_COOKIE, response.cookies)
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
        key = response.cookies[conf.ANON_COOKIE].value
        self.assertEqual(response._request.csrf_token, cache.get(prep_key(key)))

    def test_existing_anon_cookie_on_request(self):
        # We reuse an existing anon cookie key+token.
        response = self.client.get('/')
        key = response.cookies[conf.ANON_COOKIE].value

        # Now check that subsequent requests use that cookie.
        response = self.client.get('/')
        self.assertEqual(response.cookies[conf.ANON_COOKIE].value, key)
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
