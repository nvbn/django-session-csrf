from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from session_csrf.decorators import per_view_csrf
from session_csrf.mixins import PerViewCsrfMixin
from session_csrf.models import Token


@login_required
def index(request):
    return render(request, 'index.html')


def global_check(request):
    return render(request, 'global.html')


@per_view_csrf
def per_view_check(request):
    Token.objects.all().delete()
    return render(request, 'per_view.html')


class PerViewCheck(PerViewCsrfMixin, TemplateView):
    template_name = 'per_view_cbv.html'

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)
