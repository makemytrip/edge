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

from django.shortcuts import render_to_response, HttpResponse, redirect, render
from django.contrib.auth.models import User
from django.template import RequestContext
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.views import View
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect, JsonResponse,HttpResponse
from django.views.generic import TemplateView, ListView, CreateView
from django_auth_ldap.backend import LDAPBackend
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser
from space.utils.dash import DashUtils
from space.utils.db_handler import DBHandler

from space.models import Space, Project, Env, ActionInfo, ActionStatus, Dendrogram, ActionQueue
from space.models import Plan as EPlan
from space.forms import SpaceForm, ProjectForm, EnvForm
from orchestration.tasks import action as orchestration_action, killing_task, action_zone as zone_action, closure_error_task
from orchestration.utils.elk_handler import ELKHandler
from orchestration.utils.edge_cache import EdgeCache
from orchestration.utils.jirautils import Jira
from orchestration.scripts.dc_deploy import DCDeploy
from orchestration.scripts.dc_deploy_non_f5 import DCDeployNonF5
from orchestration.scripts.micro_service import DCDeployMicroService
from orchestration.scripts.docker import DCDeployDocker
from orchestration.scripts.storm_deploy import StormDeploy
from orchestration.scripts.aws_deploy_mmt import AWSMmt
from orchestration.utils.generic_utils import separate_servers_by_zone, get_script_class_name

from space.serializers import ActionSerializer, ProjectSerializer, SpaceSerializer, EnvSerializer, DendrogramSerializer
from rest_framework import viewsets
from rest_framework.views import APIView

import logging,json

import time
from django.core import serializers


logger = logging.getLogger(__name__)


class Dash(View):
    def __init__(self):
        self.d = {}

    @method_decorator(login_required)
    def get(self, request, space_name=None):
        self.d['space_info'] = {}
        self.d['space_count'] = Space.objects.count()
        space_list = request.session.get('space_list', [])

        if space_name:
            try:
                self.d['space'] = Space.objects.get(name=space_name)
            except Space.DoesNotExist as e:
                logger.exception(e)
                return HttpResponseRedirect(reverse('dash'))

            self.d['space_project'] = Project.objects.filter(space__name=space_name)
            self.d['action_list'] = EPlan.objects.values_list('name', flat=True)
            self.d['hard_plans'] = ["hard_deploy", "hard_rollback", "hard_restart"]

            return render(request, 'dash.html', self.d)
        else:
            
            self.d['project_list'] = Project.objects.filter(space__name__in=space_list).values_list('name', flat=True)
            action_info = ActionInfo.objects.filter(project__name__in=self.d['project_list'])

            for space in space_list:

                project_list = Project.objects.filter(space__name=space).values_list('name', flat=True)
                action_info = ActionInfo.objects.filter(project__name__in=project_list, status__name__in=['INPROGRESS', 'BUILDING'])
               
                self.d['space_info'][space] = [action_info.count(), project_list.count()]

            # self.d['space_dendro_info'] = space_dendro_info
            logger.info(self.d)

            return render(request,'home.html',self.d)



class LoadDendrogram(View):

    def __init__(self):
        self.d = {}

    @method_decorator(login_required)
    def get(self, request, space_name=None):
       
        self.d['space_info'] = {}
        self.d['space_count'] = Space.objects.count()
        space_list = request.session.get('space_list', [])

        space_dendro_info = {}

        query = Project.objects.filter(space__name__in=space_list).values_list('name', flat=True)
        self.d['project_list'] = Project.objects.filter(space__name__in=space_list).values_list('name', flat=True)
        action_info = ActionInfo.objects.filter(project__name__in=self.d['project_list'])

        for space in space_list:

            project_list = Project.objects.filter(space__name=space).values_list('name', flat=True)
            space_dendro_info[space] = {}
            projects = Project.objects.filter(space__name=space)
            dendro = Dendrogram.objects.filter(project__in=projects)
            for d in dendro:

                if not d.project.name in space_dendro_info[space].keys():
                    space_dendro_info[space][d.project.name] = {}
                if not d.version in space_dendro_info[space][d.project.name].keys():
                    space_dendro_info[space][d.project.name][d.version] = []

                space_dendro_info[space][d.project.name].get(d.version).append(d.server)
            self.d['space_info'][space] = [action_info.count(), project_list.count()]

        self.d['space_dendro_info'] = space_dendro_info

        logger.info(self.d)
        self.d['project_list'] = ProjectSerializer(query,many=True).data

        return JsonResponse(self.d)



class Plan(View):

    def __init__(self):
        self.d = {}
        self.api_resp = {}

    @method_decorator(login_required)
    def get(self, request, space_name=None, project_name=None, action=None):
        project_details = {}
        if space_name and project_name and action:
            self.d['space'] = Space.objects.get(name=space_name)
            self.d['project'] = Project.objects.get(name=project_name)
            self.d['action'] = action
            server_info = []
            try:
                server_info = DashUtils.get_server_object(self.d['project'])
                for pool in server_info:
                    dendro = Dendrogram.objects.filter(server__in=pool['servers'], project=self.d['project'])
                    for d in dendro:
                        project_details[d.server] = d.version
            except Exception as e:
                logger.exception(e)
                self.d['error'] = e
            self.d['server_info'] = server_info
            self.d['project_details'] = project_details
        return render(request, 'plan.html', self.d)

    def patch(self, request, space_name=None, project_name=None, action=None):
        STOP_TASK_STATUS = ['COMPLETED', 'REVOKED', 'MANUAL_FAILED']
        status = True
        code = 200
        error_message = None
        api_data={}
        try:
            api_data = json.loads(request.body)
            logger.info("data recieved%s" % api_data)
        except Exception, e:
            error_message="%s-%s" %("Unable to parse request params from Canary Response", str(e))
            logger.error(error_message)
            return JsonResponse({'status': False, 'code': 400, 'error': error_message}, status=400)

        try:
            task_id = api_data.get('task_id')
            if task_id is None:
                raise Exception("Action Info task id cannot be None.")
            zone = api_data.get('zone').upper()
            if zone is None or len(zone) == 0:
                raise Exception("Zone for Action Info task id - %s cannot be - %s" %(task_id, zone))
            task_status = api_data.get('task_status')
            action_info_obj = ActionInfo.objects.get(id=task_id)
        except Exception, e:
            error_message = "%s-%s" % ("Unable to parse response values from Canary Response", str(e))
            logger.error(error_message)
            return JsonResponse({'status': False, 'code': 400, 'error': error_message}, status=400)

        try:
            # We don't need to raise Exception here, need to fix
            if action_info_obj.status.name.upper() in STOP_TASK_STATUS:
                message = "Action Info Task Id - %s has already been completed" % task_id
                ELKHandler(task_id).write_logs(exception=message)
                return JsonResponse({'status': False, 'code': 400, 'error': message}, status=200)
            edge_cache_obj = EdgeCache(task_id, zone)
            data = edge_cache_obj.get()
            if data is None or len(data) == 0:
                raise Exception("Cache Miss - Data for task_id - %s not found in Cache" % task_id)
            current_staggered_label = data.get('current_staggered_label')
            if task_status is not True:
                status = False
                error_message = "Canary [%s] status is %s for staggered - %s, so not scheduling any further task"\
                                %(zone, task_status, current_staggered_label)
                raise Exception(error_message)
            else:
                script_name = action_info_obj.script_file_name
                staggered_batch = data.get('staggered_batch',"").split(",")
                current_staggered_label_index = staggered_batch.index(current_staggered_label)
                next_staggered_label = staggered_batch[current_staggered_label_index+1]
                edge_cache_obj.set(current_staggered_label=next_staggered_label)
                params = data.get('params', None)
                celery_task_id = zone_action.delay(action_info_obj.id, params, script_name)
                DBHandler().updateActionInfoTaskIds(task_id, celery_task_id)
                message = "Canary [%s] has status - %s for staggered label - %s, so scheduled task for " \
                          "label - %s" % (zone, task_status, current_staggered_label, next_staggered_label)
                ELKHandler(task_id).write_logs(exception=message, level='info')
        except Exception, e:
            status=False
            code = 500
            logger.exception(e)
            error_message = "%s - %s" % ("Unable to schedule Action Info Task after canary Response", str(e))
            logger.error(error_message)
            EdgeCache(task_id, zone).set(task_status='FAILED')
            """DBHandler().setActionInfoState(task_id, 'FAILED')
            Jira(action_info_obj.config_dict().get('jira_id')).update_transition("FAILED")"""
            closure_error_task(task_id=task_id)
            ELKHandler(task_id).write_logs(exception=error_message)
        finally:
            return JsonResponse({'status':status, 'code':code, 'error' : error_message}, status=200)

    def post(self, request, space_name=None, project_name=None, action=None):

        self.d['error'] = None
        self.resp_status = 200

        try:
            if space_name and project_name and action:
                self.d['space'] = Space.objects.get(name=space_name)
                self.d['project'] = Project.objects.get(name=project_name)
                self.d['action'] = EPlan.objects.get(name=action)
                self.d['servers'] = request.POST.getlist('servers', [])
                self.d['countdown'] = request.POST.get('countdown', 10)
                self.api_resp['project'] = project_name
                reason = request.POST.get('reason', None)
                if not request.user.is_authenticated:
                    api_data = JSONParser().parse(request).get('content')
                    logger.info("data recieved %s" % api_data)

                user = request.user if request.user.is_authenticated() else None
                if user is None:
                    try:
                        user = User.objects.get(username=api_data.get('user'))
                    except User.DoesNotExist as e:
                        user = LDAPBackend().populate_user(api_data.get('user'))
                    except Exception as e:
                        logger.exception(e)
                logger.debug("%s------%s" % (request.user.is_authenticated(), user))

                if not request.user.is_authenticated():
                    self.d['servers'] = api_data.get('servers', None)
                    self.d['countdown'] = api_data.get('countdown', 10)
                    if not self.d['servers'] or len(self.d['servers']) == 0:
                        logger.info('no servers found, calc servers')
                        server_info = DashUtils.get_server_object(self.d['project'])
                        servers = []
                        for info in server_info:
                            servers.extend(info.get('servers', []))

                        self.d['servers'] = list(set(servers))
                    elif self.d['servers'] is None or self.d['servers'] == "" or "" in self.d['servers']:
                        raise Exception('No servers selected in Jira')

                retries = 0
                dbobj = DBHandler()

                self.d['servers'] = list(set(self.d['servers']))
                try:
                    project_config = self.d['project'].config_dict()
                    
                    # Expecting user sends description as string through api
                    if reason is None:
                        reason = project_config.get("description", "Unknown Reason")

                    if type(reason) is not dict:
                        description = {}
                        for s in self.d['servers']:
                            description[s] = reason
                        # Adding/updating description in config & making new config    
                        project_config['description'] = description
                        new_config = json.dumps(project_config, indent=4)
                        # Saving new config
                        project = Project.objects.get(name=self.d['project'])
                        project.config = new_config
                        project.save()
                        logger.info("Successfully updated description for project - {project}".format(project=self.d['project']))
                    else:
                        # If it is already dict, assuming it is correct.
                        logger.info("Not updating description for project - {project}".format(project=self.d['project']))
                except Exception as e:
                    logger.info("Exception while updating description - {error} for project {project}".format(error=e,project=self.d['project']))
                active_servers = DashUtils().check_active_servers(self.d['servers'], self.d['space'].name, self.d['project'].name, self.d['action'].name)
                self.d['project'] = Project.objects.get(name=project_name)
                if len(self.d['servers']) > 0 and len(active_servers) > 0:
                    existing_queue_servers = DashUtils().check_existing_queue_servers(self.d['project'], self.d['space'], self.d['action'], self.d['servers'])
                    if len(existing_queue_servers) > 0:
                        raise Exception('Unable to perform action !!! There is already a task with similar action in queue.')
                    else:
                        # active_actions = []
                        conf = self.d['project'].total_config_dict()
                        jira_id = conf.get('jira_id')
                        conf['countdown'] = int(self.d['countdown'])
                        conf = json.dumps(conf)
                        get_queue = DashUtils().add_entry_to_action_queue(space=self.d['space'], project=self.d['project'], servers=self.d['servers'], action=self.d['action'], user=user, config=conf)
                        active_tasks = DashUtils().get_active_tasks(self.d['project'])
                        # active_actions = [active_actions + str(i) for i in active_tasks]
                        self.api_resp['queue_id'] = get_queue.id

                        try:
                            if jira_id:
                                host_uri=dbobj.getValue("edge_host")
                                # url="%s%s" %(host_uri, reverse('action', args=(self.d['space'].name, active_tasks[0])))
                                jira_msg = "Queued this task"
                                jira_obj = Jira(jira_id)
                                jira_obj.comment(str(jira_msg))
                        except Exception as e:
                            logger.exception(e)
                        raise AssertionError('Queued this task . Currently active task id - %s' % (active_tasks))
                if len(self.d['servers']) > 0:
                    # add entry to ActionInfo and redirect to action page
                    self.d['servers'] = json.dumps(self.d['servers'])

                    conf = self.d['project'].total_config_dict()
                    if self.d['action'].name in ["rollback", "hard_rollback"] and conf.get('rollback_version', None) is not None:
                        conf['version'] = conf.get('rollback_version', None)
                    elif self.d['action'].name in ["rollback", "hard_rollback"]:
                        raise ValueError("rollback version is mandatory for action %s" % (self.d['action'].name))
                    conf['countdown'] = int(self.d['countdown'])
                    conf = json.dumps(conf)

                    status = ActionStatus.objects.get(name='BUILDING')
                    script_file_name = self.d['project'].env.script_file_name

                    new_action = ActionInfo(project=self.d['project'], action=self.d['action'], servers=self.d['servers'],
                                            config=conf, user=user, status=status, script_file_name=script_file_name)
                    new_action.save()
                    logger.info("added a new action %s" % new_action.id)
                    self.d['action_id'] = new_action.id
                    self.api_resp['action_id'] = new_action.id
                    # call to backend tasks
                    task = orchestration_action.apply_async((new_action.id,), countdown=int(self.d['countdown']))
                    # Store Task Ids
                    new_action.task_ids = task.id
                    new_action.save()
                    if request.user.is_authenticated():
                        return HttpResponseRedirect(reverse('action', args=(space_name, new_action.id,)))
            else:
                raise ValueError('Insufficient data')

        except AssertionError as ae:
            logger.exception(ae)
            self.d['error'] = ae
            self.api_resp['error'] = str(ae)
            self.resp_status = 200

        except Exception as e:
            logger.exception(e)
            self.d['error'] = e
            self.api_resp['error'] = str(e)
            self.resp_status = 500

        if not request.user.is_authenticated():
            return JsonResponse(self.api_resp, status=self.resp_status)
        else:
            return render(request, 'plan.html', self.d)


class Wizard(View):

    def __init__(self):
        self.d = {
            'obj' : None,
            'form' : None,
            'action' : None,
            'msg' : None
        }
        self.forms_dict = {'space': SpaceForm, 'project': ProjectForm, 'env': EnvForm}
        self.models_dict = {'space': Space, 'project': Project, 'env': Env}

    @method_decorator(login_required)
    def get(self, request, form_obj='space', obj_id=None):
        self.d['obj'] = form_obj
        try:
            if obj_id:
                model_obj = self.models_dict[form_obj]
                record = model_obj.objects.get(id=obj_id)
            else:
                raise ValueError('Object id is None')
        except ValueError as e:
            self.d['form'] = self.forms_dict.get(form_obj, ProjectForm)
            self.d['action'] = 'create'
        except Exception as e:
            logger.exception(e)
            self.d['form'] = self.forms_dict.get(form_obj, ProjectForm)
            self.d['action'] = 'create'
            self.d['msg'] = e.message
        else:
            self.d['form'] = self.forms_dict.get(form_obj)(instance=record)
            self.d['action'] = "update"
        finally:
            return render(request, 'wizard.html', self.d)

    @method_decorator(login_required)
    def post(self, request, form_obj=None, obj_id=None):
        self.d['obj'] = form_obj
        self.d['action'] = request.POST.get('action') if request.POST.get('action') else 'create'

        # get correct form from the request object
        form = self.forms_dict.get(form_obj) if self.forms_dict.get(form_obj, None) else None
        if obj_id:
            model_obj = self.models_dict[form_obj]
            record = model_obj.objects.get(id=obj_id)
            form = form(request.POST, instance=record)
        else:
            form = form(request.POST)

        if form and form.is_valid():
            try:
                form.save()
                self.d['msg'] = "%s, %s: %s" % (self.d['action'], form_obj, form.cleaned_data['name'])
            except Exception as e:
                logger.exception(e)
                self.d['msg'] = e.message
        else:
            self.d['error'] = form.errors.as_json()

        self.d['form'] = form

        return render(request, 'wizard.html', self.d)


class Action(View):

    @method_decorator(login_required)
    def get(self, request, space_name=None, id=None):
        self.d = {}
        try:
            self.d['space'] = Space.objects.get(name=space_name)
            self.d['project'] = Project.objects.filter(space=self.d['space'])
            if id:
                self.d['action_info_list'] = ActionInfo.objects.filter(id=id)

                es = ELKHandler(id)
                self.d['basic_entries'] = es.read_action_entries(detailed=False)

                if request.user:
                    self.d['detailed_entries'] = es.read_action_entries(detailed=True)

                self.d['display'] = []
                for entry in self.d['basic_entries']:
                    if entry.get('category') == 'display' and entry['exception'] is not None:
                        self.d['display'].append({entry.get('level', 'error').upper(): entry.get('exception')})

                self.d['action_info_id'] = id

                class_name = get_script_class_name(self.d['action_info_list'][0].script_file_name)
                class_object = globals().get(class_name, None)
                script_obj = class_object(task_obj=self.d['action_info_list'][0])

                self.d['task_details'] = getattr(script_obj, 'get_task_details')(self.d['action_info_list'][0].action.name)

            else:
                self.d['action_info_list'] = ActionInfo.objects.filter(project__in=self.d['project']).order_by('-id')
        except Exception as e:
            self.d['error'] = e
            logger.exception(e)

        return render(request, 'action.html', self.d)

    @method_decorator(login_required)
    def post(self, request, space_name=None, id=None):
        self.d = {}
        self.data = {"draw": 1, "recordsTotal": 0, "recordsFiltered": 0, "data": []}

        try:
            if id:
                action_info = ActionInfo.objects.get(id=id)
                es = ELKHandler(id)
                # basic_entries = es.read_action_entries(detailed=False)
                detailed_entries = es.read_action_entries(detailed=True)

                data_table_info = []
                server_detail = {}

                for server in action_info.server_list():
                    list_info = {}
                    server_detail[server] = []

                    list_info['server'] = server

                    for entry in detailed_entries:
                        if entry['server'] == server:
                            task_info = {}
                            task_info[entry['task']] = {
                                'status': entry.get('status'),
                                'duration': entry.get('duration'),
                                'batch_count': entry.get('batch_count'),
                                'description': entry.get('description'),
                                'staggered_label': entry.get('staggered_label'),
                                'method': entry.get('method'),
                                'exception': entry.get('exception'),
                                'session': entry.get('session'),
                                'timestamp': entry.get('timestamp').split('.')[0].replace('T',' '),
                                'starttime': entry.get('starttime').split('.')[0].replace('T',' '),
                                'endtime': entry.get('endtime').split('.')[0].replace('T',' ')
                            }
                            server_detail[server].append(task_info)

                    list_info['details'] = server_detail[server]

                    data_table_info.append(list_info)

            self.data['data'] = data_table_info
            self.data['recordsTotal'] = len(data_table_info)
            self.data['recordsFiltered'] = len(data_table_info)

        except Exception as e:
            self.d['error'] = e
            logger.exception(e)

        return HttpResponse(json.dumps(self.data), content_type='application/json')


'''
    Rest APIs.
'''


class ActionAPI(View):
    def get(self, request, space_name=None, id=None, cmd=None):

        user = request.user
        if id and cmd.lower() == "revoke":
            killing_task(id, user=user, kill_action="MANUAL_FAILED")

        resp = {}
        if id:
            resp['display'] = []

            es = ELKHandler(id)
            basic_entries = es.read_action_entries(detailed=False)
            if len(basic_entries) > 0:
                for entry in basic_entries:
                    if entry.get('category') == 'display' and entry['exception'] is not None:
                        resp['display'].append({entry.get('level', 'error').upper(): entry.get('exception')})

            try:
                status = 200
                action_info = ActionInfo.objects.get(id=id)
                action_info = ActionSerializer(action_info, many=False)
                resp.update(action_info.data)
            except Exception as e:
                resp['status'] = "FAILED"
                resp['error'] = str(e)
                status = 404
            finally:
                return JsonResponse(resp, status=status, safe=True)

class EdgeAPI(APIView):
    modeldetail = {'space': Space, 'project': Project, 'env': Env}
    serializerdetail = {'space': SpaceSerializer, 'project': ProjectSerializer, 'env': EnvSerializer, 'dendrogram': DendrogramSerializer}

    def get(self, request, form_obj=None, name=None, format=None):
        try:
            many=False
            if str(name).strip().lower() == 'all':
                many=True
                queryset = self.modeldetail.get(form_obj).objects.all()
            else:
                queryset = self.modeldetail.get(form_obj).objects.get(name=name)
            serializer = self.serializerdetail.get(form_obj)(queryset, many=many)
            return JsonResponse(serializer.data, safe=False)
        except Exception, e:
            logger.error(e)
            return JsonResponse({}, status=404)

    def put(self, request, form_obj=None, name=None):
        try:
            data = JSONParser().parse(request).get('content')
            logger.debug("Data Receieved for put Api - %s" % data)
            obj = self.modeldetail.get(form_obj).objects.get(name=name)
            configs = obj.config_dict()
            configs.update(data)
            serializer = self.serializerdetail.get(form_obj)(obj, data={'config':json.dumps(configs, indent=4)})
            if serializer.is_valid():
                serializer.save()
                return JsonResponse(serializer.data)
            return JsonResponse(serializer.errors, status=400)
        except Exception,e:
            logger.error(e)
            return JsonResponse({}, status=404)

    def post(self, request, form_obj=None, name=None):
        try:
            server = request.POST.get('server', None)
            version = request.POST.get('version', None)

            queryset = Dendrogram().get_project_name(server, version)
            serializer = DendrogramSerializer(queryset, many=True)
            return JsonResponse(serializer.data, status=200, safe=False)
        except Exception, e:
            logger.exception(e)
            return JsonResponse({'message': str(e)}, status=404)

class DendrogramAPI(APIView):

    def get(self, request, server=None):
        try:
            server = request.GET.get('server', None)
            if server is not None:
                queryset = Dendrogram().get_project_name(server)
                serializer = DendrogramSerializer(queryset, many=True)
                return JsonResponse(serializer.data, status=200, safe=False)
            else:
                return JsonResponse({'message':'Not Found'}, status=404, safe=False)
        except Exception, e:
            logger.exception(e)
            return JsonResponse({'message': str(e)}, status=404)

    def post(self, request):
        try:
            req = json.loads(request.body)
            project_name = req.get('project_name', None)
            username = req.get('user', None)
            server = req.get('server', None)
            action = req.get('action', None)
            version = req.get('version', 'Unknown')
            if action is not None and server is not None:
                if action == 'add' and project_name is not None:
                    user = User.objects.get(username=username)
                    project = Project.objects.get(name=project_name)
                    dendro = Dendrogram(project=project, user=user, server=server, version=version)
                    dendro_id = dendro.save()
                    return JsonResponse({'result': True,'action':action,'id':dendro.id}, status=200, safe=True)
                elif action == 'remove':
                    Dendrogram.objects.filter(server=server).delete()
                    return JsonResponse({'result': True,'action':action,'user':username}, status=200, safe=True)
                else:
                    return JsonResponse({'result': False,'error':'Invalid Action'}, status=404, safe=True)
            else:
                return JsonResponse({'error':'Please provide valid values','configs':{'Project Name':project_name,'server':server,'action':action}}, status=404, safe=True)
        except Exception, e:
            logger.exception(e)
            return JsonResponse({'message': str(e)}, status=500)

class Doc(View):

    def get(self, request, md_file=None):
        self.d = {}
        if md_file:
            return render(request, md_file + '.html', self.d)

class FetchprojectAPI(View):

    def get(self, request):
        for name, value in request.GET.items():
            search_term = name
            search_value = value
        logger.debug("Data Receieved for post Fetch Project Api - %s" % search_value)
        queryset = Project().get_projects(search_term, search_value)
        if queryset:
            serializer = ProjectSerializer(queryset, many=True)
            return JsonResponse(serializer.data, status=200, safe=False)
        else:
            return JsonResponse({'error':'Not Found'}, status=404, safe=False)

class FetchfqdnAPI(View):

    def get(self, request):
        pool_name = request.GET.get('pool')
        dc = request.GET.get('dc')
        entries = DashUtils().get_fqdn_from_pool(pool_name,dc)
        if len(entries):
            serializer = ProjectSerializer(entries, many=True)
            return JsonResponse(serializer.data, status=200, safe=False)
        else:
            return JsonResponse({'error':'Not Found'}, status=404, safe=False)
