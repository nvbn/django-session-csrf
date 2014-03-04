# This overrides django.core.context_processors.csrf to dump our csrf_token
# into the template context.
def context_processor(request):
    # Django warns about an empty token unless you call it NOTPROVIDED.
    return {'csrf_token': getattr(request, 'csrf_token', 'NOTPROVIDED')}
