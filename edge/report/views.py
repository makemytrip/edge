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

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.views import View
from django.shortcuts import render_to_response, HttpResponse, redirect, render
from django.contrib.auth.models import User
from django.template import RequestContext
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from datetime import timedelta

from space.models import Project, Space, ActionInfo, Configs, Plan, ActionStatus

import logging, requests, json


logger = logging.getLogger(__name__)


class Report(View):

    @method_decorator(login_required)
    def get(self, request):

        self.d = {}
        return render(request, 'report.html', self.d)


class ReportPerSpace(View):

    @method_decorator(login_required)
    def get(self, request, space_name=None):

        self.d = {}
        try:
            self.d['search_project'] = request.GET.getlist('project', [])
            self.d['search_status'] = request.GET.getlist('status', [])
            self.d['search_days'] = request.GET.get('days')
            self.d['search_plan'] = request.GET.getlist('plan', [])
            self.d['search_user'] = request.GET.getlist('user', [])

            if space_name.lower() == 'all':
                self.d['space'] = Space.objects.filter(name__in=request.session.get('space_list'))
            else:
                self.d['space'] = Space.objects.filter(name=space_name)

            self.d['days'] = Configs().getValue('report_days')
            self.d['project_list'] = Project.objects.filter(space__in=self.d['space']).values_list('name', flat=True)
            self.d['plan_list'] = Plan.objects.all().values_list('name', flat=True)
            self.d['status_list'] = ActionStatus.objects.all().values_list('name', flat=True)
            self.d['user_list'] = User.objects.all().order_by('first_name')

            self.d['s_days'] = self.d['days'][0]
            if self.d['search_days']:
                self.d['s_days'] = int(self.d['search_days'])

            s_project_list = self.d['project_list']
            if len(self.d['search_project']) > 0:
                s_project_list = list(set(self.d['project_list']).intersection(set(self.d['search_project'])))

            s_plan = self.d['plan_list']
            if len(self.d['search_plan']) > 0:
                s_plan = list(set(self.d['plan_list']).intersection(set(self.d['search_plan'])))

            s_status = self.d['status_list']
            if len(self.d['search_status']) > 0:
                s_status = list(set(self.d['status_list']).intersection(set(self.d['search_status'])))

            s_user = self.d['user_list'].values_list('username', flat=True)
            if len(self.d['search_user']) > 0:
                s_user = list(set(self.d['user_list'].values_list('username', flat=True)).intersection(set(self.d['search_user'])))

            if self.d['project_list']:
                self.d['action_info_list'] = ActionInfo.objects.filter(project__name__in=s_project_list, action__name__in=s_plan, status__name__in=s_status, user__username__in=s_user, timestamp__gte=timezone.now()-timedelta(days=self.d['s_days'])).order_by('-id')

        except Exception as e:
            self.d['error'] = e
            logger.exception(e)
        return render(request, 'report_per_space.html', self.d)
