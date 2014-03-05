from datetime import datetime
from django.db import models
from django.middleware.csrf import _get_new_csrf_key
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from . import conf


class TokenManager(models.Manager):
    """Token manager"""

    @property
    def _expiration_date(self):
        return datetime.now() - conf.CSRF_TOKEN_LIFETIME

    def get_expired(self):
        """Get expired tokens"""
        return self.filter(created__lt=self._expiration_date)

    def has_valid(self, owner, value, for_view=None):
        """Has valid token with user and value"""
        return self.filter(
            owner=owner, value=value, for_view=for_view,
            created__gte=self._expiration_date,
        ).exists()


class Token(models.Model):
    """Storage for csrf tokens"""
    value = models.CharField(max_length=32, verbose_name=_('token value'))
    owner = models.ForeignKey(User, verbose_name=_('owner'))
    created = models.DateTimeField(
        auto_now_add=True, verbose_name=_('created'),
    )
    for_view = models.CharField(
        null=True, blank=True,
        max_length=255, verbose_name=_('for view'),
    )

    objects = TokenManager()

    def save(self, *args, **kwargs):
        """Generate token on first save"""
        if not self.id:
            self.value = _get_new_csrf_key()
        return super(Token, self).save(*args, **kwargs)

    def __unicode__(self):
        return '{}:{}'.format(self.owner, self.created)
