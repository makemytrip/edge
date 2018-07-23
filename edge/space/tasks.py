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

# Create your tasks here
from __future__ import absolute_import, unicode_literals
from celery import shared_task
from space.models import ActionQueue, Project, ActionInfo
from space.utils.dash import DashUtils
from django.http import HttpResponseRedirect
from celery import Celery
from celery.schedules import crontab
from celery.decorators import periodic_task
from space.views import Plan
from orchestration.utils.jirautils import Jira
from space.utils.db_handler import DBHandler

import logging, requests, json

logger = logging.getLogger(__name__)


@periodic_task(
    #run_every=crontab(minute='*/5'),
    run_every=crontab(),
    name="action_queue_tasks",
    ignore_result=True
)
def check_queue_entries():

    dbobj = DBHandler()
    queued_tasks = ActionQueue.objects.all()
    logger.info("starting to check queue entries")

    for task in queued_tasks:
        if task.action.name == "restart":
            queue_retries = int(dbobj.getValue("restart_queue_retries"))
        elif task.action.name == "deploy":
            queue_retries = int(dbobj.getValue("deploy_queue_retries"))
        else: 
            queue_retries = 10
        if task.retries < queue_retries:
            server_list = []
            total_servers = task.server_list()
            server_list.extend(total_servers)
            check_queue = DashUtils().check_active_servers(server_list, task.space, task.project.name, task.action.name)
            if len(check_queue) > 0:
                task.retries += 1
                logger.debug("updating retries %d for project %s from action queue" % (task.retries, task.project.name))
                task.save()
            else:
                host_uri=dbobj.getValue("edge_host")
                url = host_uri + "/space/" + task.space.name + "/" + task.project.name + "/" + task.action.name + "/"
                payload = {'content':{'servers': server_list, 'user': task.user.username}}
                start_task = requests.post(url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                action_id = start_task.json().get('action_id', None)
                logger.debug("started task %s for queue entry - %s, %s -- %s" % (action_id, task.project.name, task.user.username, dbobj.getValue("st2_user")))
                if task.user.username == dbobj.getValue("st2_user"):
                    logger.info("sending response to st2 for queue id %s and task id %s" % (task.id, action_id))
                    payload = {'queue_id': task.id, 'action_id': action_id, 'status': True}
                    send_st2 = send_response_to_st2(dbobj, payload)
                    logger.info("Response recieved from st2 - %s" %(send_st2.text))
                task.delete()
        else:
            # Jira update
            jira_id = Project.objects.get(name=task.project).config_dict().get('jira_id')
            host_uri= dbobj.getValue("edge_host")
            jira_msg = "Unable to perform action. Maximum retry count has been exceeded."
            jira_obj = Jira(jira_id)
            jira_obj.comment(str(jira_msg))

            # st2 update
            if task.user.username == dbobj.getValue("st2_user"):
                logger.info("sending response queue_failed to st2 for queue id %s" % (task.id))
                payload = {'queue_id': task.id, 'status': False, 'error': jira_msg}
                send_st2 = send_response_to_st2(dbobj, payload)
                logger.info("Response recieved from st2 - %s" %(send_st2.text))

            task.delete()
    return True

def send_response_to_st2(dbobj, payload):
    header = {'St2-Api-Key':dbobj.getValue("st2_api_key"),'Content-Type': 'application/json'}
    send_st2 = requests.post(dbobj.getValue("st2_host"), data=json.dumps(payload), headers=header, verify=False)
    return send_st2
