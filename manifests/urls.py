from django.conf.urls import patterns, url

from manifests import views

urlpatterns = patterns('',
    url(r'^(?P<view_type>view(-dev|-annotator)?)/(?P<document_id>([a-z]+:[A-Za-z\d]+;?)+)$', views.view, name='view'),

    url(r'^(?P<document_id>[a-z]+:[A-Za-z\d]+)$', views.manifest, name='manifest'),

    url(r'^delete/(?P<document_id>[a-z]+:[A-Za-z\d]+)$', views.delete, name='delete'),

    url(r'^refresh/(?P<document_id>[a-z]+:[A-Za-z\d]+)$', views.refresh, name='refresh'),
    url(r'^refresh/source/(?P<source>[a-z]+)$', views.refresh_by_source, name='refresh_by_source'),

    # probably won't find a better solution for images because won't actually serve 
    # HTML pages with mirador out of django (it's just for testing/demo purposes)
    url(r'^(?P<view_type>view(-dev|-annotator)?)/images/openseadragon/(?P<filename>.*)$', views.get_image), 
    url(r'^(?P<view_type>view(-dev|-annotator)?)//.*$', views.clean_url), 
)
