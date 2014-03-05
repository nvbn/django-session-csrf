from django.conf.urls.defaults import patterns, include, url
from django.contrib import admin
from .views import PerViewCheck


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'views.index'),
    url(r'^global/$', 'views.global_check'),
    url(r'^per-view/$', 'views.per_view_check'),
    url(r'^per-view-cbv/$', PerViewCheck.as_view()),
    url(r'^admin/', include(admin.site.urls)),
)
