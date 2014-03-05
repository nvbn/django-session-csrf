from django.conf.urls.defaults import patterns, include, url
from django.contrib import admin


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'views.index'),
    url(r'^global/$', 'views.global_check'),
    url(r'^per-view/$', 'views.per_view_check'),
    url(r'^admin/', include(admin.site.urls)),
)
