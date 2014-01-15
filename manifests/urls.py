from django.conf.urls import patterns, url

from manifests import views

urlpatterns = patterns('',
    url(r'^view/mets/(?P<document_id>[A-Za-z\d;]+)$', views.view_mets, name='view_mets'),
    url(r'^view/mods/(?P<document_id>[A-Za-z\d;]+)$', views.view_mods, name='view_mods'),
    url(r'^mets/(?P<document_id>[A-Za-z\d]+)$', views.manifest_mets, name='manifest_mets'),
    url(r'^mods/(?P<document_id>[A-Za-z\d]+)$', views.manifest_mods, name='manifest_mods'),
    url(r'^delete/(?P<document_id>[A-Za-z\d]+)$', views.delete, name='delete'),
    url(r'^refresh/mets/(?P<document_id>[A-Za-z\d]+)$', views.refresh_mets, name='refresh_mets'),
    url(r'^refresh/mods/(?P<document_id>[A-Za-z\d]+)$', views.refresh_mods, name='refresh_mods'),
    url(r'^refresh/mets/all$', views.refresh_mets_all, name='refresh_mets_all'),
    url(r'^refresh/mods/all$', views.refresh_mods_all, name='refresh_mods_all'),
    url(r'^refresh/all$', views.refresh_all, name='refresh_all'),
    url(r'^view/(mets|mods)/images/openseadragon/(?P<filename>.*)$', views.get_image), # hack to deal with this problem
)
