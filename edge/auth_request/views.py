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

from django.shortcuts import render_to_response, HttpResponse, redirect
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, login, logout
from django.views import View
from django.conf import settings
from django.template import RequestContext
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from space.models import Space, Env
from space.utils.dash import DashUtils

from auth_request.myLdapAuth import AuthLdap

import logging, requests, json

import time

logger = logging.getLogger(__name__)


class EdgeLogin(View):

    def post(self, request):

        d = {'msg': None}
        if request and not isinstance(request, User):

            if request.POST:
                user = authenticate(username=request.POST.get('user_id'), password=request.POST.get('password'))
                logger.info("User - %s, Request is authenticated %s" % (user, request.user.is_authenticated))

                if user is not None:
                    logger.info("User logged in - %s, next redirection %s" % (user.username, request.GET.get('next')))
                    login(request, user)

                    # setting the session variables
                    space_list = []
                    space_permissions = {}
                    env_details = []
                    if user.is_superuser:
                        logger.debug("user - %s is super user, so adding all spaces and environments" % user.username)
                        for space_obj in Space.objects.all():
                            space_list.append(space_obj.name)
                            space_permissions[space_obj.name] = {}
                            space_permissions[space_obj.name]['admin'] = True
                        env_details = list(Env.objects.all().order_by('name').values('id', 'name'))
                    else:
                        user_member_list = set(AuthLdap().getusermember(user.username))
                        for space_obj in Space.objects.all():
                            space_permissions[space_obj.name] = {}
                            operator_dl = space_obj.operator_dl.split(',')
                            operator_dl = list(set([dl.split('@')[0].strip().lower() for dl in operator_dl]))
                            logger.debug("Operator DL for Space - %s is %s" %(space_obj.name, operator_dl))
                            if set(operator_dl).intersection(user_member_list):
                                space_list.append(space_obj.name)
                                space_permissions[space_obj.name]['operator'] = True
                            admin_dl = space_obj.admin_dl.split(',')
                            admin_dl = list(set([dl.split('@')[0].strip() for dl in admin_dl]))
                            logger.debug("Admin DL for Space - %s is %s" % (space_obj.name, admin_dl))
                            if set(admin_dl).intersection(set(user_member_list)):
                                space_list.append(space_obj.name)
                                space_permissions[space_obj.name]['admin'] = True
                    DashUtils.update_session(request, 'username', user.username)
                    space_list=list(set(space_list))
                    space_list.sort()
                    DashUtils.update_session(request, 'env', env_details)
                    DashUtils.update_session(request, 'space_list', space_list)
                    DashUtils.update_session(request, 'space_permissions', space_permissions)

                    redirect_url = request.GET.get('next') if request.GET.get('next') else '/'

                    return redirect(redirect_url)
                else:
                    d['msg'] = 'Invalid Login, Do try again'


        return render_to_response('login.html', d, RequestContext(request))

    def get(self, request):
        d = {'msg': None}
        return render_to_response('login.html', d, RequestContext(request))


class EdgeLogout(View):

    @method_decorator(login_required)
    def get(self, request):
        logout(request)
        return redirect('/space/login', name='login')
