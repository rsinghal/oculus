from django.conf.urls import patterns, url

from manifests import views

urlpatterns = patterns('',
    url(r'^view/(?P<document_id>([a-z]+:[A-Za-z\d]+;?)+)$', views.view, name='view'),

    url(r'^(?P<document_id>[a-z]+:[A-Za-z\d]+)$', views.manifest, name='manifest'),

    url(r'^delete/(?P<document_id>[a-z]+:[A-Za-z\d]+)$', views.delete, name='delete'),

    url(r'^refresh/(?P<document_id>[a-z]+:[A-Za-z\d]+)$', views.refresh, name='refresh'),

    # probably won't find a better solution for images because won't actually serve 
    # HTML pages with mirador out of django (it's just for testing/demo purposes)
    url(r'^view/images/openseadragon/(?P<filename>.*)$', views.get_image), 
)
