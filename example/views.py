from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from session_csrf.decorators import per_view_csrf
from session_csrf.models import Token


@login_required
def index(request):
    return render(request, 'index.html')


@login_required
def global_check(request):
    return render(request, 'global.html')


@login_required
@per_view_csrf
def per_view_check(request):
    Token.objects.all().delete()
    return render(request, 'per_view.html')
