from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'oculus.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^manifests/', include('manifests.urls')),
    url(r'^lti_init/', include('hx_lti_initializer.urls', namespace="hx_lti_intializer")),
    url(r'^admin/', include(admin.site.urls)),
)
