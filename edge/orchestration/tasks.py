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

from __future__ import absolute_import, unicode_literals
from django.core.urlresolvers import reverse
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.conf import settings
from celery.result import AsyncResult
from django.utils.timezone import localtime
import logging, time, requests

import json, os, jinja2

from celery import shared_task, chord, chain
from celery.signals import after_task_publish, task_prerun, before_task_publish, task_postrun, worker_process_init
from celery.registry import tasks
from edge.celery import app
from space.utils.db_handler import DBHandler

from orchestration.utils.elk_handler import ELKHandler
from orchestration.utils.consul_handler import ConsulOperation
from orchestration.scripts.dc_deploy import DCDeploy
from orchestration.scripts.micro_service import DCDeployMicroService
from orchestration.scripts.docker import DCDeployDocker
from orchestration.scripts.dc_deploy_non_f5 import DCDeployNonF5
from orchestration.scripts.storm_deploy import StormDeploy
from orchestration.scripts.aws_deploy_mmt import AWSMmt

from orchestration.utils.lb import LB
from orchestration.utils.grafana import Grafana
from orchestration.utils.edge_cache import EdgeCache
from orchestration.utils.jirautils import Jira
from orchestration.utils.generic_utils import separate_servers_by_zone, get_script_class_name

from space.models import ActionInfo, Configs, Dendrogram
logger = logging.getLogger(__name__)

# from orchestration import tasks
# app.control.revoke(task_id)
# app.conf.task_default_queue="TPPPP"


@shared_task
def action(task_id):
    try:
        dbobj = DBHandler()
        action_info = ActionInfo.objects.get(id=task_id)
        if not action_info.status.name == "BUILDING":
            message = "task [%s] is either completed or not scheduled, status - %s. Can't start it." %(task_id, action_info.status.name)
            raise Exception(message)

        action_info.update_status('SCHEDULED')
        action_info.update_start_time()

        logger.info("ActionInfo[%s], status - %s" % (action_info.id, action_info.status.name))
        configs = action_info.config_dict()
        # key Name from which server details is available
        server_info = configs.get('server_info')
        server_info_dict = configs.get(server_info, {})

        # Actual servers on which action need to be taken
        servers = separate_servers_by_zone(action_info.server_list())
        script_name = action_info.script_file_name
        zone_list = [{'zone' : zone, server_info : server_info_dict.get(zone), 'servers': servers.get(zone)} for zone in servers if servers.get(zone)]

        logger.debug("server_info_dict - %s zone_list[%s]- %s" %(server_info_dict, len(zone_list), zone_list))
        zone_parallelazation = configs.get('zone_parallelazation', True)
        if zone_parallelazation is True:
            if len(zone_list) > 1:
                res = chord([action_zone.s(action_info.id, serverdetail, script_name)
                            for serverdetail in zone_list ])(closure_task.s(task_id=task_id).on_error(closure_error_task.s(task_id=task_id)))
                for taskids in res.parent.children:
                    dbobj.updateActionInfoTaskIds(action_info, taskids.task_id)
            elif len(zone_list) == 1:
                res = action_zone.apply_async((action_info.id, zone_list[0], script_name), link=closure_task.s(task_id=task_id), link_error=closure_error_task.s(task_id=task_id))
                dbobj.updateActionInfoTaskIds(action_info, res.task_id)
            else:
                raise Exception("Unable to capture zone info from task- %s" % task_id)
        else:
            zone_serialization_order = configs.get('zone_serialization_order', [])
            edge_cache = EdgeCache(task_id)
            current_serialize_zone = edge_cache.get().get('current_serialize_zone', None)
            next_serialize_zone = edge_cache.get().get('next_serialize_zone', None)

            if current_serialize_zone is None and next_serialize_zone is None:
                # It means it is first zone deployment.
                current_serialize_zone = zone_serialization_order[0] if len(zone_serialization_order) > 0 else None
                next_serialize_zone = zone_serialization_order[1] if len(zone_serialization_order) > 1 else None
                edge_cache.set(next_serialize_zone=next_serialize_zone, current_serialize_zone=current_serialize_zone)
            elif next_serialize_zone is not None:
                current_serialize_zone = next_serialize_zone
                next_serialize_zone_index = zone_serialization_order.index(current_serialize_zone)+1
                next_serialize_zone = next_serialize_zone_index if len(zone_serialization_order) > next_serialize_zone_index+1 else None
                edge_cache.set(next_serialize_zone=next_serialize_zone, current_serialize_zone=current_serialize_zone)
            else:
                logger.info("deployment for all zone - %s has been completed." % zone_serialization_order)
                action_info.update_status('COMPLETED')
                return
            if current_serialize_zone is not None:
                zone_configuration = [ zone_detail for zone_detail in zone_list if zone_detail.get('zone') == current_serialize_zone ]
                if len(zone_configuration) > 0:
                    res = action_zone.apply_async((action_info.id, zone_configuration[0], script_name),
                                                  link=closure_task.s(task_id=task_id), link_error=closure_error_task.s(task_id=task_id))
                    dbobj.updateActionInfoTaskIds(action_info, res.id)
                    ELKHandler(task_id).write_logs(exception="Scheduling task for zone - %s" % current_serialize_zone, level='info')
                else:
                    message="No Zone Information Configured for zone - %s" % current_serialize_zone
                    ELKHandler(task_id).write_logs(exception=message, level="warn")
                    closure_task(task_id=task_id)
                    # not raising error as there might be no servers selected for this zone
                    # raise Exception(message)
        edge_cache = EdgeCache(task_id)
        zone = [zone.get('zone') for zone in zone_list]
        edge_cache.set(zone=zone)
        try:
            # Update Status in Jira
            email_dict = {}
            jira_id = configs.get('jira_id', None)
            space_name = dbobj.getSpaceName(action_info.project.name)
            host_uri = dbobj.getValue("edge_host")
            uri="%s%s" %(host_uri, reverse('action', args=(space_name,task_id)))
            message = "Started - %s at Edge Task Id - %s, check status : - %s" % (action_info.action.name, task_id, uri)
            if jira_id is not None and action_info.action.name.lower() == "deploy":
                jira_obj = Jira(jira_id)
                jira_obj.update_transition("InProgress")
                jira_obj.comment(message)

            if configs.get('notify_me', False):

                if configs.get('notify_action', 'all') in [action_info.action.name,'all']:

                    reason = configs.get('description', None)
                    email_dict['reason'] = reason
                    email_dict['action'] = action_info.action.name
                    email_dict['task_id'] = task_id
                    email_dict['uri'] = uri
                    email_dict['user'] = action_info.user.first_name

                    recipients = dbobj.getSpaceDLs(action_info.project.name)
                    cc = []
                    subject = 'Edge notify for Project - %s | Action -%s | Task Id - [#%s]' % (action_info.project.name, action_info.action.name, task_id)
                    result = render('report/templates/email_msg.html',email_dict)
                    email_from = 'edge_'+action_info.action.name+'@makemytrip.com'
                    edge_email = EmailMessage(subject, result, email_from, recipients, cc=cc)
                    edge_email.content_subtype = "html"
                    edge_email.send(fail_silently=False)

        except Exception, e:
            logger.error(e)
    except Exception, e:
        logger.exception(e)
        dbobj.setActionInfoState(task_id, 'FAILED')
        dbobj.updateActionInfoEndTime(task_id)
        # Send Error to ELK
        ELKHandler(task_id).write_logs(exception=str(e))


def get_action_object(task_id):
    dbobj = DBHandler()
    return dbobj.getActionInfoObj(task_id)

def render(tpl_path, context):
        path, filename = os.path.split(tpl_path)
        return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(filename).render(context=context)


def get_task_status(task_id):
    status = None
    data = EdgeCache(task_id).get()
    if data is None or type(data) is not dict or len(data) == 0:
        return status
    TASK_STATUS_PRIORITY = DBHandler().getActionStatus()
    TASK_STATUS_PRIORITY.append(None)
    for zone in data.get('zone', []):
        rdata = EdgeCache(task_id, zone).get()
        if rdata.get('task_status') in TASK_STATUS_PRIORITY and TASK_STATUS_PRIORITY.index(
                rdata.get('task_status')) < TASK_STATUS_PRIORITY.index(status):
            status = rdata.get('task_status')
    return status

def check_completion_server_wise(action):
    status = True
    try:
        es = ELKHandler(action.id)
        es_data = es.read_action_entries()
        server_list = action.server_list()
        es_server_info = {}
        for server in server_list:
            es_server_info[server] = {"version": None, "project": action.project.name}
        for entry in es_data:
            if entry.get("category") == "report" and entry.get("version") == action.config_dict().get("version"):
                    es_server_info[entry.get("server")]["version"] = entry.get("version")
                    try:
                        dendrogram_info = Dendrogram.objects.get(server=entry.get("server"), project=action.project)
                        if action.action.name not in ["restart","hard_restart"]:
                            dendrogram_info.version = entry.get("version")
                            dendrogram_info.save()
                            logger.info("Updating dendrogram data for %s - %s" % (action.project.name, entry.get("server")))
                        else: 
                            logger.info("Not updating dendrogram data for %s - %s for action - %s" % (action.project.name, entry.get("server"), action.action.name))
                            pass
                    except Dendrogram.DoesNotExist as e:
                        version_name = "Unknown" if action.action.name in ["restart","hard_restart"] else entry.get('version')
                        Dendrogram(project=action.project, user=action.user, server=entry.get("server"), version=version_name).save()

        for server, info in es_server_info.items():
            if info.get("version") is None:
                status = False
                break
    except Exception as e:
        logger.exception(e)
    finally:
        logger.info(" for action %s check_completion_server_wise status is %s" % (action.id, status))
        return status


@shared_task
def closure_task(*args, **kwargs):
    logger.info(args)
    logger.info(kwargs)
    task_id = kwargs.get('task_id', None)
    logger.info("Executing Closure Task for id - %s " % task_id)
    status = get_task_status(task_id)
    dbobj = DBHandler()
    if status is None:
        try:
            action_obj = get_action_object(task_id)
            configs = action_obj.config_dict()
            if configs.get('zone_parallelazation', True) is False:
                dbobj.setActionInfoState(task_id, 'BUILDING')
                action.delay(task_id)
        except Exception, e:
            raise Exception(e)
        try:
            # check if all servers are deployed/restarted for this action
            action_obj = get_action_object(task_id)
            completion_status = check_completion_server_wise(action_obj)
            if completion_status is True:
                status='COMPLETED'
                logger.info("task is completed over all the servers. updating over jira, consul")
                dbobj.setActionInfoState(task_id, status)

                # Updating over Grafana
                if configs.get('dashboard_name', None) is not None:
                    if action_obj.action.name.lower() in ["deploy","hard_deploy","rollback","hard_rollback"]:
                        try:
                            task_end_time = localtime(action_obj.task_end_time)
                            dashboard = configs.get('dashboard_name', None)
                            version = configs.get('version', None)
                            grafanaobj = Grafana(dashboard)
                            response = grafanaobj.send_annotations(task_id, task_end_time, version, action_obj.project.space.name, action_obj.action.name.lower(), action_obj.project.name)
                            logger.info("Updated to dashboard - {db}, taskid - {tid}, response - {resp}".format(db=dashboard,tid=task_id,resp=response))
                        except Exception as e:
                            logger.info("Error sending to grafana . Edge task id - {task}. Error - {err}".format(task=task_id,err=e))

                jira_id = configs.get('jira_id', None)
                if jira_id is not None and action_obj.action.name.lower() == "deploy":
                    jira_obj = Jira(jira_id)
                    jira_obj.update_transition("Completed")

                # update consul for scaling purpose
                consul_client = ConsulOperation()
                key = "projects/" + action_obj.project.space.name.upper() + "/" + action_obj.project.name
                version = configs.get('version', None)
                set_output = consul_client.setKV(key,version)
                logger.debug('consul setKV resp %s' % set_output)
            else:
                status='FAILED'
                dbobj.setActionInfoState(task_id, status)
        except Exception as e:
            logger.exception(e)
    else:
        dbobj.setActionInfoState(task_id, status)
    dbobj.updateActionInfoEndTime(task_id)


@shared_task
def closure_error_task(*args, **kwargs):
    logger.debug(args)
    logger.debug(kwargs)
    task_id = kwargs.get('task_id', None)
    logger.info("Executing Closure Error Task for id - %s " % task_id)
    status = get_task_status(task_id)
    if status is None:
        status = 'FAILED'
        try:
            action_obj = get_action_object(task_id)
            configs = action_obj.config_dict()
            jira_id = configs.get('jira_id', None)
            completion_status = check_completion_server_wise(action_obj)
            if jira_id is not None and action_obj.action.name.lower() == "deploy":
                jira_obj = Jira(jira_id)
                jira_obj.update_transition("Failed")
            if configs.get('notify_me', False):
                space_name = action_obj.project.space.name
                recipients = action_obj.project.space.dls()
                cc = []
                host_uri = Configs().getValue("edge_host")
                uri = "%s%s" % (host_uri, reverse('action', args=(space_name,task_id)))
                message = "Error for Edge Task Id - %s, check status : - %s" % (task_id, uri)
                subject = 'Edge notify Error for %s [#%s]' % (action_obj.project.name, task_id)
                edge_email = EmailMessage(subject, message, settings.EMAIL_FROM, recipients, cc=cc)
                edge_email.content_subtype = "html"
                edge_email.send(fail_silently=False)
        except Exception as e:
            logger.exception(e)

    dbobj = DBHandler()
    dbobj.setActionInfoState(task_id, status)
    dbobj.updateActionInfoEndTime(task_id)
    logger.info("Executed Closure Error Task for id - %s " % task_id)


@shared_task
def action_zone(task_id, params, script_name=None):
    try:
        class_name = get_script_class_name(script_name)
        class_method = globals().get(class_name, None)
        logger.debug("Class Name Found - %s, Method - %s" % (class_name, class_method))
        if class_method is None:
            raise Exception("No Scripts - %s can be found to deploy for task_id - %s"  %(script_name, task_id))

        dbobj = DBHandler()
        action_info = dbobj.getActionInfoObj(task_id)
        action_info.update_status('INPROGRESS')
        logger.debug("TaskObj - Status - %s" % action_info.status.name)
        script_obj = class_method(action_info, params=params)
        action = action_info.action.name.lower()

        logger.debug("Exec %s on %s, task id - %s for zone - %s with params - %s" %(action, action_info.project, action_info.id, params.get('zone'), params))
        getattr(script_obj, action)()
        logger.info("Task[%s] for Project- %s for zone- %s is completed" %(action_info.id, action_info.project, params.get('zone')))
        if ActionInfo.objects.get(id=task_id).config_dict().get('is_canary') is True:
            closure_task(task_id=task_id)
    except Exception, e:
        logger.exception(e)
        if ActionInfo.objects.get(id=task_id).config_dict().get('is_canary') is True:
            EdgeCache(task_id, params.get('zone')).set(task_status='FAILED')
            closure_error_task(task_id=task_id)
        raise Exception(e)


def killing_task(task_id, reason=None, user=None, kill_action='MANUAL_FAILED'):
    dbobj = DBHandler()
    task_obj = dbobj.getActionInfoObj(task_id)
    killed_status = False
    celery_stop_task_status = [ 'REVOKED', 'SUCCESS', 'FAILED' ]

    # if killed_status is True:
    dbobj.updateActionInfoEndTime(task_id)
    dbobj.setActionInfoState(task_id, kill_action.upper(), reason)
    username = user.username if user else "anonymous_user"
    killing_logs = "task is %s by %s, reason %s, killed_status %s" % (kill_action.upper(), username, reason, killed_status)
    ELKHandler(task_id).write_logs(exception=killing_logs)

    try:
        for task in task_obj.task_ids.split(","):
            retry_count = 3
            task_killed_status = False
            if task is not None and str(task).strip != "":
                while retry_count > 0 and task_killed_status is False:
                    logger.info("Revoking Task Id - %s for Action Task Id - %s, Trying - %s" %(task, task_id, retry_count))
                    app.control.revoke(task, terminate=True)
                    time.sleep(1)
                    response = AsyncResult(task)
                    if response.status.upper() in celery_stop_task_status:
                        task_killed_status = True
                        logger.info("Task ID - %s has been revoked with status - %s and state - %s" %(task, response.status, response.state))
                    retry_count -= 1
                    if response.status.upper() == 'REVOKED':
                        killed_status = True
                if task_killed_status is False:
                    exception = "Unable to Revoke on Action Info Id - %s celery task id - %s with state %s" %(task_id, task, response.state)
                    ELKHandler(task_id).write_logs(exception=exception)
    except Exception as e:
        logger.error(e)


@worker_process_init.connect
def fix_multiprocessing(**kwargs):
    # don't be a daemon, so we can create new subprocesses
    from multiprocessing import current_process
    current_process().daemon = False
