# Copyright 2018 MakeMyTrip (Paritosh Anand)
#
# This file is part of edge.
#
# edge is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dataShark.  If not, see <http://www.gnu.org/licenses/>.

from django.conf.urls import include, url
from space.views import Dash, Plan, Wizard, Action, ActionAPI, EdgeAPI, FetchprojectAPI, Doc, DendrogramAPI,LoadDendrogram,FetchfqdnAPI
from auth_request.views import EdgeLogin, EdgeLogout
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^$',Dash.as_view(), name='dash'),
    url(r'^login/$', EdgeLogin.as_view(), name='edge_login'),
    url(r'^logout/$', EdgeLogout.as_view(), name='edge_logout'),
    url(r'^doc/(?P<md_file>[a-zA-Z].*)/$', Doc.as_view(), name='doc'),

    url(r'^loadDendrogram/$',LoadDendrogram.as_view(),name='load_dendro'),

    url(r'^wizard/fetch_project/api/$', FetchprojectAPI.as_view(), name='fetchproject_api'),
    url(r'^wizard/fetch_fqdn/api/$', FetchfqdnAPI.as_view(), name='FetchfqdnAPI'),
    url(r'^wizard/dendrogram/api/$', DendrogramAPI.as_view(), name='dendrogram_api'),
    url(r'^wizard/(?P<form_obj>.+?)/(?P<obj_id>[0-9].*)/$', Wizard.as_view(), name='wizard'),
    url(r'^wizard/(?P<form_obj>.+?)/api/(?P<name>[a-zA-Z].*)/$', EdgeAPI.as_view(), name='edge-api'),
    url(r'^wizard/(?P<form_obj>.*?)/$', Wizard.as_view(), name='wizard'),

    url(r'^action/(?P<space_name>.+?)/(?P<id>.+?)/(?P<cmd>.+?)/$', ActionAPI.as_view(), name='action_api'),
    url(r'^action/(?P<space_name>.+?)/(?P<id>.+?)/$', Action.as_view(), name='action'),
    url(r'^action/(?P<space_name>.+?)/$', Action.as_view(), name='action'),

    # url(r'^report/(?P<space_name>.+?)/(?P<project_name>.+?)/$', Report.as_view(), name='report'),

    url(r'^(?P<space_name>.+?)/(?P<project_name>.+?)/(?P<action>.+?)/$', Plan.as_view(), name='plan'),
    url(r'^(?P<space_name>.+?)/$', Dash.as_view(), name='dash'),

]
