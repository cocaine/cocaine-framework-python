from django.conf.urls import patterns, url

import spock.views

urlpatterns = patterns('',
    url(r'^apps/$', spock.views.apps),
    url(r'^info/$', spock.views.info),
)
