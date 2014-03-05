from datetime import datetime, timedelta
import django.test.client
try:
    from django.conf.urls import patterns
except ImportError:
    from django.conf.urls.defaults import patterns
from django import http
from django.contrib.auth import logout
from django.core import signals
from django.core.handlers.wsgi import WSGIRequest
from django.db import close_connection
from ..decorators import anonymous_csrf, anonymous_csrf_exempt
from .. import conf


urlpatterns = patterns('',
    ('^$', lambda r: http.HttpResponse()),
    ('^anon$', anonymous_csrf(lambda r: http.HttpResponse())),
    ('^no-anon-csrf$', anonymous_csrf_exempt(lambda r: http.HttpResponse())),
    ('^logout$', anonymous_csrf(lambda r: logout(r) or http.HttpResponse())),
)


def make_expired(token):
    """Make token expired"""
    token.created =\
        datetime.now() - conf.CSRF_TOKEN_LIFETIME - timedelta(days=1)
    token.save()
    return token


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
