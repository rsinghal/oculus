from django.conf.urls import patterns, url

from manifests import views

urlpatterns = patterns('',
    url(r'^(?P<document_id>\d+)$', views.manifest, name='manifest'),
    url(r'^delete/(?P<document_id>\d+)$', views.delete, name='delete')
)
